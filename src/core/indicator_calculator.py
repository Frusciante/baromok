"""
자세 지표 계산기

랜드마크로부터 자세 관련 지표를 계산 (거리, 비율, 각도 등)
"""
import numpy as np
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
    shoulder_width: float  # 양쪽 어깨 거리
    shoulder_tilt_deg: float  # 어깨 기울기 (도)
    neck_offset: float  # 목-어깨 정렬 오차
    eye_line_tilt: float  # 눈 수평선 기울기 (도)
    chin_occlusion: float  # 턱 가림 정도 (0~1)
    hand_near_face: bool  # 손이 얼굴 근처인가
    timestamp: float  # 타임스탬프
    step_index: int = 0 # 캘리브레이션 단계 (디버그용)


class IndicatorCalculator:
    """자세 지표 계산기"""
    
    def __init__(self, config: Optional[ConfigManager] = None):
        """초기화"""
        self.config = config
        self.geometry_helper = GeometryHelper()
        self.normalization_helper = NormalizationHelper()
        # 어깨 기울기 스무딩 버퍼
        self._shoulder_tilt_history = deque(maxlen=5)
        logger.info("IndicatorCalculator 초기화 완료")
    
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
    
    def calculate_face_shoulder_ratio(
        self,
        cheek_distance: float,
        shoulder_width: float
    ) -> float:
        """
        얼굴 크기 대비 어깨 너비 비율 계산 (거리 메트릭)
        """
        if shoulder_width < 1e-3:
            return 0.0
        
        ratio = cheek_distance / shoulder_width
        return float(np.clip(ratio, 0.0, 1.0))
    
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
        if not chin_points or not hand_tips:
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
            hand_points = hand_tips.get(hand_key, [])
            for hand_point in hand_points:
                hand = np.array(hand_point[:2])
                for chin_point in chin_points:
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
        if face_center is None or not hand_tips:
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
            hand_points = hand_tips.get(hand_key, [])
            for hand_point in hand_points:
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
        if face_center is None or not hand_tips:
            return 0.0
            
        min_distance = 1.0
        face = np.array(face_center)
        for hand_key in ['right_hand_tips', 'left_hand_tips']:
            hand_points = hand_tips.get(hand_key, [])
            for hand_point in hand_points:
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
            shoulder_w_raw = self.calculate_shoulder_width(landmarks['left_shoulder'], landmarks['right_shoulder'])
            
            cheek_dist = self.ema_filters['cheek_distance'].process(cheek_dist_raw)
            shoulder_w = self.ema_filters['shoulder_width'].process(shoulder_w_raw)
            eye_dist = self.ema_filters['eye_distance'].process(eye_dist_raw)
            
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
            
            chin_occ = self.calculate_chin_occlusion(
                landmarks.get('chin_points', []),
                {
                    'right_hand_tips': landmarks.get('right_hand_tips', []),
                    'left_hand_tips': landmarks.get('left_hand_tips', [])
                }
            )
            
            hand_near = self.calculate_hand_near_face(
                {
                    'right_hand_tips': landmarks.get('right_hand_tips', []),
                    'left_hand_tips': landmarks.get('left_hand_tips', [])
                },
                landmarks.get('face_center'),
                threshold=0.15
            )
            
            return PostureIndicators(
                cheek_distance=cheek_dist,
                eye_distance=eye_dist,
                shoulder_width=shoulder_w,
                shoulder_tilt_deg=shoulder_tilt,
                neck_offset=neck_off,
                eye_line_tilt=eye_tilt,
                chin_occlusion=chin_occ,
                hand_near_face=hand_near,
                timestamp=timestamp
            )
        except Exception as e:
            logger.error(f"지표 계산 실패: {e}")
            return None


def create_indicator_calculator(config: Optional[ConfigManager] = None) -> IndicatorCalculator:
    """지표 계산기 생성 (팩토리 함수)"""
    return IndicatorCalculator(config)
