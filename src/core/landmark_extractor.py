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

        self._initialize_models()
        logger.info("LandmarkExtractor 초기화 완료")

    def _initialize_models(self):
        """MediaPipe 모델 로드"""
        model_dir = Path(self.model_base_path)

        try:
            # Pose Landmarker 로드
            BaseOptions = mp.tasks.BaseOptions
            PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
            VisionRunningMode = mp.tasks.vision.RunningMode

            options = PoseLandmarkerOptions(
                base_options=BaseOptions(
                    model_asset_path=str(model_dir / "pose_landmarker.task")
                ),
                running_mode=VisionRunningMode.IMAGE,
                num_poses=1,
            )
            self.pose_landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(
                options
            )
            logger.info("Pose Landmarker 로드 완료")

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
                running_mode=VisionRunningMode.IMAGE,
                num_faces=1,
            )
            self.face_landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(
                options
            )
            logger.info("Face Landmarker 로드 완료")

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
                running_mode=VisionRunningMode.IMAGE,
                num_hands=2,
            )
            self.hand_landmarker = mp.tasks.vision.HandLandmarker.create_from_options(
                options
            )
            logger.info("Hand Landmarker 로드 완료")

        except Exception as e:
            logger.warning(f"Hand Landmarker 로드 실패: {e}. 대체 모델 사용...")
            self.hand_landmarker = None

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

        # mp.Image may not provide timestamp_ms in some MediaPipe builds; fall back to current time
        try:
            timestamp_ms = int(mp_image.timestamp_ms)
        except Exception:
            timestamp_ms = int(time.time() * 1000)
        pose_data = None
        face_data = None
        hands_data = None

        # Pose 추출
        if self.pose_landmarker is not None:
            try:
                pose_result = self.pose_landmarker.detect(mp_image)
                try:
                    logger.debug(
                        f"pose_result type={type(pose_result)} attrs={dir(pose_result)}"
                    )
                except Exception:
                    logger.debug(f"pose_result repr: {repr(pose_result)}")

                def _extract_list(obj):
                    # try common attribute names that may contain landmark lists
                    for attr in (
                        "landmarks",
                        "pose_landmarks",
                        "keypoints",
                        "world_landmarks",
                        "landmark",
                    ):
                        val = getattr(obj, attr, None)
                        if val:
                            # If the returned object wraps landmarks under 'landmark', unwrap it
                            try:
                                if hasattr(val, "landmark"):
                                    inner = getattr(val, "landmark")
                                    if inner:
                                        return inner
                            except Exception:
                                pass
                            return val
                    return None

                pose_list = _extract_list(pose_result)
                if pose_list:
                    landmarks = (
                        pose_list[0]
                        if isinstance(pose_list, list) and len(pose_list) > 0
                        else pose_list
                    )
                    # build coords and confidences with fallbacks
                    coords = []
                    confs = []
                    for lm in landmarks:
                        x = getattr(lm, "x", getattr(lm, "position_x", None))
                        y = getattr(lm, "y", getattr(lm, "position_y", None))
                        z = getattr(lm, "z", getattr(lm, "position_z", 0.0))
                        # 안전하게 None 처리
                        if x is None or y is None:
                            continue
                        coords.append((x, y, z))
                        p = getattr(lm, "presence", None)
                        if p is None:
                            p = getattr(lm, "visibility", None)
                        try:
                            confs.append(float(p) if p is not None else 1.0)
                        except Exception:
                            confs.append(1.0)

                    pose_data = LandmarkData(
                        landmarks=[(c[0], c[1], c[2]) for c in coords],
                        confidences=confs,
                        timestamp_ms=timestamp_ms,
                    )
                else:
                    logger.debug(
                        f"Pose 결과에 랜드마크 속성이 없습니다: attrs={dir(pose_result)}"
                    )
            except Exception as e:
                logger.debug(f"Pose 추출 실패: {e}")

        # Face 추출
        if self.face_landmarker is not None:
            try:
                face_result = self.face_landmarker.detect(mp_image)
                try:
                    logger.debug(
                        f"face_result type={type(face_result)} attrs={dir(face_result)}"
                    )
                except Exception:
                    logger.debug(f"face_result repr: {repr(face_result)}")

                def _extract_list(obj):
                    for attr in (
                        "landmarks",
                        "face_landmarks",
                        "keypoints",
                        "landmark",
                    ):
                        val = getattr(obj, attr, None)
                        if val:
                            # If the returned object wraps landmarks under 'landmark', unwrap it
                            try:
                                if hasattr(val, "landmark"):
                                    inner = getattr(val, "landmark")
                                    if inner:
                                        return inner
                            except Exception:
                                pass
                            return val
                    return None

                face_list = _extract_list(face_result)
                if face_list:
                    landmarks = (
                        face_list[0]
                        if isinstance(face_list, list) and len(face_list) > 0
                        else face_list
                    )
                    coords = []
                    confs = []
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
                            confs.append(float(p) if p is not None else 1.0)
                        except Exception:
                            confs.append(1.0)

                    face_data = LandmarkData(
                        landmarks=[(c[0], c[1], c[2]) for c in coords],
                        confidences=confs,
                        timestamp_ms=timestamp_ms,
                    )
                else:
                    logger.debug(
                        f"Face 결과에 랜드마크 속성이 없습니다: attrs={dir(face_result)}"
                    )
            except Exception as e:
                logger.debug(f"Face 추출 실패: {e}")

        # Hand 추출
        if self.hand_landmarker is not None:
            try:
                hand_result = self.hand_landmarker.detect(mp_image)
                try:
                    logger.debug(
                        f"hand_result type={type(hand_result)} attrs={dir(hand_result)}"
                    )
                except Exception:
                    logger.debug(f"hand_result repr: {repr(hand_result)}")

                def _extract_list(obj):
                    for attr in (
                        "landmarks",
                        "hand_landmarks",
                        "keypoints",
                        "landmark",
                    ):
                        val = getattr(obj, attr, None)
                        if val:
                            # If the returned object wraps landmarks under 'landmark', unwrap it
                            try:
                                if hasattr(val, "landmark"):
                                    inner = getattr(val, "landmark")
                                    if inner:
                                        return inner
                            except Exception:
                                pass
                            return val
                    return None

                hand_list = _extract_list(hand_result)
                if hand_list:
                    hands_data = []
                    iterable = hand_list if isinstance(hand_list, list) else [hand_list]
                    for hand_idx, landmarks in enumerate(iterable):
                        coords = []
                        confs = []
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
                                confs.append(float(p) if p is not None else 1.0)
                            except Exception:
                                confs.append(1.0)

                        hand_data = LandmarkData(
                            landmarks=[(c[0], c[1], c[2]) for c in coords],
                            confidences=confs,
                            timestamp_ms=timestamp_ms,
                        )
                        hands_data.append(hand_data)
                else:
                    logger.debug(
                        f"Hand 결과에 랜드마크 속성이 없습니다: attrs={dir(hand_result)}"
                    )
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

            # 코 (30), 양쪽 눈 (1,4), 양쪽 광대 (152,378), 턱 (199,427)
            if len(face_lms) > 30 and face_conf[30] > confidence_threshold:
                landmarks["face_center"] = (
                    int(face_lms[30][0] * frame_width),
                    int(face_lms[30][1] * frame_height),
                )

            if len(face_lms) > 1 and face_conf[1] > confidence_threshold:
                landmarks["left_eye"] = (
                    int(face_lms[1][0] * frame_width),
                    int(face_lms[1][1] * frame_height),
                )

            if len(face_lms) > 4 and face_conf[4] > confidence_threshold:
                landmarks["right_eye"] = (
                    int(face_lms[4][0] * frame_width),
                    int(face_lms[4][1] * frame_height),
                )

            if len(face_lms) > 152 and face_conf[152] > confidence_threshold:
                landmarks["left_cheek"] = (
                    int(face_lms[152][0] * frame_width),
                    int(face_lms[152][1] * frame_height),
                )
                landmarks["confidences"]["left_cheek"] = face_conf[152]

            if len(face_lms) > 378 and face_conf[378] > confidence_threshold:
                landmarks["right_cheek"] = (
                    int(face_lms[378][0] * frame_width),
                    int(face_lms[378][1] * frame_height),
                )
                landmarks["confidences"]["right_cheek"] = face_conf[378]

            # 턱 포인트 (199, 427)
            chin_indices = [199, 427]
            for idx in chin_indices:
                if len(face_lms) > idx and face_conf[idx] > confidence_threshold:
                    landmarks["chin_points"].append(
                        (
                            int(face_lms[idx][0] * frame_width),
                            int(face_lms[idx][1] * frame_height),
                        )
                    )

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
                landmarks["left_shoulder"] = (
                    int(pose_lms[11][0] * frame_width),
                    int(pose_lms[11][1] * frame_height),
                )
                landmarks["confidences"]["left_shoulder"] = pose_conf[11]

            if len(pose_lms) > 12 and pose_conf[12] > confidence_threshold:
                landmarks["right_shoulder"] = (
                    int(pose_lms[12][0] * frame_width),
                    int(pose_lms[12][1] * frame_height),
                )
                landmarks["confidences"]["right_shoulder"] = pose_conf[12]

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
        if extracted.hands is not None:
            for hand_idx, hand_data in enumerate(extracted.hands):
                if hand_data.landmarks:
                    # 손가락 팁 인덱스: 4, 8, 12, 16, 20
                    finger_tips = []
                    for tip_idx in [4, 8, 12, 16, 20]:
                        if (
                            len(hand_data.landmarks) > tip_idx
                            and hand_data.confidences[tip_idx] > confidence_threshold
                        ):
                            finger_tips.append(
                                (
                                    int(hand_data.landmarks[tip_idx][0] * frame_width),
                                    int(hand_data.landmarks[tip_idx][1] * frame_height),
                                    hand_data.landmarks[tip_idx][2],  # z 포함
                                )
                            )

                    # Handedness 확인 (Right=0, Left=1)
                    if hand_idx == 0:
                        landmarks["right_hand_tips"] = finger_tips
                    else:
                        landmarks["left_hand_tips"] = finger_tips

        return landmarks

    def normalize_landmarks(
        self, landmarks: Dict[str, any], frame_width: int, frame_height: int
    ) -> Dict[str, any]:
        """
        랜드마크를 정규화된 좌표로 변환 (0~1 범위)

        Args:
            landmarks: 랜드마크 딕셔너리 (픽셀 좌표)
            frame_width: 프레임 너비
            frame_height: 프레임 높이

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
                # chin_points, *_hand_tips 등
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
            elif isinstance(value, tuple):
                # 일반 포인트
                normalized[key] = (value[0] / frame_width, value[1] / frame_height)
            else:
                normalized[key] = value

        return normalized


def create_landmark_extractor(
    model_base_path: str = "assets/models",
) -> LandmarkExtractor:
    """랜드마크 추출기 생성 (팩토리 함수)"""
    return LandmarkExtractor(model_base_path)
