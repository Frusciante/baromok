"""
카메라 워커 스레드

QThread 기반 실시간 카메라 프레임 처리
"""

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from datetime import datetime
from typing import Optional
import logging

from src.core.landmark_extractor import LandmarkExtractor, ExtractedLandmarks
from src.core.indicator_calculator import IndicatorCalculator, PostureIndicators
from src.core.judgment_engine import JudgmentEngine, PostureJudgmentResult
from src.core.state_machine import StateMachine, PostureState

logger = logging.getLogger(__name__)


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

        Args:
            landmark_extractor: 랜드마크 추출기
            indicator_calculator: 지표 계산기
            judgment_engine: 판정 엔진
            state_machine: 상태 머신
            camera_index: 카메라 인덱스 (0 = 기본 카메라)
            camera_fps: 카메라 FPS
            camera_width: 카메라 해상도 너비
            camera_height: 카메라 해상도 높이
        """
        super().__init__()

        self.landmark_extractor = landmark_extractor
        self.indicator_calculator = indicator_calculator
        self.judgment_engine = judgment_engine
        self.state_machine = state_machine

        self.camera_index = camera_index
        self.camera_fps = camera_fps
        self.camera_width = camera_width
        self.camera_height = camera_height
        self.frame_delay = int(1000 / camera_fps)  # ms 단위

        # 카메라 객체
        self.cap = None

        # 스레드 제어 플래그
        self.is_running = False
        self.is_paused = False

        # 프레임 카운터
        self.frame_count = 0
        self.start_time: Optional[datetime] = None

        logger.info(
            f"CameraWorker 초기화: {camera_width}x{camera_height} @ {camera_fps} FPS"
        )

    def run(self):
        """스레드 메인 루프"""
        try:
            # 카메라 초기화
            self.cap = cv2.VideoCapture(self.camera_index)

            if not self.cap.isOpened():
                error_msg = f"카메라 {self.camera_index}를 열 수 없습니다"
                logger.error(error_msg)
                self.error_signal.emit(error_msg)
                return

            # 카메라 설정
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
            self.cap.set(cv2.CAP_PROP_FPS, self.camera_fps)

            self.is_running = True
            self.start_time = datetime.now()
            self.frame_count = 0

            logger.info("카메라 캡처 시작")
            self.status_changed_signal.emit("카메라 시작됨")

            # 메인 루프
            while self.is_running:
                # 일시정지 상태 확인
                if self.is_paused:
                    self.msleep(100)
                    continue

                # 프레임 읽기
                ret, frame = self.cap.read()

                if not ret:
                    logger.warning("프레임 읽기 실패")
                    break

                # 프레임 처리
                try:
                    frame_data = self.process_frame(frame)
                    self.frame_processed_signal.emit(frame_data)
                    self.frame_count += 1
                except Exception as e:
                    logger.error(f"프레임 처리 중 오류: {e}", exc_info=True)
                    self.error_signal.emit(f"프레임 처리 오류: {str(e)}")

                # FPS 제어 (지연)
                self.msleep(self.frame_delay)

            logger.info(f"카메라 캡처 종료 (처리된 프레임: {self.frame_count})")
            self.status_changed_signal.emit("카메라 종료됨")

        except Exception as e:
            error_msg = f"카메라 스레드 오류: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error_signal.emit(error_msg)

        finally:
            # 정리
            if self.cap is not None:
                self.cap.release()
            self.is_running = False

    def process_frame(self, frame: np.ndarray) -> dict:
        """
        프레임 처리

        1. 랜드마크 추출
        2. 지표 계산
        3. 판정 (posture_type, probability)
        4. 상태 머신 업데이트

        Args:
            frame: OpenCV 프레임 (BGR)

        Returns:
            {
                'frame': 주석 달린 프레임 (numpy array),
                'frame_rgb': RGB 프레임,
                'landmarks': ExtractedLandmarks,
                'indicators': PostureIndicators,
                'posture_type': str (예: "forward_head"),
                'probability': float (0-1),
                'state': PostureState,
                'timestamp': datetime,
                'frame_number': int
            }
        """
        timestamp = datetime.now()

        # 1. 랜드마크 추출
        landmarks = ExtractedLandmarks(
            pose=None,
            face=None,
            hands=None,
            frame_timestamp_ms=0,
        )
        try:
            landmarks = self.landmark_extractor.extract_landmarks(frame)
        except Exception as e:
            logger.debug(f"랜드마크 추출 실패: {e}")

        # 2. 지표 계산
        indicators: Optional[PostureIndicators] = None
        try:
            frame_height, frame_width = frame.shape[:2]
            relevant_landmarks = self.landmark_extractor.get_relevant_landmarks(
                landmarks,
                frame_width=frame_width,
                frame_height=frame_height,
            )
            normalized_landmarks = self.landmark_extractor.normalize_landmarks(
                relevant_landmarks,
                frame_width=frame_width,
                frame_height=frame_height,
            )
            indicators = self.indicator_calculator.calculate_all_indicators(
                normalized_landmarks,
                timestamp=timestamp.timestamp(),
            )
        except Exception as e:
            logger.debug(f"지표 계산 실패: {e}")

        # 3. 판정 (posture_type, probability)
        posture_type = "normal"
        probability = 0.0
        confirmed_posture = None
        judgment_result: Optional[PostureJudgmentResult] = None
        if indicators is not None:
            try:
                judgment_result = self.judgment_engine.judge_single_frame(indicators)
                self.judgment_engine.accumulate_frame(judgment_result)
                confirmed_posture = self.judgment_engine.get_confirmed_posture(
                    fps=self.camera_fps
                )

                if judgment_result.dominant_posture:
                    posture_type = judgment_result.dominant_posture
                    likelihood_map = {
                        "forward_head": judgment_result.forward_head_likelihood,
                        "recline": judgment_result.recline_likelihood,
                        "crossed_leg_estimated": judgment_result.crossed_leg_likelihood,
                        "chin_rest_estimated": judgment_result.chin_rest_likelihood,
                    }
                    probability = float(likelihood_map.get(posture_type, 0.0))
            except Exception as e:
                logger.debug(f"판정 실패: {e}")

        # 4. 상태 머신 업데이트
        try:
            if confirmed_posture:
                self.state_machine.update_state(confirmed_posture)
            else:
                self.state_machine.update_state(None)
        except Exception as e:
            logger.debug(f"상태 머신 업데이트 실패: {e}")

        current_state = self.state_machine.get_current_state()

        # 5. 시각화 (주석 달린 프레임)
        annotated_frame = self._annotate_frame(
            frame, landmarks, indicators, posture_type, probability, current_state
        )

        # 결과 반환
        return {
            "frame": annotated_frame,
            "frame_rgb": cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
            "landmarks": landmarks,
            "indicators": indicators,
            "posture_type": posture_type,
            "probability": probability,
            "state": current_state.value,  # "NORMAL", "WARNING", "BAD_POSTURE"
            "timestamp": timestamp,
            "frame_number": self.frame_count,
        }

    def _annotate_frame(
        self,
        frame: np.ndarray,
        landmarks: ExtractedLandmarks,
        indicators: PostureIndicators,
        posture_type: str,
        probability: float,
        state: PostureState,
    ) -> np.ndarray:
        """
        프레임에 주석 추가 (랜드마크, 상태 등)

        Args:
            frame: 원본 프레임
            landmarks: 추출된 랜드마크
            indicators: 계산된 지표
            posture_type: 자세 유형
            probability: 확률
            state: 현재 상태

        Returns:
            주석 달린 프레임
        """
        annotated = frame.copy()

        # 상태에 따른 색상
        state_colors = {
            PostureState.NORMAL: (0, 255, 0),  # 초록
            PostureState.WARNING: (0, 165, 255),  # 주황
            PostureState.BAD_POSTURE: (0, 0, 255),  # 빨강
        }
        color = state_colors.get(state, (255, 255, 255))

        # 프레임 테두리
        cv2.rectangle(
            annotated,
            (0, 0),
            (annotated.shape[1] - 1, annotated.shape[0] - 1),
            color,
            3,
        )

        # 상태 텍스트
        state_text_map = {
            PostureState.NORMAL: "정상",
            PostureState.WARNING: "경고",
            PostureState.BAD_POSTURE: "나쁜자세",
        }
        state_text = state_text_map.get(state, "알 수 없음")

        # 상단 정보 표시
        info_text = f"{state_text} | {posture_type} | Prob: {probability:.2f}"
        cv2.putText(
            annotated, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2
        )

        # 랜드마크 시각화 (얼굴 중앙점만 간단히)
        if landmarks.pose is not None and landmarks.pose.landmarks:
            nose = landmarks.pose.landmarks[0]
            x = int(nose[0] * annotated.shape[1])
            y = int(nose[1] * annotated.shape[0])
            cv2.circle(annotated, (x, y), 5, (0, 255, 255), -1)

        # 지표 정보 (간단한 버전)
        if indicators is not None:
            indicator_text = f"Cheek: {indicators.cheek_distance:.2f}"
            cv2.putText(
                annotated,
                indicator_text,
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (200, 200, 200),
                1,
            )

        return annotated

    def pause(self):
        """캡처 일시정지"""
        self.is_paused = True
        logger.info("카메라 일시정지")
        self.status_changed_signal.emit("일시정지됨")

    def resume(self):
        """캡처 재개"""
        self.is_paused = False
        logger.info("카메라 재개")
        self.status_changed_signal.emit("재개됨")

    def stop_capture(self):
        """캡처 중지"""
        self.is_running = False
        logger.info("카메라 중지 요청")
        self.wait()  # 스레드 종료 대기

    def get_elapsed_time(self) -> int:
        """경과 시간 반환 (초)"""
        if self.start_time is None:
            return 0
        return int((datetime.now() - self.start_time).total_seconds())


def create_camera_worker(
    landmark_extractor: LandmarkExtractor,
    indicator_calculator: IndicatorCalculator,
    judgment_engine: JudgmentEngine,
    state_machine: StateMachine,
    config=None,
) -> CameraWorker:
    """카메라 워커 생성"""

    # 설정에서 카메라 파라미터 읽기
    if config:
        camera_index = config.get_app_setting("camera_index")
        camera_fps = config.get_app_setting("camera_fps")
        camera_width = config.get_app_setting("camera_resolution_width")
        camera_height = config.get_app_setting("camera_resolution_height")
    else:
        camera_index = 0
        camera_fps = 30
        camera_width = 1280
        camera_height = 720

    return CameraWorker(
        landmark_extractor,
        indicator_calculator,
        judgment_engine,
        state_machine,
        camera_index=camera_index,
        camera_fps=camera_fps,
        camera_width=camera_width,
        camera_height=camera_height,
    )
