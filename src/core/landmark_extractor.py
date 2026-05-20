"""
랜드마크 추출기

MediaPipe를 사용하여 웹캠 프레임에서 얼굴, 어깨, 손 랜드마크 추출
"""

import mediapipe as mp
import numpy as np
import cv2
import time
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from pathlib import Path
from src.utils.logger import get_logger
from src.utils.helpers import OneEuroFilter
from src.config import get_config
import time

logger = get_logger(__name__)


@dataclass
class LandmarkData:
    """랜드마크 데이터"""

    landmarks: List[Tuple[float, float, float]]  # (x, y, z)
    confidences: List[float]
    timestamp_ms: int


@dataclass
class ExtractedLandmarks:
    """추출된 랜드마크 결과"""

    pose: Optional[LandmarkData]
    face: Optional[LandmarkData]
    hands: Optional[List[LandmarkData]]  # 최대 2개
    frame_timestamp_ms: int


class LandmarkExtractor:
    """MediaPipe 기반 랜드마크 추출기"""

    def __init__(self, model_base_path: str = "assets/models"):
        """
        초기화

        Args:
            model_base_path: MediaPipe task 파일이 있는 디렉토리
        """
        self.model_base_path = model_base_path
        self.pose_landmarker = None
        self.face_landmarker = None
        self.hand_landmarker = None
        self.one_euro_filter = None

        # 설정 로드
        self.config = get_config()
        self.mp_config = self.config.get_mediapipe_config()

        self._initialize_models()
        logger.info("LandmarkExtractor 초기화 완료")

    def _initialize_models(self):
        """MediaPipe 모델 로드"""
        model_dir = Path(self.model_base_path)

        # 기본 임계값 설정
        face_cfg = self.mp_config.get(
            "face",
            {
                "min_detection_confidence": 0.5,
                "min_presence_confidence": 0.5,
                "min_tracking_confidence": 0.5,
            },
        )
        pose_cfg = self.mp_config.get(
            "pose",
            {
                "min_detection_confidence": 0.5,
                "min_presence_confidence": 0.5,
                "min_tracking_confidence": 0.5,
            },
        )
        hand_cfg = self.mp_config.get(
            "hand",
            {
                "min_detection_confidence": 0.5,
                "min_presence_confidence": 0.5,
                "min_tracking_confidence": 0.5,
            },
        )

        try:
            # Pose Landmarker 로드
            BaseOptions = mp.tasks.BaseOptions
            PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
            VisionRunningMode = mp.tasks.vision.RunningMode

            options = PoseLandmarkerOptions(
                base_options=BaseOptions(
                    model_asset_path=str(model_dir / "pose_landmarker.task")
                ),
                running_mode=VisionRunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=pose_cfg.get(
                    "min_detection_confidence", 0.5
                ),
                min_pose_presence_confidence=pose_cfg.get(
                    "min_presence_confidence", 0.5
                ),
                min_tracking_confidence=pose_cfg.get("min_tracking_confidence", 0.5),
            )
            self.pose_landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(
                options
            )
            logger.info(
                f"Pose Landmarker 로드 완료 (mode: VIDEO, conf: {pose_cfg.get('min_detection_confidence')})"
            )

        except Exception as e:
            logger.warning(f"Pose Landmarker 로드 실패: {e}. 대체 모델 사용...")
            self.pose_landmarker = None

        try:
            # Face Landmarker 로드
            FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions

            options = FaceLandmarkerOptions(
                base_options=BaseOptions(
                    model_asset_path=str(model_dir / "face_landmarker.task")
                ),
                running_mode=VisionRunningMode.VIDEO,
                num_faces=1,
                min_face_detection_confidence=face_cfg.get(
                    "min_detection_confidence", 0.5
                ),
                min_face_presence_confidence=face_cfg.get(
                    "min_presence_confidence", 0.5
                ),
                min_tracking_confidence=face_cfg.get("min_tracking_confidence", 0.5),
            )
            self.face_landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(
                options
            )
            logger.info(
                f"Face Landmarker 로드 완료 (mode: VIDEO, conf: {face_cfg.get('min_detection_confidence')})"
            )

        except Exception as e:
            logger.warning(f"Face Landmarker 로드 실패: {e}. 대체 모델 사용...")
            self.face_landmarker = None

        try:
            # Hand Landmarker 로드
            HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions

            options = HandLandmarkerOptions(
                base_options=BaseOptions(
                    model_asset_path=str(model_dir / "hand_landmarker.task")
                ),
                running_mode=VisionRunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=hand_cfg.get(
                    "min_detection_confidence", 0.5
                ),
                min_hand_presence_confidence=hand_cfg.get(
                    "min_presence_confidence", 0.5
                ),
                min_tracking_confidence=hand_cfg.get("min_tracking_confidence", 0.5),
            )
            self.hand_landmarker = mp.tasks.vision.HandLandmarker.create_from_options(
                options
            )
            logger.info(
                f"Hand Landmarker 로드 완료 (mode: VIDEO, conf: {hand_cfg.get('min_detection_confidence')})"
            )

        except Exception as e:
            logger.warning(f"Hand Landmarker 로드 실패: {e}. 대체 모델 사용...")
            self.hand_landmarker = None

    def _extract_landmark_list(self, obj, candidate_attrs: tuple[str, ...]):
        """MediaPipe 결과 객체에서 랜드마크 리스트를 공통 방식으로 추출한다."""
        for attr in candidate_attrs:
            val = getattr(obj, attr, None)
            if val:
                try:
                    if hasattr(val, "landmark"):
                        inner = getattr(val, "landmark")
                        if inner:
                            return inner
                except Exception:
                    pass
                return val
        return None

    def _build_landmark_data(self, landmarks, timestamp_ms: int) -> LandmarkData:
        """랜드마크 객체 목록을 LandmarkData로 변환한다."""
        coords = []
        confidences = []
        for lm in landmarks:
            x = getattr(lm, "x", getattr(lm, "position_x", None))
            y = getattr(lm, "y", getattr(lm, "position_y", None))
            z = getattr(lm, "z", getattr(lm, "position_z", 0.0))
            if x is None or y is None:
                continue
            coords.append((x, y, z))
            p = getattr(lm, "presence", None)
            if p is None:
                p = getattr(lm, "visibility", None)
            try:
                confidences.append(float(p) if p is not None else 1.0)
            except Exception:
                confidences.append(1.0)

        return LandmarkData(
            landmarks=[(c[0], c[1], c[2]) for c in coords],
            confidences=confidences,
            timestamp_ms=timestamp_ms,
        )

    def _get_pixel_point(
        self, landmark, confidence: float, frame_width: int, frame_height: int
    ):
        """정규화 좌표를 픽셀 좌표로 변환한다."""
        x = int(min(max(landmark[0] * frame_width, 0), frame_width - 1))
        y = int(min(max(landmark[1] * frame_height, 0), frame_height - 1))
        return (x, y, confidence)

    def _map_hand_landmarks(
        self,
        extracted,
        landmarks,
        frame_width: int,
        frame_height: int,
        confidence_threshold: float,
    ):
        """손 랜드마크를 handedness 기준으로 left/right에 채운다."""
        if extracted.hands is None:
            return

        for hand_idx, hand_data in enumerate(extracted.hands):
            if not hand_data.landmarks:
                continue

            finger_tips = []
            for tip_idx in [4, 8, 12, 16, 20]:
                if (
                    len(hand_data.landmarks) > tip_idx
                    and hand_data.confidences[tip_idx] > confidence_threshold
                ):
                    finger_point = self._get_pixel_point(
                        hand_data.landmarks[tip_idx],
                        hand_data.confidences[tip_idx],
                        frame_width,
                        frame_height,
                    )
                    finger_tips.append(
                        (
                            finger_point[0],
                            finger_point[1],
                            hand_data.landmarks[tip_idx][2],
                        )
                    )

            if hand_idx == 0:
                landmarks["right_hand_tips"] = finger_tips
            else:
                landmarks["left_hand_tips"] = finger_tips

    def extract_landmarks(self, frame: np.ndarray) -> ExtractedLandmarks:
        """
        웹캠 프레임에서 랜드마크 추출

        Args:
            frame: OpenCV 프레임 (BGR)

        Returns:
            추출된 랜드마크
        """
        if frame is None or frame.size == 0:
            logger.warning("유효하지 않은 프레임")
            return ExtractedLandmarks(None, None, None, 0)

        # BGR → RGB 변환
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # VIDEO 모드에서는 명시적인 타임스탬프가 필요함
        timestamp_ms = int(time.time() * 1000)

        pose_data = None
        face_data = None
        hands_data = None

        # Pose 추출
        if self.pose_landmarker is not None:
            try:
                pose_result = self.pose_landmarker.detect_for_video(
                    mp_image, timestamp_ms
                )
                pose_list = self._extract_landmark_list(
                    pose_result,
                    (
                        "landmarks",
                        "pose_landmarks",
                        "keypoints",
                        "world_landmarks",
                        "landmark",
                    ),
                )
                if pose_list:
                    landmarks = (
                        pose_list[0]
                        if isinstance(pose_list, list) and len(pose_list) > 0
                        else pose_list
                    )
                    pose_data = self._build_landmark_data(landmarks, timestamp_ms)
            except Exception as e:
                logger.debug(f"Pose 추출 실패: {e}")

        # Face 추출
        if self.face_landmarker is not None:
            try:
                face_result = self.face_landmarker.detect_for_video(
                    mp_image, timestamp_ms
                )
                face_list = self._extract_landmark_list(
                    face_result,
                    (
                        "landmarks",
                        "face_landmarks",
                        "keypoints",
                        "landmark",
                    ),
                )
                if face_list:
                    landmarks = (
                        face_list[0]
                        if isinstance(face_list, list) and len(face_list) > 0
                        else face_list
                    )
                    face_data = self._build_landmark_data(landmarks, timestamp_ms)
            except Exception as e:
                logger.debug(f"Face 추출 실패: {e}")

        # Hand 추출
        if self.hand_landmarker is not None:
            try:
                hand_result = self.hand_landmarker.detect_for_video(
                    mp_image, timestamp_ms
                )
                hand_list = self._extract_landmark_list(
                    hand_result,
                    (
                        "landmarks",
                        "hand_landmarks",
                        "keypoints",
                        "landmark",
                    ),
                )
                if hand_list:
                    hands_data = []
                    iterable = hand_list if isinstance(hand_list, list) else [hand_list]
                    for hand_idx, landmarks in enumerate(iterable):
                        hand_data = self._build_landmark_data(landmarks, timestamp_ms)
                        hands_data.append(hand_data)
            except Exception as e:
                logger.debug(f"Hand 추출 실패: {e}")

        return ExtractedLandmarks(pose_data, face_data, hands_data, timestamp_ms)

    def get_relevant_landmarks(
        self,
        extracted: ExtractedLandmarks,
        frame_width: int,
        frame_height: int,
        confidence_threshold: float = 0.5,
    ) -> Dict[str, any]:
        """
        자세 판정에 필요한 랜드마크만 추출

        Args:
            extracted: 추출된 랜드마크
            frame_width: 프레임 너비
            frame_height: 프레임 높이
            confidence_threshold: 신뢰도 임계값

        Returns:
            관련 랜드마크 딕셔너리
        """
        landmarks = {
            "face_center": None,
            "left_eye": None,
            "right_eye": None,
            "left_cheek": None,
            "right_cheek": None,
            "chin_points": [],
            "left_shoulder": None,
            "right_shoulder": None,
            "left_hand_tips": [],
            "right_hand_tips": [],
            "confidences": {},
        }

        # Face 랜드마크
        if extracted.face is not None and extracted.face.landmarks:
            face_lms = extracted.face.landmarks
            face_conf = extracted.face.confidences

            def _get_face_point(index: int, name: str):
                """Face landmark index를 픽셀 좌표로 변환"""
                if len(face_lms) > index and len(face_conf) > index:
                    if face_conf[index] > confidence_threshold:
                        point = self._get_pixel_point(
                            face_lms[index],
                            face_conf[index],
                            frame_width,
                            frame_height,
                        )
                        landmarks["confidences"][name] = face_conf[index]
                        return (point[0], point[1])
                return None

            def _assign_pair_by_x(left_key: str, right_key: str, point_a, point_b):
                """화면 x좌표 기준으로 왼쪽/오른쪽 포인트를 정렬해서 저장"""
                if point_a is None or point_b is None:
                    return

                if point_a[0] <= point_b[0]:
                    landmarks[left_key] = point_a
                    landmarks[right_key] = point_b
                else:
                    landmarks[left_key] = point_b
                    landmarks[right_key] = point_a

            # 대표 얼굴 포인트
            # 1: 코 끝에 가까운 face mesh point
            nose_point = _get_face_point(1, "face_center")
            if nose_point is not None:
                landmarks["face_center"] = nose_point

            # 눈: 화면 기준 좌/우 눈 외곽 포인트
            # 33, 263은 양쪽 눈 외곽 기준점으로 쓰기 좋음
            eye_a = _get_face_point(33, "eye_a")
            eye_b = _get_face_point(263, "eye_b")
            _assign_pair_by_x("left_eye", "right_eye", eye_a, eye_b)

            # 광대/볼: 화면 기준 좌/우 얼굴 외곽 쪽 포인트
            # 234, 454는 cheek/face side 기준점으로 쓰기 좋음
            cheek_a = _get_face_point(234, "cheek_a")
            cheek_b = _get_face_point(454, "cheek_b")
            _assign_pair_by_x("left_cheek", "right_cheek", cheek_a, cheek_b)

            # 입꼬리: 시각화 및 추후 턱 괸 자세 보조용
            mouth_a = _get_face_point(61, "mouth_a")
            mouth_b = _get_face_point(291, "mouth_b")
            _assign_pair_by_x("left_mouth", "right_mouth", mouth_a, mouth_b)

            # 턱 포인트
            # 152는 턱 아래쪽 대표 포인트
            chin_point = _get_face_point(152, "chin")
            if chin_point is not None:
                landmarks["chin_points"].append(chin_point)

        # 디버그: 필수 face 포인트 신뢰도 로깅(존재하지 않거나 낮으면 원인 파악에 도움됨)
        try:
            if extracted.face is not None:
                fc = extracted.face.confidences
                vals = {
                    "face_30": float(fc[30]) if len(fc) > 30 else None,
                    "face_1": float(fc[1]) if len(fc) > 1 else None,
                    "face_4": float(fc[4]) if len(fc) > 4 else None,
                    "face_152": float(fc[152]) if len(fc) > 152 else None,
                    "face_378": float(fc[378]) if len(fc) > 378 else None,
                }
                logger.debug(f"Face landmark confidences: {vals}")
        except Exception:
            logger.debug("Face confidences 로깅 중 예외")

        # Pose 랜드마크 (어깨)
        if extracted.pose is not None and extracted.pose.landmarks:
            pose_lms = extracted.pose.landmarks
            pose_conf = extracted.pose.confidences

            # 왼쪽 어깨 (11), 오른쪽 어깨 (12)
            if len(pose_lms) > 11 and pose_conf[11] > confidence_threshold:
                left_shoulder = self._get_pixel_point(
                    pose_lms[11], pose_conf[11], frame_width, frame_height
                )
                landmarks["left_shoulder"] = (left_shoulder[0], left_shoulder[1])
                landmarks["confidences"]["left_shoulder"] = left_shoulder[2]

            if len(pose_lms) > 12 and pose_conf[12] > confidence_threshold:
                right_shoulder = self._get_pixel_point(
                    pose_lms[12], pose_conf[12], frame_width, frame_height
                )
                landmarks["right_shoulder"] = (right_shoulder[0], right_shoulder[1])
                landmarks["confidences"]["right_shoulder"] = right_shoulder[2]

        # 어깨 좌표가 이미지 좌표계상 좌/우가 반전되어 들어오는 경우 교정
        try:
            ls = landmarks.get("left_shoulder")
            rs = landmarks.get("right_shoulder")
            if ls is not None and rs is not None:
                # 픽셀 x 좌표를 비교해서 왼쪽이 더 큰 경우(반전) swap
                if ls[0] > rs[0]:
                    logger.debug(
                        f"어깨 좌표 좌우 반전 감지: left_shoulder.x={ls[0]} > right_shoulder.x={rs[0]}; 스왑 수행"
                    )
                    landmarks["left_shoulder"], landmarks["right_shoulder"] = rs, ls
                    # confidences도 교체
                    lc = landmarks["confidences"].get("left_shoulder")
                    rc = landmarks["confidences"].get("right_shoulder")
                    landmarks["confidences"]["left_shoulder"] = rc
                    landmarks["confidences"]["right_shoulder"] = lc
        except Exception:
            logger.debug("어깨 좌표 교정 중 예외 발생")

        # 디버그: pose(어깨) 신뢰도 로깅
        try:
            if extracted.pose is not None:
                pc = extracted.pose.confidences
                pvals = {
                    "pose_11": float(pc[11]) if len(pc) > 11 else None,
                    "pose_12": float(pc[12]) if len(pc) > 12 else None,
                }
                logger.debug(f"Pose landmark confidences: {pvals}")
        except Exception:
            logger.debug("Pose confidences 로깅 중 예외")

        # Hand 랜드마크 (손가락 팁)
        self._map_hand_landmarks(
            extracted, landmarks, frame_width, frame_height, confidence_threshold
        )

        return landmarks

    def normalize_landmarks(
        self,
        landmarks: Dict[str, any],
        frame_width: int,
        frame_height: int,
        timestamp_ms: Optional[int] = None,
        low_latency: bool = False,
    ) -> Dict[str, any]:
        """
        랜드마크를 정규화된 좌표로 변환 (0~1 범위)

        Args:
            landmarks: 랜드마크 딕셔너리 (픽셀 좌표)
            frame_width: 프레임 너비
            frame_height: 프레임 높이
            timestamp_ms: 프레임 타임스탬프 (OneEuro 필터용)
            low_latency: True이면 필터 지연을 최소화 (Baseline 수집용)

        Returns:
            정규화된 랜드마크
        """
        normalized = {}

        for key, value in landmarks.items():
            if value is None:
                normalized[key] = None
            elif key == "confidences":
                normalized[key] = value
            elif isinstance(value, list):
                # 손가락 팁은 3D 유지, chin_points는 2D로 변환
                if key in ["left_hand_tips", "right_hand_tips"]:
                    normalized[key] = [
                        (
                            (
                                p[0] / frame_width,
                                p[1] / frame_height,
                                p[2] if len(p) > 2 else 0,
                            )
                            if len(p) >= 2
                            else p
                        )
                        for p in value
                    ]
                else:
                    # chin_points는 2D 유지 (x, y)만
                    normalized[key] = [
                        (
                            (
                                p[0] / frame_width,
                                p[1] / frame_height,
                            )
                            if len(p) >= 2
                            else p
                        )
                        for p in value
                    ]
            elif isinstance(value, tuple):
                # 일반 포인트
                normalized[key] = (value[0] / frame_width, value[1] / frame_height)
            else:
                normalized[key] = value

        # One Euro Filter 및 EMA Filter 적용 (주요 2D 좌표들)
        # 사용자의 요청에 따라 뺨(cheek)과 어깨(shoulder)의 안정성에 집중한다.
        filter_keys = [
            "face_center",
            "left_eye",
            "right_eye",
            "left_cheek",
            "right_cheek",
            "left_shoulder",
            "right_shoulder",
        ]

        if self.one_euro_filter is None or not hasattr(self, "ema_filters_x"):
            # key별로 독립적인 필터 인스턴스를 관리한다.
            # 1. One Euro Filter: 잔떨림 억제를 위해 min_cutoff를 더 낮춤 (0.01)
            self.one_euro_filters: Dict[str, OneEuroFilter] = {
                key: OneEuroFilter(min_cutoff=0.01, beta=0.005) for key in filter_keys
            }
            # 2. EMA Filter: 프로토타입과 동일한 alpha=0.15 적용
            from src.utils.helpers import EMAFilter

            self.ema_filters_x = {k: EMAFilter(alpha=0.15) for k in filter_keys}
            self.ema_filters_y = {k: EMAFilter(alpha=0.15) for k in filter_keys}
            self.one_euro_filter = True  # 초기화 완료 플래그

        # 타임스탬프 처리 (ms -> s)
        t_sec = (timestamp_ms / 1000.0) if timestamp_ms is not None else time.time()

        # 필터 계수 조정 (low_latency 모드)
        current_min_cutoff = 0.5 if low_latency else 0.01
        current_beta = 0.01 if low_latency else 0.005
        current_alpha = 0.5 if low_latency else 0.15

        for key in filter_keys:
            val = normalized.get(key)
            if val is not None:
                # 필터 계수 동적 업데이트
                filter_obj = self.one_euro_filters[key]
                filter_obj.min_cutoff = current_min_cutoff
                filter_obj.beta = current_beta

                self.ema_filters_x[key].alpha = current_alpha
                self.ema_filters_y[key].alpha = current_alpha

                # 1. One Euro Filter 적용 (좌표 벡터)
                one_euro_filtered = filter_obj.process(t_sec, np.array(val))

                # 2. EMA Filter 적용 (X, Y 각각)
                fx = self.ema_filters_x[key].process(one_euro_filtered[0])
                fy = self.ema_filters_y[key].process(one_euro_filtered[1])

                normalized[key] = (float(fx), float(fy))

        return normalized


def create_landmark_extractor(
    model_base_path: str = "assets/models",
) -> LandmarkExtractor:
    """랜드마크 추출기 생성 (팩토리 함수)"""
    return LandmarkExtractor(model_base_path)
