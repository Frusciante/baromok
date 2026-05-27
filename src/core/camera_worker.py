"""
카메라 워커 스레드

QThread 기반 실시간 카메라 프레임 처리
"""

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from datetime import datetime
from typing import Optional, Dict, Any

from src.utils.logger import get_logger

from src.core.landmark_extractor import LandmarkExtractor, ExtractedLandmarks
from src.core.indicator_calculator import IndicatorCalculator, PostureIndicators
from src.core.judgment_engine import JudgmentEngine, PostureJudgmentResult
from src.core.state_machine import StateMachine, PostureState

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

        # baseline 수집 모드
        # True일 때는 랜드마크 추출과 지표 계산까지만 수행하고,
        # JudgmentEngine / StateMachine은 실행하지 않는다.
        self.is_baseline_mode = False
        self.current_step = 0  # 자세 맞춤 단계 (0=대기, 1~20=수집)

        # 프레임 카운터
        self.frame_count = 0
        self.start_time: Optional[datetime] = None

        # V2 엔진 (옵셔널 — set_v2_components 로 주입)
        self.engine_mode: str = "v1"
        self._engine_v2 = None
        self._cal_mgr_v2 = None

        logger.info(
            f"CameraWorker 초기화: {camera_width}x{camera_height} @ {camera_fps} FPS"
        )

    def set_v2_components(self, engine_v2, cal_mgr_v2) -> None:
        """V2 판정 엔진 및 캘리브레이션 매니저 주입"""
        self._engine_v2 = engine_v2
        self._cal_mgr_v2 = cal_mgr_v2
        logger.info("V2 컴포넌트 설정 완료")

    def set_baseline_mode(self, enabled: bool):
        """Baseline 수집 모드 설정"""
        self.is_baseline_mode = enabled

        if enabled:
            self.judgment_engine.reset_history()
            if self._engine_v2 is not None:
                self._engine_v2.reset_filters()
            self.state_machine.reset()
            # V2 캘리브레이션 병행 수집 시작 (이미 수집 중이면 중복 시작 방지)
            if self._cal_mgr_v2 is not None and not self._cal_mgr_v2.is_collecting:
                self._cal_mgr_v2.start_collection()
                logger.info("V2 캘리브레이션 병행 수집 시작")
            logger.info("Baseline 모드 활성화: 판정/상태 머신 업데이트 비활성화")
        else:
            logger.info("Baseline 모드 비활성화: 일반 자세 감지 모드")

    def run(self):
        """스레드 메인 루프"""
        try:
            # 이전 세션에서 남은 일시정지 상태를 제거한다.
            self.is_paused = False

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

            # 일반 감지 모드로 새로 시작할 때는 이전 자세 누적 이력을 제거한다.
            if not self.is_baseline_mode:
                self.judgment_engine.reset_history()

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
                # v1.1: 캘리브레이션/베이스라인 수집 모드일 때는 대기 시간을 0으로 하여 
                # 하드웨어가 허용하는 최대 FPS로 데이터를 수집한다.
                if not self.is_baseline_mode:
                    self.msleep(self.frame_delay)
                else:
                    # 캘리브레이션 시에는 하드웨어가 허용하는 최대 속도로 프레임을 읽기 위해 
                    # 인위적인 지연(msleep)을 제거한다.
                    pass

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
        current_timestamp_seconds = timestamp.timestamp()

        # 1. 랜드마크 추출
        landmarks = ExtractedLandmarks(
            pose=None,
            face=None,
            hands=None,
            frame_timestamp_ms=0,
        )
        try:
            landmarks = self.landmark_extractor.extract_landmarks(frame)

            try:
                pose_present = landmarks.pose is not None
                face_present = landmarks.face is not None
                hands_count = len(landmarks.hands) if landmarks.hands else 0
                logger.debug(
                    f"랜드마크 추출 결과 - pose: {pose_present}, "
                    f"face: {face_present}, hands: {hands_count}"
                )
            except Exception:
                logger.debug("랜드마크 추출 결과 로깅 중 예외 발생")

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
            logger.debug(f"관련 랜드마크 (픽셀 좌표): {relevant_landmarks}")

            normalized_landmarks = self.landmark_extractor.normalize_landmarks(
                relevant_landmarks,
                frame_width=frame_width,
                frame_height=frame_height,
                timestamp_ms=landmarks.frame_timestamp_ms,
                low_latency=True # 속도 향상을 위해 항상 low_latency 적용
            )
            logger.debug(f"정규화된 랜드마크: {normalized_landmarks}")

            indicators = self.indicator_calculator.calculate_all_indicators(
                normalized_landmarks,
                timestamp=current_timestamp_seconds,
                low_latency=True # 속도 향상을 위해 항상 low_latency 적용
            )
            
            # 자세 맞춤 단계 정보 주입 (디버그용)
            if indicators:
                indicators.step_index = self.current_step

            if indicators is None:
                logger.debug(
                    "IndicatorCalculator returned None (필수 랜드마크 누락). "
                    f"relevant_landmarks={relevant_landmarks}"
                )

        except Exception as e:
            logger.debug(f"지표 계산 실패: {e}")

        # Baseline 모드에서는 판정 엔진과 상태 머신을 실행하지 않는다.
        # baseline 수집 중에 JudgmentEngine이 baseline 대비 변화율을 계산하려 하면
        # 아직 baseline이 없기 때문에 불필요한 경고와 오탐 이력이 생길 수 있다.
        if self.is_baseline_mode:
            # V2 캘리브레이션 병행 수집
            if self._cal_mgr_v2 is not None and self._cal_mgr_v2.is_collecting and indicators is not None:
                self._cal_mgr_v2.add_frame(indicators)

            current_state = self.state_machine.get_current_state()

            annotated_frame = self._annotate_frame(
                frame,
                landmarks,
                indicators,
                "baseline",
                0.0,
                current_state,
                normalized_landmarks=normalized_landmarks,
                display_label="자세 맞춤 중",
            )

            return {
                "frame": annotated_frame,
                "frame_rgb": cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                "landmarks": landmarks,
                "indicators": indicators,
                "posture_type": "baseline",
                "probability": 0.0,
                "display_label": "자세 맞춤 중",
                "state": current_state.value,
                "timestamp": timestamp,
                "frame_number": self.frame_count,
            }

        # 3. 판정 (V1 / V2 분기)
        posture_type = "normal"
        probability = 0.0
        display_label = "바른 자세"
        confirmed_posture = None
        judgment_result: Optional[PostureJudgmentResult] = None

        if indicators is not None:
            if self.engine_mode == "v2" and self._engine_v2 is not None:
                # ─── V2 판정 경로 ─────────────────────────────────────────
                try:
                    result_v2 = self._engine_v2.judge(indicators)
                    confirmed_v2 = self._engine_v2.update_sustain(result_v2)
                    posture_type = result_v2.detected_posture
                    probability = result_v2.confidence
                    display_label = result_v2.display_label
                    try:
                        if confirmed_v2 and result_v2.detected_posture != "neutral":
                            self.state_machine.update_state(confirmed_v2)
                        else:
                            self.state_machine.update_state(None)
                    except Exception as e:
                        logger.debug(f"V2 상태 머신 업데이트 실패: {e}")
                except Exception as e:
                    logger.debug(f"V2 판정 실패: {e}")
            else:
                # ─── V1 판정 경로 (기존) ──────────────────────────────────
                try:
                    judgment_result = self.judgment_engine.judge_single_frame(indicators)

                    self.judgment_engine.accumulate_frame(
                        judgment_result,
                        current_timestamp=current_timestamp_seconds,
                    )

                    confirmed_posture = self.judgment_engine.get_confirmed_posture(
                        current_timestamp=current_timestamp_seconds,
                    )

                    if judgment_result.dominant_posture:
                        posture_type = judgment_result.dominant_posture
                        likelihood_map = {
                            "forward_head": judgment_result.forward_head_likelihood,
                            "recline": judgment_result.recline_likelihood,
                            "chin_rest_estimated": judgment_result.chin_rest_likelihood,
                        }
                        probability = float(likelihood_map.get(posture_type, 0.0))
                    display_label = posture_type  # detection_screen 에서 한국어로 변환

                except Exception as e:
                    logger.debug(f"V1 판정 실패: {e}")

                # 4. V1 상태 머신 업데이트
                try:
                    if confirmed_posture:
                        self.state_machine.update_state(confirmed_posture)
                    else:
                        self.state_machine.update_state(None)
                except Exception as e:
                    logger.debug(f"상태 머신 업데이트 실패: {e}")
        else:
            # 필수 지표가 없으면 자세 누적 이력을 초기화한다.
            self.judgment_engine.reset_history()

        current_state = self.state_machine.get_current_state()

        # 5. 시각화 (주석 달린 프레임)
        # v1.1: 필터링된 정규화 좌표(normalized_landmarks)를 전달하여 시각적 안정성 확보
        annotated_frame = self._annotate_frame(
            frame,
            landmarks,
            indicators,
            posture_type,
            probability,
            current_state,
            normalized_landmarks=normalized_landmarks,
            display_label=display_label,
        )

        # 결과 반환
        return {
            "frame": annotated_frame,
            "frame_rgb": cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
            "landmarks": landmarks,
            "indicators": indicators,
            "posture_type": posture_type,
            "probability": probability,
            "display_label": display_label,
            "state": current_state.value,
            "timestamp": timestamp,
            "frame_number": self.frame_count,
        }

    def _annotate_frame(
        self,
        frame: np.ndarray,
        landmarks: ExtractedLandmarks,
        indicators: Optional[PostureIndicators],
        posture_type: str,
        probability: float,
        state: PostureState,
        normalized_landmarks: Optional[Dict[str, any]] = None,
        display_label: str = "",
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
            normalized_landmarks: 필터링된 정규화 좌표 (제공 시 시각화에 사용)

        Returns:
            주석 달린 프레임
        """
        annotated = frame.copy()
        frame_height, frame_width = annotated.shape[:2]

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
            annotated,
            info_text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )

        # 지표 정보 (상세 버전)
        if indicators is not None:
            y_offset = 60

            if self.engine_mode == "v2":
                # V2 모드: display_label + Δ 표시
                v2_text = f"[V2] {display_label} | Conf: {probability:.2f}"
                cv2.putText(annotated, v2_text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                y_offset += 20
                cheek_text = f"Cheek: {indicators.cheek_distance:.3f} | EyeTilt: {getattr(indicators, 'eye_line_tilt', 0):.1f}deg"
                cv2.putText(annotated, cheek_text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            else:
                # V1 모드: Baseline 정보 (RANSAC 기대값 포함)
                try:
                    baseline = self.judgment_engine.baseline_manager.get_baseline_metrics()
                except Exception:
                    baseline = None
                if baseline and not self.is_baseline_mode:
                    expected_cheek = self.judgment_engine.baseline_manager.get_expected_cheek(indicators.shoulder_width)
                    deviation = (indicators.cheek_distance - expected_cheek) / expected_cheek

                    debug_text = f"Cheek: {indicators.cheek_distance:.3f} (Exp: {expected_cheek:.3f})"
                    cv2.putText(annotated, debug_text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    y_offset += 20

                    delta_text = f"Dev: {deviation*100:+.1f}%"
                    cv2.putText(annotated, delta_text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    y_offset += 20

                    detail_text = f"ShldTilt: {indicators.shoulder_tilt_deg:+.1f}deg | EyeTilt: {indicators.eye_line_tilt:+.1f}deg"
                    cv2.putText(annotated, detail_text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    y_offset += 20

                    hand_text = f"HandFace: {indicators.hand_face_score:.2f} | ChinOcc: {indicators.chin_occlusion:.2f}"
                    cv2.putText(annotated, hand_text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    y_offset += 20
                else:
                    indicator_text = f"Cheek: {indicators.cheek_distance:.2f} | Sh: {indicators.shoulder_width:.2f}"
                    cv2.putText(
                        annotated,
                        indicator_text,
                        (10, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (200, 200, 200),
                        1,
                    )

        # 랜드마크 시각화
        try:
            # v1.1: 필터링된 정규화 좌표가 있다면 이를 픽셀 좌표로 변환하여 사용
            if normalized_landmarks:
                vis_landmarks = {}
                for key, val in normalized_landmarks.items():
                    if val is None:
                        vis_landmarks[key] = None
                    elif isinstance(val, tuple) and len(val) == 2:
                        vis_landmarks[key] = (int(val[0] * frame_width), int(val[1] * frame_height))
                    elif isinstance(val, list):
                        # chin_points 등 리스트 처리
                        vis_landmarks[key] = [(int(p[0] * frame_width), int(p[1] * frame_height)) for p in val]
                    else:
                        vis_landmarks[key] = val
                relevant_landmarks = vis_landmarks
            else:
                relevant_landmarks = self.landmark_extractor.get_relevant_landmarks(
                    landmarks,
                    frame_width=frame_width,
                    frame_height=frame_height,
                )

            point_styles = {
                "face_center": ((0, 255, 255), 5, "Nose"),
                "left_eye": ((255, 255, 0), 4, "L Eye"),
                "right_eye": ((255, 255, 0), 4, "R Eye"),
                "left_cheek": ((255, 0, 255), 4, "L Cheek"),
                "right_cheek": ((255, 0, 255), 4, "R Cheek"),
                "left_shoulder": ((0, 255, 0), 6, "L Shoulder"),
                "right_shoulder": ((0, 255, 0), 6, "R Shoulder"),
            }

            for key, (point_color, radius, label) in point_styles.items():
                point = relevant_landmarks.get(key)
                if point is None: continue
                x, y = point
                cv2.circle(annotated, (x, y), radius, point_color, -1)
                cv2.putText(annotated, label, (x + 6, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, point_color, 1)

            # 턱 포인트
            for index, point in enumerate(relevant_landmarks.get("chin_points", [])):
                x, y = point
                cv2.circle(annotated, (x, y), 4, (0, 128, 255), -1)

            # 손가락 팁 (정규화된 값이 있으면 이를 픽셀로 변환해서 표시)
            for hand_key, hand_color in [("left_hand_tips", (255, 128, 0)), ("right_hand_tips", (128, 0, 255))]:
                tips = relevant_landmarks.get(hand_key, [])
                for point in tips:
                    x, y = int(point[0]), int(point[1])
                    cv2.circle(annotated, (x, y), 4, hand_color, -1)

            # 어깨 및 뺨(얼굴 거리) 연결선
            ls, rs = relevant_landmarks.get("left_shoulder"), relevant_landmarks.get("right_shoulder")
            if ls and rs: cv2.line(annotated, ls, rs, (0, 255, 0), 2)
            lc, rc = relevant_landmarks.get("left_cheek"), relevant_landmarks.get("right_cheek")
            if lc and rc: cv2.line(annotated, lc, rc, (255, 0, 255), 2)

        except Exception as e:
            logger.debug(f"랜드마크 시각화 실패: {e}")

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
        self.is_paused = False
        logger.info("카메라 중지 요청")
        # 대기 시간이 무한정으로 블록되는 것을 방지하기 위해 타임아웃을 설정합니다.
        # (메인 스레드에서 호출될 수 있으므로 UI 응답없음 방지)
        waited = self.wait(2000)  # 최대 2초 대기
        if not waited:
            logger.warning("카메라 스레드가 지정된 시간 내에 종료되지 않았습니다.")

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
