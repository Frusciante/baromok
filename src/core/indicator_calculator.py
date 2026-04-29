"""
자세 지표 계산기

랜드마크로부터 자세 관련 지표를 계산 (거리, 비율, 각도 등)
"""
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Dict, Optional
from src.utils.helpers import GeometryHelper, NormalizationHelper
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PostureIndicators:
    """자세 지표 데이터"""
    cheek_distance: float  # 양쪽 광대 거리
    eye_distance: float  # 양쪽 눈 거리
    face_shoulder_ratio: float  # cheek_distance / shoulder_width
    shoulder_width: float  # 양쪽 어깨 거리
    shoulder_tilt_deg: float  # 어깨 기울기 (도)
    neck_offset: float  # 목-어깨 정렬 오차
    eye_line_tilt: float  # 눈 수평선 기울기 (도)
    chin_occlusion: float  # 턱 가림 정도 (0~1)
    hand_near_face: bool  # 손이 얼굴 근처인가
    timestamp: float  # 타임스탬프


class IndicatorCalculator:
    """자세 지표 계산기"""
    
    def __init__(self):
        """초기화"""
        self.geometry_helper = GeometryHelper()
        self.normalization_helper = NormalizationHelper()
        logger.info("IndicatorCalculator 초기화 완료")
    
    def calculate_cheek_distance(
        self, 
        left_cheek: Tuple[float, float], 
        right_cheek: Tuple[float, float]
    ) -> float:
        """
        양쪽 광대뼈 간 거리 계산
        
        Args:
            left_cheek: 왼쪽 광대 (정규화 좌표)
            right_cheek: 오른쪽 광대 (정규화 좌표)
            
        Returns:
            정규화된 거리 (0~1)
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
        
        Args:
            left_eye: 왼쪽 눈 (정규화 좌표)
            right_eye: 오른쪽 눈 (정규화 좌표)
            
        Returns:
            정규화된 거리 (0~1)
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
        
        Args:
            left_shoulder: 왼쪽 어깨 (정규화 좌표)
            right_shoulder: 오른쪽 어깨 (정규화 좌표)
            
        Returns:
            정규화된 거리 (0~1)
        """
        if left_shoulder is None or right_shoulder is None:
            return 0.0
        
        left = np.array(left_shoulder)
        right = np.array(right_shoulder)
        
        distance = self.geometry_helper.calculate_distance(left, right)
        return float(np.clip(distance, 0.0, 1.0))
    
    def calculate_face_shoulder_ratio(
        self, 
        cheek_distance: float, 
        shoulder_width: float
    ) -> float:
        """
        얼굴-어깨 비율 계산
        
        비율 증가: 머리가 카메라에 가까워짐 (거북목)
        비율 감소: 머리가 카메라에서 멀어짐 (누운 자세)
        
        Args:
            cheek_distance: 광대 거리
            shoulder_width: 어깨 너비
            
        Returns:
            비율 (0~2)
        """
        if shoulder_width == 0 or shoulder_width < 0.01:
            return 0.0
        
        ratio = cheek_distance / shoulder_width
        return float(np.clip(ratio, 0.0, 2.0))
    
    def calculate_shoulder_tilt_degree(
        self, 
        left_shoulder: Tuple[float, float], 
        right_shoulder: Tuple[float, float]
    ) -> float:
        """
        좌우 어깨 기울기 계산 (도 단위)
        
        양수: 오른쪽 어깨가 높음
        음수: 왼쪽 어깨가 높음
        절댓값이 클수록 다리 꼬기 또는 비대칭 자세
        
        Args:
            left_shoulder: 왼쪽 어깨 (정규화 좌표)
            right_shoulder: 오른쪽 어깨 (정규화 좌표)
            
        Returns:
            각도 (-90~90도)
        """
        if left_shoulder is None or right_shoulder is None:
            return 0.0
        
        left = np.array(left_shoulder)
        right = np.array(right_shoulder)
        
        # 높이 차이 계산 (y축)
        height_diff = right[1] - left[1]  # y축은 아래로 증가
        width_diff = right[0] - left[0]
        
        # 각도 계산 (라디안)
        angle_rad = np.arctan2(-height_diff, width_diff)  # 음수로 변환 (위가 양수가 되도록)
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
        
        코와 어깨 중심의 수평 거리
        
        Args:
            face_center: 얼굴 중심 (코)
            left_shoulder: 왼쪽 어깨
            right_shoulder: 오른쪽 어깨
            
        Returns:
            정규화된 거리 (0~1)
        """
        if face_center is None or left_shoulder is None or right_shoulder is None:
            return 0.0
        
        # 어깨 중심 계산
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
        눈 수평선과 프레임 수평선의 각도 차이
        
        큰 값: 머리가 기울어짐 (턱 괸 자세 가능성)
        
        Args:
            left_eye: 왼쪽 눈 (정규화 좌표)
            right_eye: 오른쪽 눈 (정규화 좌표)
            
        Returns:
            각도 (-90~90도)
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
        
        Args:
            chin_points: 턱 포인트 리스트
            hand_tips: 손가락 팁 딕셔너리
                      {'right_hand_tips': [...], 'left_hand_tips': [...]}
            
        Returns:
            겹침 정도 (0~1)
        """
        if not chin_points or not hand_tips:
            return 0.0
        
        occlusion_score = 0.0
        total_hand_points = 0
        
        for hand_key in ['right_hand_tips', 'left_hand_tips']:
            hand_points = hand_tips.get(hand_key, [])
            if not hand_points:
                continue
            
            for hand_point in hand_points:
                hand = np.array(hand_point[:2])  # (x, y) 만 사용
                total_hand_points += 1
                
                # 턱 포인트와의 거리
                for chin_point in chin_points:
                    chin = np.array(chin_point)
                    distance = self.geometry_helper.calculate_distance(chin, hand)
                    
                    # 거리가 가까울수록 겹침 점수 증가
                    # threshold: 0.1 (얼굴 크기의 10%)
                    if distance < 0.1:
                        occlusion_score += (1.0 - distance / 0.1) * 0.1
        
        return float(np.clip(occlusion_score, 0.0, 1.0))
    
    def calculate_hand_near_face(
        self, 
        hand_tips: dict, 
        face_center: Tuple[float, float],
        threshold: float = 0.15
    ) -> bool:
        """
        손이 얼굴 근처에 있는지 판단
        
        Args:
            hand_tips: 손가락 팁 딕셔너리
            face_center: 얼굴 중심 (코)
            threshold: 거리 임계값 (얼굴 크기 대비 비율)
            
        Returns:
            True if 손이 얼굴 근처, False otherwise
        """
        if face_center is None or not hand_tips:
            return False
        
        face = np.array(face_center)
        
        for hand_key in ['right_hand_tips', 'left_hand_tips']:
            hand_points = hand_tips.get(hand_key, [])
            for hand_point in hand_points:
                hand = np.array(hand_point[:2])  # (x, y) 만 사용
                distance = self.geometry_helper.calculate_distance(hand, face)
                
                if distance < threshold:
                    return True
        
        return False
    
    def calculate_all_indicators(
        self, 
        landmarks: Dict[str, any],
        timestamp: float = 0.0
    ) -> Optional[PostureIndicators]:
        """
        모든 자세 지표 계산
        
        Args:
            landmarks: get_relevant_landmarks()의 반환값
            timestamp: 타임스탬프
            
        Returns:
            PostureIndicators 또는 None (필수 랜드마크 없을 때)
        """
        # 필수 랜드마크 확인
        if (landmarks.get('left_cheek') is None or 
            landmarks.get('right_cheek') is None or
            landmarks.get('left_shoulder') is None or
            landmarks.get('right_shoulder') is None):
            logger.debug("필수 랜드마크 부재")
            return None
        
        try:
            cheek_dist = self.calculate_cheek_distance(
                landmarks['left_cheek'], 
                landmarks['right_cheek']
            )
            
            eye_dist = self.calculate_eye_distance(
                landmarks.get('left_eye'),
                landmarks.get('right_eye')
            )
            
            shoulder_w = self.calculate_shoulder_width(
                landmarks['left_shoulder'],
                landmarks['right_shoulder']
            )
            
            face_ratio = self.calculate_face_shoulder_ratio(cheek_dist, shoulder_w)
            
            shoulder_tilt = self.calculate_shoulder_tilt_degree(
                landmarks['left_shoulder'],
                landmarks['right_shoulder']
            )
            
            neck_off = self.calculate_neck_offset(
                landmarks.get('face_center'),
                landmarks['left_shoulder'],
                landmarks['right_shoulder']
            )
            
            eye_tilt = self.calculate_eye_line_tilt(
                landmarks.get('left_eye'),
                landmarks.get('right_eye')
            )
            
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
                face_shoulder_ratio=face_ratio,
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


def create_indicator_calculator() -> IndicatorCalculator:
    """지표 계산기 생성 (팩토리 함수)"""
    return IndicatorCalculator()
