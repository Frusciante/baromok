"""
자세 지표 계산기

랜드마크로부터 자세 관련 지표를 계산 (거리, 비율, 각도 등)
"""
import numpy as np
import math
import time
from dataclasses import dataclass
from typing import Tuple, Dict, Optional
from src.utils.helpers import GeometryHelper, NormalizationHelper, EMAFilter
from src.utils.logger import get_logger
from collections import deque

from src.config import ConfigManager

logger = get_logger(__name__)


@dataclass
class PostureIndicators:
    """자세 지표 데이터"""
    cheek_distance: float  # 양쪽 광대 거리 (얼굴 길이/크기 척도로 사용)
    eye_distance: float  # 양쪽 눈 거리
    face_vertical_length: float # 얼굴 세로 길이 (미간-턱 끝)
    shoulder_width: float  # 양쪽 어깨 거리
    shoulder_tilt_deg: float  # 어깨 기울기 (도)
    neck_offset: float  # 목-어깨 정렬 오차
    eye_line_tilt: float  # 눈 수평선 기울기 (도)
    chin_occlusion: float  # 턱 가림 정도 (0~1)
    hand_near_face: bool  # 손이 얼굴 근처인가
    hand_face_score: float # 손-얼굴 상호작용 점수 (신규)
    
    # [신규] 중앙 정렬(Symmetry) 지표
    eye_symmetry_ratio: float   # 눈 중앙 정렬 비율 (0~1, 0에 가까울수록 대칭)
    cheek_symmetry_ratio: float # 광대 중앙 정렬 비율
    chin_alignment_offset: float # 턱의 수평 이탈 정도
    
    # Absolute eye-screen distance (cm) measured via iris; None if unavailable
    eye_screen_distance_cm: Optional[float] = None
    # Warning flag: eye closer than configured threshold continuously for sustain_seconds
    eye_close_warning: bool = False
    
    timestamp: float = 0.0  # 타임스탬프
    step_index: int = 0 # 자세 맞춤 단계 (디버그용)


