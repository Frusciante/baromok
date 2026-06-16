"""
랜드마크 추출기

MediaPipe를 사용하여 웹캠 프레임에서 얼굴, 어깨, 손 랜드마크 추출
"""

import mediapipe as mp
import numpy as np
import cv2
import time
from src.utils.helpers import OneEuroFilter
from typing import Dict, Tuple, Optional, List
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from src.utils.logger import get_logger
from src.config import get_config
from src.utils.paths import MODELS_DIR

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

    def __init__(self, model_base_path: str = str(MODELS_DIR)):
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
        # ghosting: sliding window (ms) for retaining recent landmark values
        self._ghost_window_ms = 1000  # 1 second
        self._ghost_windows: Dict[str, deque] = {}
        # OneEuro filters for representative scalar points (applied between representative values)
        self._one_euro_filters: Dict[str, OneEuroFilter] = {}

        # 설정 로드
        self.config = get_config()
        self.mp_config = self.config.get_mediapipe_config()
        # 필터 설정 로드 (posture_definition_criteria.json의 filters)
        try:
            self._filters_config = self.config.get_filters_config()
        except Exception:
            # 호환성: fallback to raw posture criteria
            self._filters_config = self.config.get_posture_criteria().get("filters", {})

        one_euro_cfg = self._filters_config.get("one_euro", {}) if self._filters_config else {}
        self._one_euro_min_cutoff = float(one_euro_cfg.get("min_cutoff", 0.05))
        self._one_euro_beta = float(one_euro_cfg.get("beta", 0.005))
        self._one_euro_d_cutoff = float(one_euro_cfg.get("d_cutoff", 1.0))

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
            # x/y 접근 — 속성 존재 여부를 한 번만 확인
            x = lm.x if hasattr(lm, "x") else getattr(lm, "position_x", None)
            y = lm.y if hasattr(lm, "y") else getattr(lm, "position_y", None)
            if x is None or y is None:
                continue
            z = lm.z if hasattr(lm, "z") else getattr(lm, "position_z", 0.0)
            coords.append((x, y, z))
            # presence > visibility 순으로 신뢰도 추출
            p = getattr(lm, "presence", None) or getattr(lm, "visibility", None)
            confidences.append(float(p) if p is not None else 1.0)

        return LandmarkData(
            landmarks=coords,
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
                    logger.debug(f"Detected face landmarks count: {len(landmarks)}")
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

            # 홍채(Iris) 추출: MediaPipe FaceMesh 468~477 인덱스
            left_iris_diam_px = None
            right_iris_diam_px = None
            try:
                n_face = len(face_lms)
                # 유효한 iris 포인트만 픽셀 좌표로 모으기
                iris_px = []
                for idx in range(468, min(478, n_face)):
                    if face_conf[idx] > confidence_threshold:
                        lm = face_lms[idx]
                        iris_px.append((
                            int(lm[0] * frame_width),
                            int(lm[1] * frame_height),
                        ))

                if len(iris_px) >= 3:
                    arr = np.array(iris_px, dtype=np.float32)
                    # 좌/우 분할 기준 x
                    mid_x = (landmarks['left_eye'][0] + landmarks['right_eye'][0]) / 2.0 \
                        if landmarks.get('left_eye') and landmarks.get('right_eye') \
                        else float(np.median(arr[:, 0]))

                    mask_l = arr[:, 0] <= mid_x
                    for mask, attr in ((mask_l, "left"), (~mask_l, "right")):
                        pts = arr[mask]
                        if len(pts) >= 3:
                            cen = pts.mean(axis=0)
                            diam = 2.0 * float(np.mean(np.linalg.norm(pts - cen, axis=1)))
                            if attr == "left":
                                left_iris_diam_px = diam
                            else:
                                right_iris_diam_px = diam
            except Exception:
                pass

            landmarks['left_iris_diameter_px'] = left_iris_diam_px
            landmarks['right_iris_diameter_px'] = right_iris_diam_px

            # 홍채 중심: 468(왼쪽), 473(오른쪽)
            left_iris_center = _get_face_point(468, "left_iris_center")
            right_iris_center = _get_face_point(473, "right_iris_center")
            landmarks['left_iris_center'] = left_iris_center
            landmarks['right_iris_center'] = right_iris_center

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

        # Pose 랜드마크 (어깨) - 신뢰도 및 해부학적 가드 강화
        if extracted.pose is not None and extracted.pose.landmarks:
            pose_lms = extracted.pose.landmarks
            pose_conf = extracted.pose.confidences

            # v1.1: 신뢰도 임계값 유지 (0.8)
            shoulder_confidence_threshold = 0.8
            
            l_sh_ok = len(pose_lms) > 11 and pose_conf[11] > shoulder_confidence_threshold
            r_sh_ok = len(pose_lms) > 12 and pose_conf[12] > shoulder_confidence_threshold
            
            if l_sh_ok and r_sh_ok:
                l_y = pose_lms[11][1]
                r_y = pose_lms[12][1]
                
                # 턱 Y 좌표 추출 (정규화)
                chin_y = landmarks["chin_points"][0][1] / frame_height if landmarks.get("chin_points") else None
                
                # 설정에서 가드 임계값 로드
                sg_cfg = self.config.get_posture_criteria().get("shoulder_guard", {})
                sh_bottom_th = sg_cfg.get("shoulder_bottom_threshold", 0.98)
                chin_low_th = sg_cfg.get("chin_low_threshold", 0.75)
                sh_top_th = sg_cfg.get("shoulder_top_threshold", 0.01)
                
                # 새로운 가드 로직 (사용자 제안): 어깨가 바닥에 붙어있으면서 턱 위치가 낮을 때 (AND 조건)
                is_invalid = False
                
                # 1. 하단 절단 감지: 어깨가 화면 하단 끝에 걸림 AND 턱이 화면 하단부에 위치
                is_bottom_cut_off = False
                if chin_y is not None:
                    shoulder_at_bottom = l_y > sh_bottom_th or r_y > sh_bottom_th
                    chin_is_low = chin_y > chin_low_th
                    if shoulder_at_bottom and chin_is_low:
                        is_bottom_cut_off = True
                
                # 2. 상단 튀는 현상 방지 (추측 오류)
                is_on_top = l_y < sh_top_th or r_y < sh_top_th
                
                if is_bottom_cut_off or is_on_top:
                    is_invalid = True
                    logger.debug(f"어깨 가드 발동: bottom_cut={is_bottom_cut_off}, top={is_on_top} (sh_y={max(l_y, r_y):.3f}, chin_y={chin_y})")

                if not is_invalid:
                    left_shoulder = self._get_pixel_point(
                        pose_lms[11], pose_conf[11], frame_width, frame_height
                    )
                    landmarks["left_shoulder"] = (left_shoulder[0], left_shoulder[1])
                    landmarks["confidences"]["left_shoulder"] = pose_conf[11]

                    right_shoulder = self._get_pixel_point(
                        pose_lms[12], pose_conf[12], frame_width, frame_height
                    )
                    landmarks["right_shoulder"] = (right_shoulder[0], right_shoulder[1])
                    landmarks["confidences"]["right_shoulder"] = pose_conf[12]
                else:
                    landmarks["left_shoulder"] = None
                    landmarks["right_shoulder"] = None
            else:
                landmarks["left_shoulder"] = None
                landmarks["right_shoulder"] = None

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
        baseline_mode: bool = False,
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

        # Keys we keep ghosted (including lists)
        _VECTOR_KEYS = (
            "face_center", "left_eye", "right_eye",
            "left_cheek", "right_cheek", "left_shoulder", "right_shoulder",
        )
        _LIST_KEYS = (
            "chin_points", "left_hand_tips", "right_hand_tips",
            "left_iris_center", "right_iris_center",
        )
        _SCALAR_KEYS = ("left_iris_diameter_px", "right_iris_diameter_px")
        ghost_keys = _VECTOR_KEYS + _LIST_KEYS + _SCALAR_KEYS

        # Lazy init deques for each ghost key
        if not self._ghost_windows:
            self._ghost_windows = {k: deque() for k in ghost_keys}

        # timestamp for this frame (ms) — compute once
        ts = int(timestamp_ms) if timestamp_ms is not None else int(time.time() * 1000)
        cutoff = ts - int(self._ghost_window_ms)
        t_sec = ts * 0.001

        # --- Ghost window update (avoid deepcopy for simple tuples/scalars) ---
        for k in ghost_keys:
            val = normalized.get(k)
            # determine if present
            present = val is not None and (not isinstance(val, list) or len(val) > 0)
            if present:
                if isinstance(val, tuple):
                    stored = (float(val[0]), float(val[1]))
                elif isinstance(val, list):
                    stored = list(val)          # shallow copy sufficient for tuples inside
                else:
                    stored = val                # scalar — immutable
                dq = self._ghost_windows.setdefault(k, deque())
                dq.append((ts, stored))
            else:
                dq = self._ghost_windows.setdefault(k, deque())

            # prune old entries
            while dq and dq[0][0] < cutoff:
                dq.popleft()

        # --- Build representative values (most recent in window) ---
        rep_values: Dict[str, any] = {}
        for k in ghost_keys:
            val = normalized.get(k)
            present = val is not None and (not isinstance(val, list) or len(val) > 0)
            if present:
                rep_values[k] = val             # use current frame value directly
            else:
                dq = self._ghost_windows.get(k)
                rep_values[k] = dq[-1][1] if dq else None

        # --- Shoulder selection: O(n) instead of O(n²) ---
        # Pick the leftmost candidate for left_shoulder and rightmost for right_shoulder
        l_dq = self._ghost_windows.get("left_shoulder")
        r_dq = self._ghost_windows.get("right_shoulder")
        if l_dq and r_dq:
            # best left_shoulder = smallest x (leftmost on screen)
            best_l = min((e[1] for e in l_dq if e[1] is not None), key=lambda p: p[0], default=None)
            # best right_shoulder = largest x (rightmost on screen)
            best_r = max((e[1] for e in r_dq if e[1] is not None), key=lambda p: p[0], default=None)
            if best_l is not None and best_r is not None and best_r[0] > best_l[0]:
                rep_values["left_shoulder"] = (float(best_l[0]), float(best_l[1]))
                rep_values["right_shoulder"] = (float(best_r[0]), float(best_r[1]))

        # --- Apply OneEuro / pass-through per key type ---
        for k in ghost_keys:
            # store raw per-frame value
            normalized[f"{k}_raw"] = normalized.get(k)

            rep = rep_values.get(k)

            if baseline_mode:
                # baseline 모드: 필터 없이 ghost 값만 사용
                if k in _VECTOR_KEYS:
                    normalized[k] = (float(rep[0]), float(rep[1])) if rep is not None else None
                elif k in _SCALAR_KEYS:
                    normalized[k] = float(rep) if rep is not None else None
                else:
                    normalized[k] = rep if rep is not None else []
                continue

            if k in _VECTOR_KEYS:
                if rep is None:
                    normalized[k] = None
                else:
                    if k not in self._one_euro_filters:
                        self._one_euro_filters[k] = OneEuroFilter(
                            min_cutoff=self._one_euro_min_cutoff,
                            beta=self._one_euro_beta,
                            d_cutoff=self._one_euro_d_cutoff,
                        )
                    try:
                        vec = np.array((float(rep[0]), float(rep[1])), dtype=np.float64)
                        filtered = self._one_euro_filters[k].process(t_sec, vec)
                        normalized[k] = (float(filtered[0]), float(filtered[1]))
                    except Exception:
                        normalized[k] = (float(rep[0]), float(rep[1]))
            else:
                # lists and scalars: pass through representative value
                normalized[k] = rep if rep is not None else ([] if k in _LIST_KEYS else None)

        return normalized


def create_landmark_extractor(
    model_base_path: str = str(MODELS_DIR),
) -> LandmarkExtractor:
    """랜드마크 추출기 생성 (팩토리 함수)"""
    return LandmarkExtractor(model_base_path)