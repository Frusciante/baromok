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


class OneEuroFilter:
    """One Euro 필터 (상태 저장, 벡터 지원)"""
    
    def __init__(self, min_cutoff: float = 0.05, beta: float = 0.005, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None

    def _smoothing_factor(self, t_e: float, cutoff) -> np.ndarray:
        r = 2 * math.pi * cutoff * t_e
        return r / (r + 1.0)

    def process(self, t: float, x: np.ndarray) -> np.ndarray:
        # 입력 x가 리스트라면 np.array로 변환
        x_arr = np.array(x, dtype=float)

        if self.t_prev is None:
            self.x_prev = x_arr
            self.dx_prev = np.zeros_like(self.x_prev)
            self.t_prev = t
            return self.x_prev

        t_e = t - self.t_prev
        if t_e <= 0:
            return self.x_prev
        
        # 1. 속도 계산
        dx = (x_arr - self.x_prev) / t_e

        # 2. 속도 스무딩
        alpha_d = self._smoothing_factor(t_e, self.d_cutoff)
        dx_hat = alpha_d * dx + (1.0 - alpha_d) * self.dx_prev

        # 3. 컷오프 계산 (가변 컷오프)
        cutoff = self.min_cutoff + self.beta * np.abs(dx_hat)

        # 4. 값 스무딩
        alpha = self._smoothing_factor(t_e, cutoff)
        x_hat = alpha * x_arr + (1.0 - alpha) * self.x_prev

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t

        return x_hat

    def reset(self):
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None


class EMAFilter:
    """EMA (Exponential Moving Average) 필터 (상태 저장)"""
    
    def __init__(self, alpha: float = 0.15):
        self.alpha = alpha
        self.value = None

    def process(self, x: float) -> float:
        if self.value is None:
            self.value = float(x)
        else:
            self.value = self.alpha * float(x) + (1.0 - self.alpha) * self.value
        return self.value

    def reset(self):
        self.value = None


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


class RansacQuadraticModel:
    """RANSAC 기반 2차 곡선 적합 모델"""
    
    def __init__(self, min_samples: int = 10, residual_threshold: float = 0.01):
        self.min_samples = min_samples
        self.residual_threshold = residual_threshold
        self.is_fitted = False
        self.model = None

    def fit(self, x_data: List[float], y_data: List[float]) -> bool:
        """2차 곡선 모델 생성 (X: 어깨 너비 등, y: 예상 비율 등)"""
        if len(x_data) < self.min_samples:
            self.is_fitted = False
            return False

        try:
            from sklearn.linear_model import RANSACRegressor
            from sklearn.preprocessing import PolynomialFeatures
            from sklearn.pipeline import make_pipeline

            X = np.array(x_data).reshape(-1, 1)
            y = np.array(y_data)

            # PolynomialFeatures(degree=2, include_bias=True) -> [1, x, x^2]
            # RANSACRegressor(fit_intercept=False) -> bias는 PolynomialFeatures에서 처리
            self.model = make_pipeline(
                PolynomialFeatures(degree=2, include_bias=True),
                RANSACRegressor(
                    residual_threshold=self.residual_threshold,
                    random_state=42,
                    max_trials=200
                )
            )
            self.model.fit(X, y)
            self.is_fitted = True
            return True
        except Exception:
            self.is_fitted = False
            return False

    def predict(self, x: float) -> float:
        """적합된 모델을 통한 예측값 반환"""
        if not self.is_fitted or self.model is None:
            return 0.0
        
        X = np.array([[x]])
        try:
            y_pred = self.model.predict(X)
            return float(y_pred[0])
        except Exception:
            return 0.0
            
    def reset(self):
        self.is_fitted = False
        self.model = None