class IndicatorCalculator:
    """자세 지표 계산기"""
    
    def __init__(self, config: Optional[ConfigManager] = None):
        """초기화"""
        self.config = config
        self.geometry_helper = GeometryHelper()
        self.normalization_helper = NormalizationHelper()
        # 어깨 기울기 스무딩 버퍼
        self._shoulder_tilt_history = deque(maxlen=5)
        
        # 설정에서 alpha 값 로드 (기본값 0.15)
        alpha = 0.15
        if self.config:
            alpha = self.config.get_posture_criteria().get("filters", {}).get("indicator_ema", {}).get("alpha", 0.15)
            
        self.ema_filters = {
            'cheek_distance': EMAFilter(alpha=alpha),
            'eye_distance': EMAFilter(alpha=alpha),
            'face_vertical_length': EMAFilter(alpha=alpha),
            'shoulder_width': EMAFilter(alpha=alpha),
            'shoulder_tilt_deg': EMAFilter(alpha=alpha),
            'neck_offset': EMAFilter(alpha=alpha),
            'eye_line_tilt': EMAFilter(alpha=alpha),
            'chin_occlusion': EMAFilter(alpha=alpha),
            'hand_face_score': EMAFilter(alpha=alpha),
        }
        logger.info(f"IndicatorCalculator 초기화 완료 (alpha={alpha})")
        # Eye monitoring / iris-based absolute distance settings
        self._eye_monitoring_cfg = {}
        try:
            if self.config:
                self._eye_monitoring_cfg = self.config.get_posture_criteria().get("eye_monitoring", {})
        except Exception:
            self._eye_monitoring_cfg = {}

        self._iris_diameter_mm = float(self._eye_monitoring_cfg.get("iris_diameter_mm", 11.7))
        self._camera_hfov_deg = float(self._eye_monitoring_cfg.get("camera_horizontal_fov_deg", 60.0))
        self._eye_distance_threshold_cm = float(self._eye_monitoring_cfg.get("distance_threshold_cm", 40.0))
        self._eye_sustain_seconds = float(self._eye_monitoring_cfg.get("sustain_seconds", 2.0))
        self._eye_close_start_time: Optional[float] = None
        # frame width for focal length calculation (pixels)
        try:
            self._camera_frame_width = int(self.config.get_app_setting('camera_resolution_width', 1280)) if self.config else 1280
        except Exception:
            self._camera_frame_width = 1280
    
    def calculate_cheek_distance(
        self, 
        left_cheek: Tuple[float, float], 
        right_cheek: Tuple[float, float]
    ) -> float:
        """
        양쪽 광대뼈 간 거리 계산
        """
        if left_cheek is None or right_cheek is None:
            return 0.0
        
        left = np.array(left_cheek)
        right = np.array(right_cheek)
        
        distance = self.geometry_helper.calculate_distance(left, right)
        return float(np.clip(distance, 0.0, 1.0))
    
    def calculate_eye_distance(
        self, 
        left_eye: Tuple[float, float], 
        right_eye: Tuple[float, float]
    ) -> float:
        """
        양쪽 눈 간 거리 계산
        """
        if left_eye is None or right_eye is None:
            return 0.0
        
        left = np.array(left_eye)
        right = np.array(right_eye)
        
        distance = self.geometry_helper.calculate_distance(left, right)
        return float(np.clip(distance, 0.0, 1.0))

    def calculate_face_vertical_length(
        self, 
        left_eye: Tuple[float, float], 
        right_eye: Tuple[float, float],
        chin: Tuple[float, float]
    ) -> float:
        """
        얼굴 세로 길이 계산 (미간 - 턱 끝)
        """
        if left_eye is None or right_eye is None or chin is None:
            return 0.0
            
        eye_midpoint = np.array([(left_eye[0] + right_eye[0]) / 2.0, 
                                (left_eye[1] + right_eye[1]) / 2.0])
        chin_point = np.array(chin)
        
        distance = self.geometry_helper.calculate_distance(eye_midpoint, chin_point)
        return float(np.clip(distance, 0.0, 1.0))
    
    def calculate_shoulder_width(
        self, 
        left_shoulder: Tuple[float, float], 
        right_shoulder: Tuple[float, float]
    ) -> float:
        """
        양쪽 어깨 간 거리 계산
        """
        if left_shoulder is None or right_shoulder is None:
            return 0.0
        
        left = np.array(left_shoulder)
        right = np.array(right_shoulder)
        
        distance = self.geometry_helper.calculate_distance(left, right)
        return float(np.clip(distance, 0.0, 1.0))
    
    def calculate_shoulder_tilt_degree(
        self, 
        left_shoulder: Tuple[float, float], 
        right_shoulder: Tuple[float, float]
    ) -> float:
        """
        좌우 어깨 기울기 계산 (도 단위)
        """
        if left_shoulder is None or right_shoulder is None:
            return 0.0
        
        left = np.array(left_shoulder)
        right = np.array(right_shoulder)
        
        height_diff = right[1] - left[1]
        width_diff = right[0] - left[0]
        
        if abs(width_diff) < 1e-3:
            return 0.0

        angle_rad = np.arctan2(-height_diff, width_diff)
        angle_deg = np.degrees(angle_rad)

        return float(np.clip(angle_deg, -90.0, 90.0))
    
    def calculate_neck_offset(
        self, 
        face_center: Tuple[float, float], 
        left_shoulder: Tuple[float, float],
        right_shoulder: Tuple[float, float]
    ) -> float:
        """
        목-어깨 정렬 오차 계산
        """
        if face_center is None or left_shoulder is None or right_shoulder is None:
            return 0.0
        
        shoulder_center_x = (left_shoulder[0] + right_shoulder[0]) / 2.0
        shoulder_center_y = (left_shoulder[1] + right_shoulder[1]) / 2.0
        
        face = np.array(face_center)
        shoulder_center = np.array([shoulder_center_x, shoulder_center_y])
        
        distance = self.geometry_helper.calculate_distance(face, shoulder_center)
        return float(np.clip(distance, 0.0, 1.0))
    
    def calculate_eye_line_tilt(
        self, 
        left_eye: Tuple[float, float], 
        right_eye: Tuple[float, float]
    ) -> float:
        """
        눈 수평선 기울기 계산
        """
        if left_eye is None or right_eye is None:
            return 0.0
        
        left = np.array(left_eye)
        right = np.array(right_eye)
        
        angle_deg = self.geometry_helper.calculate_angle_with_horizontal(left, right)
        return float(np.clip(angle_deg, -90.0, 90.0))
    
    def calculate_chin_occlusion(
        self, 
        chin_points: list, 
        hand_tips: dict
    ) -> float:
        """
        손과 턱의 겹침 정도 계산
        """
        # 방어: None 값이 들어올 수 있으므로 빈 리스트/딕셔너리로 대체
        if not chin_points:
            return 0.0
        if not hand_tips or (not (hand_tips.get('right_hand_tips') or hand_tips.get('left_hand_tips'))):
            return 0.0

        threshold = 0.1
        if self.config:
            # 설정에서 임계값 로드 시도
            try:
                threshold = self.config.get_posture_criteria().get("chin_rest_estimated", {}).get("primary_conditions", {}).get("chin_occlusion", {}).get("threshold", 0.1)
            except Exception:
                pass
        
        occlusion_score = 0.0
        for hand_key in ['right_hand_tips', 'left_hand_tips']:
            hand_points = hand_tips.get(hand_key) or []
            for hand_point in hand_points:
                if hand_point is None:
                    continue
                hand = np.array(hand_point[:2])
                for chin_point in chin_points:
                    if chin_point is None:
                        continue
                    chin = np.array(chin_point)
                    distance = self.geometry_helper.calculate_distance(chin, hand)
                    if distance < threshold:
                        occlusion_score += (1.0 - distance / threshold) * 0.1
        
        return float(np.clip(occlusion_score, 0.0, 1.0))
    
    def calculate_hand_near_face(
        self, 
        hand_tips: dict, 
        face_center: Tuple[float, float],
        threshold: Optional[float] = None
    ) -> bool:
        """
        손이 얼굴 근처에 있는지 판단
        """
        if face_center is None:
            return False
        
        if threshold is None:
            threshold = 0.15
            if self.config:
                try:
                    threshold = self.config.get_posture_criteria().get("chin_rest_estimated", {}).get("primary_conditions", {}).get("hand_near_face", {}).get("threshold", 0.15)
                except Exception:
                    pass
        
        face = np.array(face_center)
        for hand_key in ['right_hand_tips', 'left_hand_tips']:
            hand_points = hand_tips.get(hand_key) or []
            for hand_point in hand_points:
                if hand_point is None:
                    continue
                hand = np.array(hand_point[:2])
                distance = self.geometry_helper.calculate_distance(hand, face)
                if distance < threshold:
                    return True
        return False
    
    def calculate_hand_near_score(
        self, 
        hand_tips: dict, 
        face_center: Tuple[float, float]
    ) -> float:
        """
        손이 얼굴 근처에 있는 정도를 점수로 계산
        """
        if face_center is None:
            return 0.0

        min_distance = 1.0
        face = np.array(face_center)
        for hand_key in ['right_hand_tips', 'left_hand_tips']:
            hand_points = hand_tips.get(hand_key) or []
            for hand_point in hand_points:
                if hand_point is None:
                    continue
                hand = np.array(hand_point[:2])
                distance = self.geometry_helper.calculate_distance(hand, face)
                if distance < min_distance:
                    min_distance = distance
                    
        min_d = 0.1
        max_d = 0.3
        score = 1.0 - (min_distance - min_d) / (max_d - min_d)
        return float(np.clip(score, 0.0, 1.0))
    
    def calculate_all_indicators(
        self,
        landmarks: Dict[str, any],
        timestamp: float = 0.0,
        low_latency: bool = False
    ) -> Optional[PostureIndicators]:
        """
        모든 자세 지표 계산
        """
        if (landmarks.get('left_cheek') is None or
            landmarks.get('right_cheek') is None or
            landmarks.get('left_shoulder') is None or
            landmarks.get('right_shoulder') is None):
            return None

        # 필터 계수 조정
        base_alpha = 0.15
        if self.config:
            try:
                base_alpha = self.config.get_posture_criteria().get("filters", {}).get("indicator_ema", {}).get("alpha", 0.15)
            except Exception:
                pass
            
        current_alpha = 0.5 if low_latency else base_alpha
        for filter_obj in self.ema_filters.values():
            filter_obj.alpha = current_alpha

        try:
            cheek_dist_raw = self.calculate_cheek_distance(landmarks['left_cheek'], landmarks['right_cheek'])            
            eye_dist_raw = self.calculate_eye_distance(landmarks.get('left_eye'), landmarks.get('right_eye'))
            
            # 얼굴 세로 길이 계산 (눈 미간 - 턱 152번)
            chin_point = landmarks.get('chin_points')[0] if landmarks.get('chin_points') else None
            face_v_len_raw = self.calculate_face_vertical_length(landmarks.get('left_eye'), landmarks.get('right_eye'), chin_point)
            
            shoulder_w_raw = self.calculate_shoulder_width(landmarks['left_shoulder'], landmarks['right_shoulder'])
            
            cheek_dist = self.ema_filters['cheek_distance'].process(cheek_dist_raw)
            shoulder_w = self.ema_filters['shoulder_width'].process(shoulder_w_raw)
            eye_dist = self.ema_filters['eye_distance'].process(eye_dist_raw)
            face_v_len = self.ema_filters['face_vertical_length'].process(face_v_len_raw)
            
            shoulder_tilt = self.calculate_shoulder_tilt_degree(landmarks['left_shoulder'], landmarks['right_shoulder'])
            try:
                self._shoulder_tilt_history.append(shoulder_tilt)
                if len(self._shoulder_tilt_history) > 0:
                    shoulder_tilt = float(np.median(list(self._shoulder_tilt_history)))
            except Exception:
                pass
            
            neck_off = self.calculate_neck_offset(landmarks.get('face_center'), landmarks['left_shoulder'], landmarks['right_shoulder'])
            eye_tilt = self.calculate_eye_line_tilt(landmarks.get('left_eye'), landmarks.get('right_eye'))
            chin_occ = self.calculate_chin_occlusion(landmarks.get('chin_points', []), {
                'right_hand_tips': landmarks.get('right_hand_tips', []),
                'left_hand_tips': landmarks.get('left_hand_tips', [])
            })
            
            # [신규] 중앙 정렬(Symmetry) 계산
            eye_sym = 0.0
            cheek_sym = 0.0
            chin_offset = 0.0
            
            face_center = landmarks.get('face_center')
            if face_center:
                # 1. 눈 대칭 (중앙-왼쪽눈 vs 중앙-오른쪽눈 수평 거리)
                if landmarks.get('left_eye') and landmarks.get('right_eye'):
                    l_dist = abs(face_center[0] - landmarks['left_eye'][0])
                    r_dist = abs(face_center[0] - landmarks['right_eye'][0])
                    total = l_dist + r_dist
                    if total > 0:
                        eye_sym = abs(l_dist - r_dist) / total
                
                # 2. 광대 대칭
                if landmarks.get('left_cheek') and landmarks.get('right_cheek'):
                    l_c_dist = abs(face_center[0] - landmarks['left_cheek'][0])
                    r_c_dist = abs(face_center[0] - landmarks['right_cheek'][0])
                    total_c = l_c_dist + r_c_dist
                    if total_c > 0:
                        cheek_sym = abs(l_c_dist - r_c_dist) / total_c
                
                # 3. 턱 수평 오프셋 (중앙선 대비 턱 위치)
                if landmarks.get('chin_points'):
                    chin_offset = abs(face_center[0] - landmarks['chin_points'][0][0])

            hand_near = self.calculate_hand_near_face({
                'right_hand_tips': landmarks.get('right_hand_tips', []),
                'left_hand_tips': landmarks.get('left_hand_tips', [])
            }, landmarks.get('face_center'))
            
            near_score = self.calculate_hand_near_score({
                'right_hand_tips': landmarks.get('right_hand_tips', []),
                'left_hand_tips': landmarks.get('left_hand_tips', [])
            }, landmarks.get('face_center'))
            
            # 설정에서 손-얼굴 가중치 로드
            hf_weights = {"near_score": 0.5, "occlusion_score": 0.5}
            if self.config:
                scoring_config = self.config.get_frame_scoring_config()
                hf_weights = scoring_config.get("hand_face_weights", hf_weights)
            
            hand_face_score_raw = (
                hf_weights.get("near_score", 0.5) * near_score + 
                hf_weights.get("occlusion_score", 0.5) * chin_occ
            )
            
            shoulder_tilt = self.ema_filters['shoulder_tilt_deg'].process(shoulder_tilt)
            neck_off = self.ema_filters['neck_offset'].process(neck_off)
            eye_tilt = self.ema_filters['eye_line_tilt'].process(eye_tilt)
            chin_occ = self.ema_filters['chin_occlusion'].process(chin_occ)
            hand_face_score = self.ema_filters['hand_face_score'].process(hand_face_score_raw)

            # --- Iris-based eye-screen absolute distance estimation (cm) ---
            eye_screen_cm = None
            eye_warning = False
            try:
                # prefer raw per-frame iris diameters if available
                left_px = None
                right_px = None
                if landmarks.get('left_iris_diameter_px_raw') is not None:
                    left_px = landmarks.get('left_iris_diameter_px_raw')
                elif landmarks.get('left_iris_diameter_px') is not None:
                    left_px = landmarks.get('left_iris_diameter_px')

                if landmarks.get('right_iris_diameter_px_raw') is not None:
                    right_px = landmarks.get('right_iris_diameter_px_raw')
                elif landmarks.get('right_iris_diameter_px') is not None:
                    right_px = landmarks.get('right_iris_diameter_px')

                def _compute_z_cm(d_px: float) -> Optional[float]:
                    if d_px is None or d_px <= 0:
                        return None
                    hfov_rad = math.radians(self._camera_hfov_deg)
                    f_px = float(self._camera_frame_width) / (2.0 * math.tan(hfov_rad / 2.0))
                    z_mm = (self._iris_diameter_mm * f_px) / float(d_px)
                    return float(z_mm / 10.0)

                left_cm = _compute_z_cm(left_px)
                right_cm = _compute_z_cm(right_px)

                # choose conservative (closer) estimate if available
                vals = [v for v in (left_cm, right_cm) if v is not None]
                if vals:
                    eye_screen_cm = float(min(vals))

                # sustained warning logic
                now = float(timestamp) if timestamp and timestamp > 0 else time.time()
                if eye_screen_cm is not None and eye_screen_cm <= self._eye_distance_threshold_cm:
                    if self._eye_close_start_time is None:
                        self._eye_close_start_time = now
                    elapsed = now - float(self._eye_close_start_time)
                    if elapsed >= float(self._eye_sustain_seconds):
                        eye_warning = True
                else:
                    self._eye_close_start_time = None
                    eye_warning = False
            except Exception:
                eye_screen_cm = None
                eye_warning = False
            
            return PostureIndicators(
                cheek_distance=cheek_dist,
                eye_distance=eye_dist,
                face_vertical_length=face_v_len,
                shoulder_width=shoulder_w,
                shoulder_tilt_deg=shoulder_tilt,
                neck_offset=neck_off,
                eye_line_tilt=eye_tilt,
                chin_occlusion=chin_occ,
                hand_near_face=hand_near,
                hand_face_score=hand_face_score,
                eye_symmetry_ratio=eye_sym,
                cheek_symmetry_ratio=cheek_sym,
                chin_alignment_offset=chin_offset,
                eye_screen_distance_cm=eye_screen_cm,
                eye_close_warning=eye_warning,
                timestamp=timestamp
            )
        except Exception as e:
            logger.error(f"지표 계산 실패: {e}")
            return None


def create_indicator_calculator(config: Optional[ConfigManager] = None) -> IndicatorCalculator:
    """지표 계산기 생성 (팩토리 함수)"""
    return IndicatorCalculator(config)
