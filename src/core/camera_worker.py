"""
카메라 워커 스레드

QThread 기반 실시간 카메라 프레임 처리 (멀티스레드 판정 통합)
"""

import cv2
import numpy as np
import threading
import time
from PyQt6.QtCore import QThread, pyqtSignal
from datetime import datetime
from typing import Optional, Dict, Any, List

from src.utils.logger import get_logger

from src.core.landmark_extractor import LandmarkExtractor, ExtractedLandmarks
from src.core.indicator_calculator import IndicatorCalculator, PostureIndicators
from src.core.judgment_engine import JudgmentEngine, PostureJudgmentResult, PostureType
from src.core.state_machine import StateMachine, PostureState
from src.core.judge_workers import PostureJudgeManager

logger = get_logger(__name__)


class CameraWorker(QThread):
    """카메라 스레드 워커 (30 FPS)"""

    # 신호 정의
    frame_processed_signal = pyqtSignal(dict)  # 처리된 프레임 데이터
    status_changed_signal = pyqtSignal(str)  # 상태 변경 메시지
    error_signal = pyqtSignal(str)  # 오류 메시지

    def __init__(
        self,
        landmark_extractor: LandmarkExtractor,
        indicator_calculator: IndicatorCalculator,
        judgment_engine: JudgmentEngine,
        state_machine: StateMachine,
        camera_index: int = 0,
        camera_fps: int = 30,
        camera_width: int = 1280,
        camera_height: int = 720,
    ):
        """
        초기화
        """
        super().__init__()

        self.landmark_extractor = landmark_extractor
        self.indicator_calculator = indicator_calculator
        self.judgment_engine = judgment_engine
        self.state_machine = state_machine

        # 멀티스레드 판정 매니저 초기화 및 연결
        self.judge_manager = PostureJudgeManager(self.judgment_engine.config, self.judgment_engine.baseline_manager)
        self.judge_manager.all_results_ready.connect(self._handle_judgment_results)

        self.camera_index = camera_index
        self.camera_fps = camera_fps
        self.camera_width = camera_width
        self.camera_height = camera_height
        self.frame_delay = int(1000 / camera_fps)  # ms 단위

        # 카메라 객체
        self.cap = None

        # 스레드 제어 플래그
        self._running_event = threading.Event()
        self._paused_event = threading.Event()
        self.is_running = False
        self.is_paused = False

        # baseline 수집 모드
        self.is_baseline_mode = False
        self.current_step = 0
        
        # 실제 판정 수행 여부 (Warmup 모드에서는 False)
        self._is_detecting = False

        # 프레임 카운터
        self.frame_count = 0
        self.start_time: Optional[datetime] = None
        
        # 최신 판정 결과 저장 (비동기 업데이트용)
        self._last_judgment_result: Optional[PostureJudgmentResult] = None
        self._last_confirmed_postures: List[str] = []
        
        # 설정 갱신 플래그 및 캐시
        self._settings_dirty = True
        self._label_cache = {}

        # 판정 시작 시간 (Warmup 제외, 실제 탐지 시간)
        self._detection_start_time: Optional[float] = None
        
        # 일시정지 시간 관리
        self._total_paused_duration = 0.0
        self._pause_start_time: Optional[float] = None

        logger.info(
            f"CameraWorker 초기화: {camera_width}x{camera_height} @ {camera_fps} FPS (멀티스레드 판정 활성)"
        )

    @property
    def is_detecting(self) -> bool:
        return self._is_detecting

    @is_detecting.setter
    def is_detecting(self, value: bool):
        # 베이스라인 모드에서는 탐지 타이머와 로직이 작동하지 않아야 함
        if self.is_baseline_mode:
            self._is_detecting = False
            self._detection_start_time = None
            self._total_paused_duration = 0.0
            self._pause_start_time = None
            return

        if value and not self._is_detecting:
            # 탐지 시작 시점 기록
            self._detection_start_time = time.time()
            self._total_paused_duration = 0.0
            self._pause_start_time = None
            logger.info("CameraWorker: 탐지 타이머 시작")
        elif not value:
            self._detection_start_time = None
            self._total_paused_duration = 0.0
            self._pause_start_time = None
        self._is_detecting = value

    def mark_settings_dirty(self):
        """설정이 변경되었음을 알림 (플래그 설정)"""
        self._settings_dirty = True
        logger.debug("CameraWorker: 설정 갱신 플래그 설정됨")

    def _sync_cached_settings(self):
        """루프 내에서 한 번만 호출되어 무거운 설정을 캐싱"""
        if not self._settings_dirty:
            return
            
        logger.info("CameraWorker: 설정 캐시 동기화 중...")
        
        # 1. 지표 계산기 설정 갱신
        self.indicator_calculator.refresh_settings()
        
        # 2. 라벨 캐시 갱신
        self._label_cache = {
            pt.value: self.judgment_engine.config.get_posture_label(pt.value)
            for pt in PostureType
        }
        self._label_cache["normal"] = "바른 자세"
        self._label_cache["baseline"] = "자세 맞춤 중"
        
        self._settings_dirty = False

    def _handle_judgment_results(self, results: List[dict]):
        """판정 워커들의 비동기 결과를 취합하여 상태 업데이트 (슬롯)"""
        now = time.time()
        
        # 1. 결과 취합
        self._last_judgment_result = self.judgment_engine.process_worker_results(results, now)
        
        # 2. 지속 시간 만족하는 자세 확인
        self._last_confirmed_postures = self.judgment_engine.get_all_confirmed_postures(now)
        
        # 3. 상태 머신 업데이트
        self.state_machine.update_state(self._last_confirmed_postures)

    def update_worker_sensitivities(self, forward_head: float, recline: float):
        """워커들의 감도를 직접 갱신 (UI 하위 호환용)"""
        sensitivity_map = {
            "forward_head": forward_head,
            "recline": recline
        }
        self.judge_manager.update_sensitivities(sensitivity_map)

    def set_baseline_mode(self, enabled: bool):
        """Baseline 수집 모드 설정"""
        self.is_baseline_mode = enabled
        if enabled:
            # 베이스라인 모드 진입 시 탐지 로직 및 타이머 비활성화
            self.is_detecting = False
            self.judgment_engine.reset_history()
            self.state_machine.reset()
            logger.info("Baseline 모드 활성화")
        else:
            logger.info("Baseline 모드 비활성화")

    def run(self):
        """스레드 메인 루프"""
        try:
            self._paused_event.clear()
            self.is_paused = False

            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                error_msg = f"카메라 {self.camera_index}를 열 수 없습니다"
                self.error_signal.emit(error_msg)
                return

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
            self.cap.set(cv2.CAP_PROP_FPS, self.camera_fps)

            self._running_event.set()
            self.is_running = True
            self.start_time = datetime.now()
            self.frame_count = 0

            if not self.is_baseline_mode:
                self.judgment_engine.reset_history()

            logger.info("카메라 캡처 시작")
            self.status_changed_signal.emit("카메라 시작됨")

            while self._running_event.is_set():
                if self._paused_event.is_set():
                    self.msleep(100)
                    continue

                ret, frame = self.cap.read()
                if not ret: break

                try:
                    frame_data = self.process_frame(frame)
                    self.frame_processed_signal.emit(frame_data)
                    self.frame_count += 1
                except Exception as e:
                    logger.error(f"프레임 처리 중 오류: {e}")

                if not self.is_baseline_mode:
                    self.msleep(self.frame_delay)

        except Exception as e:
            self.error_signal.emit(f"카메라 스레드 오류: {e}")
        finally:
            if self.cap: self.cap.release()
            self._running_event.clear()
            self.is_running = False

    def process_frame(self, frame: np.ndarray) -> dict:
        """프레임 처리 (탐지 단계가 아니면 로직 스킵)"""
        # 0. 설정 갱신 확인 (플래그 기반 캐싱)
        self._sync_cached_settings()

        timestamp = datetime.now()
        current_timestamp_seconds = timestamp.timestamp()

        # 1. 탐지 비활성 모드 (단순 예열) 처리
        # 탐지 중도 아니고, 베이스라인 수집 중도 아닌 경우 로직 수행 안 함
        if not self.is_detecting and not self.is_baseline_mode:
            return {
                "frame": frame.copy(),  # 효과 없는 원본 프레임
                "frame_rgb": cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                "landmarks": None,
                "indicators": None,
                "posture_type": "warmup",
                "probability": 0.0,
                "display_label": "예열 중",
                "state": PostureState.NORMAL.value,
                "timestamp": timestamp,
                "frame_number": self.frame_count,
                "active_postures": []
            }

        # 2. 랜드마크 추출 (탐지 또는 베이스라인 모드일 때만 수행)
        landmarks = self.landmark_extractor.extract_landmarks(frame)

        # 2. 지표 계산
        frame_height, frame_width = frame.shape[:2]
        relevant_landmarks = self.landmark_extractor.get_relevant_landmarks(
            landmarks, frame_width=frame_width, frame_height=frame_height
        )
        normalized_landmarks = self.landmark_extractor.normalize_landmarks(
            relevant_landmarks, frame_width=frame_width, frame_height=frame_height,
            timestamp_ms=landmarks.frame_timestamp_ms, baseline_mode=self.is_baseline_mode
        )
        
        indicators = self.indicator_calculator.calculate_all_indicators(
            normalized_landmarks, timestamp=current_timestamp_seconds, baseline_mode=self.is_baseline_mode
        )
        if indicators: indicators.step_index = self.current_step

        # Baseline 모드 처리
        if self.is_baseline_mode:
            current_state = self.state_machine.get_current_state()
            annotated_frame = self._annotate_frame(frame, landmarks, indicators, "baseline", 0.0, current_state, normalized_landmarks, "자세 맞춤 중")
            return {
                "frame": annotated_frame, "frame_rgb": cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                "landmarks": landmarks, "indicators": indicators, "posture_type": "baseline",
                "probability": 0.0, "state": current_state.value, "timestamp": timestamp, "frame_number": self.frame_count
            }

        # 3. 비동기 판정 브로드캐스트
        posture_type = "normal"
        probability = 0.0
        display_label = ""
        
        if indicators is not None:
            # 워커들에게 판정 요청
            self.judge_manager.broadcast_indicators(indicators)
            
            # UI용으로는 가장 최근에 수집된 비동기 결과 사용
            if self._last_judgment_result:
                if self._last_judgment_result.dominant_posture:
                    posture_type = self._last_judgment_result.dominant_posture
                    for p in self._last_judgment_result.active_postures:
                        if p["posture_type"] == posture_type:
                            probability = p["likelihood"]
                            break
                
                if len(self._last_judgment_result.active_postures) > 1:
                    active_names = [self._label_cache.get(p["posture_type"], p["posture_type"]) 
                                    for p in self._last_judgment_result.active_postures]
                    display_label = f"{', '.join(active_names)} 동시 감지"

        current_state = self.state_machine.get_current_state()

        # 4. 시각화
        annotated_frame = self._annotate_frame(
            frame, landmarks, indicators, posture_type, probability,
            current_state, normalized_landmarks=normalized_landmarks, display_label=display_label
        )

        return {
            "frame": annotated_frame, "frame_rgb": cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
            "landmarks": landmarks, "indicators": indicators, "posture_type": posture_type,
            "probability": probability, "display_label": display_label, "state": current_state.value,
            "timestamp": timestamp, "frame_number": self.frame_count,
            "active_postures": [p["posture_type"] for p in self._last_judgment_result.active_postures] if self._last_judgment_result else []
        }

    def _annotate_frame(
        self, frame, landmarks, indicators, posture_type, probability, state, normalized_landmarks=None, display_label=""
    ) -> np.ndarray:
        """프레임 시각화 로직"""
        annotated = frame.copy()
        frame_height, frame_width = annotated.shape[:2]
        
        state_colors = {PostureState.NORMAL: (0, 255, 0), PostureState.WARNING: (0, 165, 255), PostureState.BAD_POSTURE: (0, 0, 255)}
        color = state_colors.get(state, (255, 255, 255))
        cv2.rectangle(annotated, (0, 0), (frame_width-1, frame_height-1), color, 3)

        # [삭제] 왼쪽 상단 정보 텍스트 (사용자 요청)
        
        # 랜드마크 시각화
        try:
            rel_lms = self.landmark_extractor.get_relevant_landmarks(landmarks, frame_width, frame_height)
            for key in ["face_center", "left_eye", "right_eye", "left_shoulder", "right_shoulder"]:
                pt = rel_lms.get(key)
                if pt: cv2.circle(annotated, pt, 4, (0, 255, 0), -1)
        except: pass

        return annotated

    def pause(self):
        """캡처 및 판정 일시정지"""
        if not self._paused_event.is_set():
            self._paused_event.set()
            self.is_paused = True
            # 탐지 중인 경우 일시정지 시작 시점 기록
            if self.is_detecting:
                self._pause_start_time = time.time()
                logger.debug("CameraWorker: 탐지 타이머 일시정지")

    def resume(self):
        """캡처 및 판정 재개"""
        if self._paused_event.is_set():
            self._paused_event.clear()
            self.is_paused = False
            # 탐지 중인 경우 누적 일시정지 시간 계산
            if self.is_detecting and self._pause_start_time is not None:
                pause_delta = time.time() - self._pause_start_time
                self._total_paused_duration += pause_delta
                self._pause_start_time = None
                logger.debug(f"CameraWorker: 탐지 타이머 재개 (이번 정지: {pause_delta:.1f}초)")

    def stop_capture(self):
        self._running_event.clear()
        self._paused_event.clear()
        self.is_running = False
        self.judge_manager.stop_all() # 판정 워커들도 종료
        self.wait(2000)

    def get_elapsed_time(self) -> int:
        if self._detection_start_time is None: return 0
        
        total_elapsed = time.time() - self._detection_start_time
        
        # 현재 일시정지 중이라면 진행 중인 정지 시간도 빼야 함
        current_pause = 0.0
        if self.is_paused and self._pause_start_time is not None:
            current_pause = time.time() - self._pause_start_time
            
        active_time = total_elapsed - (self._total_paused_duration + current_pause)
        return int(max(0, active_time))


def create_camera_worker(le, ic, je, sm, config=None) -> CameraWorker:
    if config:
        idx = config.get_app_setting("camera_index")
        fps = config.get_app_setting("camera_fps")
        w = config.get_app_setting("camera_resolution_width")
        h = config.get_app_setting("camera_resolution_height")
    else:
        idx, fps, w, h = 0, 30, 1280, 720
    return CameraWorker(le, ic, je, sm, camera_index=idx, camera_fps=fps, camera_width=w, camera_height=h)
