"""
Baseline 관리자

바른자세 수집, 저장, 비교 기능 제공
"""
import json
import time
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np

from src.config import ConfigManager
from src.core.indicator_calculator import PostureIndicators
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BaselineMetrics:
    """Baseline 메트릭"""
    timestamp: str
    collection_duration_seconds: float
    frame_count: int
    metrics: Dict[str, float]


class BaselineManager:
    """Baseline 관리자"""
    
    def __init__(self, config: ConfigManager, data_dir: str = "data"):
        """
        초기화
        
        Args:
            config: 설정 관리자
            data_dir: 데이터 저장 디렉토리
        """
        self.config = config
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.baseline_metrics: Optional[BaselineMetrics] = None
        self.collection_frames: list = []
        self.is_collecting = False
        self.collection_start_time = 0.0
        
        logger.info(f"BaselineManager 초기화 완료 (data_dir: {self.data_dir})")
    
    def start_baseline_collection(self):
        """Baseline 수집 시작"""
        self.is_collecting = True
        self.collection_frames = []
        self.collection_start_time = time.time()
        logger.info("Baseline 수집 시작")
    
    def add_frame_to_collection(self, indicators: PostureIndicators):
        """
        Baseline 수집 중 프레임 추가
        
        Args:
            indicators: PostureIndicators
        """
        if not self.is_collecting:
            logger.warning("Baseline 수집 중이 아님")
            return
        
        self.collection_frames.append(indicators)
    
    def finish_baseline_collection(self, fps: int = 30) -> bool:
        """
        Baseline 수집 완료
        
        Args:
            fps: FPS (프레임 당 계산용)
            
        Returns:
            성공 여부
        """
        if not self.is_collecting:
            logger.warning("Baseline 수집 중이 아님")
            return False
        
        self.is_collecting = False
        
        # 수집 시간 확인
        baseline_config = self.config.get_baseline_config()
        expected_duration = baseline_config['capture']['duration_seconds']  # 기본 5초
        
        actual_duration = time.time() - self.collection_start_time
        frame_count = len(self.collection_frames)
        expected_frame_count = int(expected_duration * fps)
        
        logger.info(f"Baseline 수집 완료: {frame_count} 프레임 (예상 {expected_frame_count})")
        
        if frame_count < expected_frame_count * 0.8:  # 80% 이상
            logger.warning(f"Baseline 프레임 부족: {frame_count} < {expected_frame_count}")
            return False
        
        # 평균/중앙값 계산
        try:
            self.baseline_metrics = self._compute_baseline_metrics(
                expected_duration, 
                frame_count
            )
            
            # 자동 저장
            self.save_baseline_to_file()
            
            logger.info("Baseline 메트릭 계산 및 저장 완료")
            return True
        
        except Exception as e:
            logger.error(f"Baseline 계산 실패: {e}")
            return False
    
    def _compute_baseline_metrics(
        self, 
        duration: float, 
        frame_count: int
    ) -> BaselineMetrics:
        """
        Baseline 메트릭 계산
        
        Args:
            duration: 수집 시간 (초)
            frame_count: 프레임 수
            
        Returns:
            BaselineMetrics
        """
        metrics = {}
        
        indicator_names = [
            'cheek_distance',
            'eye_distance',
            'face_shoulder_ratio',
            'shoulder_width',
            'shoulder_tilt_deg',
            'neck_offset',
            'eye_line_tilt',
            'chin_occlusion'
        ]
        
        for name in indicator_names:
            values = []
            for frame in self.collection_frames:
                value = getattr(frame, name, None)
                if value is not None:
                    values.append(value)
            
            if values:
                # 중앙값 사용 (외이값 영향 최소화)
                median_value = float(np.median(values))
                metrics[name] = median_value
                logger.debug(f"{name}: median={median_value:.4f}, count={len(values)}")
        
        return BaselineMetrics(
            timestamp=datetime.now().isoformat(),
            collection_duration_seconds=duration,
            frame_count=frame_count,
            metrics=metrics
        )
    
    def save_baseline_to_file(self, filepath: Optional[str] = None) -> bool:
        """
        Baseline 메트릭을 JSON으로 저장
        
        Args:
            filepath: 저장 경로 (None이면 기본값 사용)
            
        Returns:
            성공 여부
        """
        if self.baseline_metrics is None:
            logger.warning("저장할 baseline이 없음")
            return False
        
        if filepath is None:
            filepath = self.data_dir / "baseline.json"
        else:
            filepath = Path(filepath)
        
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'timestamp': self.baseline_metrics.timestamp,
                'collection_duration_seconds': self.baseline_metrics.collection_duration_seconds,
                'frame_count': self.baseline_metrics.frame_count,
                'metrics': self.baseline_metrics.metrics
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Baseline 저장 완료: {filepath}")
            return True
        
        except Exception as e:
            logger.error(f"Baseline 저장 실패: {e}")
            return False
    
    def load_baseline_from_file(self, filepath: Optional[str] = None) -> bool:
        """
        저장된 baseline 로드
        
        Args:
            filepath: 로드 경로 (None이면 기본값 사용)
            
        Returns:
            성공 여부
        """
        if filepath is None:
            filepath = self.data_dir / "baseline.json"
        else:
            filepath = Path(filepath)
        
        if not filepath.exists():
            logger.warning(f"Baseline 파일 없음: {filepath}")
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.baseline_metrics = BaselineMetrics(
                timestamp=data.get('timestamp', ''),
                collection_duration_seconds=data.get('collection_duration_seconds', 0),
                frame_count=data.get('frame_count', 0),
                metrics=data.get('metrics', {})
            )
            
            logger.info(f"Baseline 로드 완료: {filepath}")
            logger.info(f"  타임스탐프: {self.baseline_metrics.timestamp}")
            logger.info(f"  프레임: {self.baseline_metrics.frame_count}")
            
            return True
        
        except Exception as e:
            logger.error(f"Baseline 로드 실패: {e}")
            return False
    
    def get_baseline_metrics(self) -> Optional[BaselineMetrics]:
        """
        현재 baseline 메트릭 반환
        
        Returns:
            BaselineMetrics 또는 None
        """
        return self.baseline_metrics
    
    def calculate_change_percentage(
        self, 
        current_value: float, 
        metric_name: str
    ) -> float:
        """
        Baseline 대비 변화율 (%) 계산
        
        Args:
            current_value: 현재 값
            metric_name: 지표 이름
            
        Returns:
            변화율 (%)
            예: baseline=10, current=11 → 10% 증가 → +10
                baseline=10, current=9 → 10% 감소 → -10
        """
        if self.baseline_metrics is None or metric_name not in self.baseline_metrics.metrics:
            logger.warning(f"Baseline이 없거나 지표 '{metric_name}'을(를) 찾을 수 없음")
            return 0.0
        
        baseline_value = self.baseline_metrics.metrics[metric_name]
        
        if baseline_value == 0:
            logger.warning(f"Baseline 값이 0: {metric_name}")
            return 0.0
        
        change_percent = (current_value - baseline_value) / baseline_value * 100.0
        
        return float(change_percent)
    
    def is_baseline_valid(self) -> bool:
        """
        Baseline이 충분한 데이터로 설정되었는지 확인
        
        Returns:
            유효 여부
        """
        if self.baseline_metrics is None:
            return False
        
        required_metrics = [
            'cheek_distance',
            'face_shoulder_ratio',
            'shoulder_width'
        ]
        
        for metric_name in required_metrics:
            if metric_name not in self.baseline_metrics.metrics:
                logger.warning(f"필수 지표 부재: {metric_name}")
                return False
        
        return True
    
    def reset(self):
        """Baseline 초기화"""
        self.baseline_metrics = None
        self.collection_frames = []
        self.is_collecting = False
        self.collection_start_time = 0.0
        logger.info("Baseline 초기화 완료")


def create_baseline_manager(config: ConfigManager, data_dir: str = "data") -> BaselineManager:
    """Baseline 관리자 생성 (팩토리 함수)"""
    return BaselineManager(config, data_dir)
