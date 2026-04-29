"""
헬퍼 함수 및 유틸리티 모음
"""
import numpy as np
from typing import Tuple, List, Optional
import math


class GeometryHelper:
    """기하학적 계산 헬퍼"""
    
    @staticmethod
    def calculate_distance(point1: np.ndarray, point2: np.ndarray) -> float:
        """
        두 점 사이의 거리 계산 (유클리드 거리)
        
        Args:
            point1: (x, y) 또는 (x, y, z) 좌표
            point2: (x, y) 또는 (x, y, z) 좌표
            
        Returns:
            거리 값
        """
        return float(np.linalg.norm(point1 - point2))
    
    @staticmethod
    def calculate_angle(point1: np.ndarray, vertex: np.ndarray, point2: np.ndarray) -> float:
        """
        세 점으로 이루어진 각도 계산 (도 단위)
        
        Args:
            point1: 첫 번째 점
            vertex: 꼭짓점
            point2: 세 번째 점
            
        Returns:
            각도 (0~180도)
        """
        v1 = point1 - vertex
        v2 = point2 - vertex
        
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle_rad = np.arccos(cos_angle)
        angle_deg = np.degrees(angle_rad)
        
        return float(angle_deg)
    
    @staticmethod
    def calculate_angle_with_horizontal(point1: np.ndarray, point2: np.ndarray) -> float:
        """
        두 점을 연결한 직선과 수평선 사이의 각도 계산
        
        Args:
            point1: 첫 번째 점
            point2: 두 번째 점
            
        Returns:
            각도 (-90~90도)
        """
        dy = point2[1] - point1[1]
        dx = point2[0] - point1[0]
        angle_rad = np.arctan2(dy, dx)
        angle_deg = np.degrees(angle_rad)
        
        return float(angle_deg)
    
    @staticmethod
    def midpoint(point1: np.ndarray, point2: np.ndarray) -> np.ndarray:
        """두 점의 중점 계산"""
        return (point1 + point2) / 2.0


class FilterHelper:
    """노이즈 필터링 헬퍼"""
    
    @staticmethod
    def moving_average(values: List[float], window_size: int = 5) -> float:
        """
        이동 평균 계산
        
        Args:
            values: 값 리스트
            window_size: 윈도우 크기
            
        Returns:
            평균값
        """
        if len(values) == 0:
            return 0.0
        window = values[-window_size:] if len(values) >= window_size else values
        return float(np.mean(window))
    
    @staticmethod
    def median_filter(values: List[float], window_size: int = 5) -> float:
        """
        중앙값 필터
        
        Args:
            values: 값 리스트
            window_size: 윈도우 크기
            
        Returns:
            중앙값
        """
        if len(values) == 0:
            return 0.0
        window = values[-window_size:] if len(values) >= window_size else values
        return float(np.median(window))
    
    @staticmethod
    def exponential_smoothing(current_value: float, previous_value: float, alpha: float = 0.3) -> float:
        """
        지수 평활 필터
        
        Args:
            current_value: 현재 값
            previous_value: 이전 값
            alpha: 평활 계수 (0~1)
            
        Returns:
            평활된 값
        """
        return float(alpha * current_value + (1 - alpha) * previous_value)


class NormalizationHelper:
    """정규화 헬퍼"""
    
    @staticmethod
    def percentage_change(original: float, current: float) -> float:
        """
        백분율 변화 계산
        
        Args:
            original: 원본값
            current: 현재값
            
        Returns:
            변화율 (%)
        """
        if original == 0:
            return 0.0
        return float((current - original) / original * 100)
    
    @staticmethod
    def normalize_to_range(value: float, min_val: float, max_val: float) -> float:
        """
        값을 0~1 범위로 정규화
        
        Args:
            value: 값
            min_val: 최솟값
            max_val: 최댓값
            
        Returns:
            정규화된 값 (0~1)
        """
        if max_val - min_val == 0:
            return 0.0
        normalized = (value - min_val) / (max_val - min_val)
        return float(np.clip(normalized, 0.0, 1.0))


class ConfidenceHelper:
    """신뢰도 관련 헬퍼"""
    
    @staticmethod
    def filter_by_confidence(landmarks: np.ndarray, confidences: np.ndarray, threshold: float = 0.5) -> Tuple[np.ndarray, np.ndarray]:
        """
        신뢰도 임계값으로 랜드마크 필터링
        
        Args:
            landmarks: 랜드마크 좌표 배열 (N, 2) 또는 (N, 3)
            confidences: 신뢰도 배열 (N,)
            threshold: 신뢰도 임계값
            
        Returns:
            필터링된 랜드마크, 신뢰도
        """
        mask = confidences >= threshold
        return landmarks[mask], confidences[mask]
    
    @staticmethod
    def average_confidence(confidences: np.ndarray) -> float:
        """
        평균 신뢰도 계산
        
        Args:
            confidences: 신뢰도 배열
            
        Returns:
            평균 신뢰도
        """
        if len(confidences) == 0:
            return 0.0
        return float(np.mean(confidences))


class TimeHelper:
    """시간 관련 헬퍼"""
    
    @staticmethod
    def frame_count_to_seconds(frame_count: int, fps: int = 30) -> float:
        """
        프레임 수를 초 단위로 변환
        
        Args:
            frame_count: 프레임 수
            fps: FPS (초당 프레임)
            
        Returns:
            초 단위 시간
        """
        if fps <= 0:
            return 0.0
        return float(frame_count / fps)
    
    @staticmethod
    def seconds_to_frame_count(seconds: float, fps: int = 30) -> int:
        """
        초를 프레임 수로 변환
        
        Args:
            seconds: 초 단위 시간
            fps: FPS
            
        Returns:
            프레임 수
        """
        return int(seconds * fps)
