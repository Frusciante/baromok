"""
판정 엔진

자세 판정 로직 구현 (4가지 자세)
"""
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum

from src.config import ConfigManager
from src.core.indicator_calculator import PostureIndicators
from src.core.baseline_manager import BaselineManager
from src.utils.logger import get_logger
from src.utils.helpers import NormalizationHelper

logger = get_logger(__name__)


class PostureType(Enum):
    """자세 유형"""
    FORWARD_HEAD = "forward_head"  # 거북목
    RECLINE = "recline"  # 기댄 자세
    CROSSED_LEG = "crossed_leg_estimated"  # 다리 꼰 자세
    CHIN_REST = "chin_rest_estimated"  # 턱 괸 자세


@dataclass
class PostureJudgmentResult:
    """단일 프레임 판정 결과"""
    forward_head_likelihood: float  # 0~1
    forward_head_triggered: bool
    recline_likelihood: float
    recline_triggered: bool
    crossed_leg_likelihood: float
    crossed_leg_triggered: bool
    chin_rest_likelihood: float
    chin_rest_triggered: bool
    dominant_posture: Optional[str]  # 가장 확률이 높은 자세
    timestamp: float


class JudgmentEngine:
    """자세 판정 엔진"""
    
    def __init__(self, config: ConfigManager, baseline_manager: BaselineManager):
        """
        초기화
        
        Args:
            config: 설정 관리자
            baseline_manager: baseline 관리자
        """
        self.config = config
        self.baseline_manager = baseline_manager
        self.normalization_helper = NormalizationHelper()
        
        # 자세별 프레임 누적 횟수
        self.posture_history: Dict[str, int] = {
            PostureType.FORWARD_HEAD.value: 0,
            PostureType.RECLINE.value: 0,
            PostureType.CROSSED_LEG.value: 0,
            PostureType.CHIN_REST.value: 0,
        }
        
        logger.info("JudgmentEngine 초기화 완료")
    
    def judge_single_frame(self, indicators: PostureIndicators) -> PostureJudgmentResult:
        """
        단일 프레임에 대한 자세 판정
        
        Args:
            indicators: PostureIndicators
            
        Returns:
            PostureJudgmentResult
        """
        # 각 자세별 판정
        forward_head_result = self._judge_forward_head(indicators)
        recline_result = self._judge_recline(indicators)
        crossed_leg_result = self._judge_crossed_leg(indicators)
        chin_rest_result = self._judge_chin_rest(indicators)
        
        # 가장 확률이 높은 자세 결정
        likelihoods = {
            PostureType.FORWARD_HEAD.value: forward_head_result['likelihood'],
            PostureType.RECLINE.value: recline_result['likelihood'],
            PostureType.CROSSED_LEG.value: crossed_leg_result['likelihood'],
            PostureType.CHIN_REST.value: chin_rest_result['likelihood'],
        }
        
        # 임계값 이상인 자세들만 고려
        above_threshold = {
            k: v for k, v in likelihoods.items() if v > 0.3
        }
        
        dominant_posture = None
        if above_threshold:
            dominant_posture = max(above_threshold, key=above_threshold.get)
        
        return PostureJudgmentResult(
            forward_head_likelihood=forward_head_result['likelihood'],
            forward_head_triggered=forward_head_result['triggered'],
            recline_likelihood=recline_result['likelihood'],
            recline_triggered=recline_result['triggered'],
            crossed_leg_likelihood=crossed_leg_result['likelihood'],
            crossed_leg_triggered=crossed_leg_result['triggered'],
            chin_rest_likelihood=chin_rest_result['likelihood'],
            chin_rest_triggered=chin_rest_result['triggered'],
            dominant_posture=dominant_posture,
            timestamp=indicators.timestamp
        )
    
    def _judge_forward_head(self, indicators: PostureIndicators) -> Dict[str, any]:
        """
        거북목 자세 판정
        
        조건:
        - cheek_distance 증가 (얼굴이 카메라에 가까워짐)
        - face_shoulder_ratio 증가
        """
        try:
            criteria = self.config.get_posture_type_config(PostureType.FORWARD_HEAD.value)
            
            cheek_change = self.baseline_manager.calculate_change_percentage(
                indicators.cheek_distance, 
                'cheek_distance'
            )
            
            ratio_change = self.baseline_manager.calculate_change_percentage(
                indicators.face_shoulder_ratio, 
                'face_shoulder_ratio'
            )
            
            # 임계값
            cheek_threshold = criteria['primary_conditions']['cheek_distance_baseline_change_percent']['threshold_percent']
            ratio_threshold = criteria['primary_conditions']['face_shoulder_ratio_baseline_change_percent']['threshold_percent']
            
            # 조건 확인
            cheek_triggered = cheek_change >= cheek_threshold
            ratio_triggered = ratio_change >= ratio_threshold
            
            # 점수 계산 (0~1)
            cheek_score = self._normalize_score(cheek_change / cheek_threshold, min_val=0, max_val=2.0)
            ratio_score = self._normalize_score(ratio_change / ratio_threshold, min_val=0, max_val=2.0)
            
            likelihood = 0.6 * cheek_score + 0.4 * ratio_score
            triggered = cheek_triggered and ratio_triggered  # 둘 다 만족
            
            logger.debug(
                f"[거북목] cheek_change={cheek_change:.1f}% (threshold={cheek_threshold}%), "
                f"ratio_change={ratio_change:.1f}% (threshold={ratio_threshold}%), "
                f"triggered={triggered}, likelihood={likelihood:.2f}"
            )
            
            return {
                'likelihood': likelihood,
                'triggered': triggered,
                'details': {
                    'cheek_change_percent': cheek_change,
                    'ratio_change_percent': ratio_change,
                    'cheek_threshold': cheek_threshold,
                    'ratio_threshold': ratio_threshold
                }
            }
        
        except Exception as e:
            logger.error(f"거북목 판정 실패: {e}")
            return {'likelihood': 0.0, 'triggered': False, 'details': {}}
    
    def _judge_recline(self, indicators: PostureIndicators) -> Dict[str, any]:
        """
        기댄 자세 판정
        
        조건:
        - cheek_distance 감소 (얼굴이 카메라에서 멀어짐)
        """
        try:
            criteria = self.config.get_posture_type_config(PostureType.RECLINE.value)
            
            cheek_change = self.baseline_manager.calculate_change_percentage(
                indicators.cheek_distance, 
                'cheek_distance'
            )
            
            # 임계값 (음수)
            cheek_threshold = criteria['primary_conditions']['cheek_distance_baseline_change_percent']['threshold_percent']
            
            # 조건 확인 (음수여야 함)
            triggered = cheek_change <= -cheek_threshold
            
            # 점수 계산
            cheek_score = self._normalize_score(abs(cheek_change) / cheek_threshold, min_val=0, max_val=2.0)
            
            likelihood = cheek_score
            
            logger.debug(
                f"[기댄자세] cheek_change={cheek_change:.1f}% (threshold=-{cheek_threshold}%), "
                f"triggered={triggered}, likelihood={likelihood:.2f}"
            )
            
            return {
                'likelihood': likelihood,
                'triggered': triggered,
                'details': {
                    'cheek_change_percent': cheek_change,
                    'threshold': cheek_threshold
                }
            }
        
        except Exception as e:
            logger.error(f"기댄 자세 판정 실패: {e}")
            return {'likelihood': 0.0, 'triggered': False, 'details': {}}
    
    def _judge_crossed_leg(self, indicators: PostureIndicators) -> Dict[str, any]:
        """
        다리 꼰 자세 추정 판정
        
        조건:
        - abs(shoulder_tilt_deg) > 임계값
        """
        try:
            criteria = self.config.get_posture_type_config(PostureType.CROSSED_LEG.value)
            
            shoulder_tilt = abs(indicators.shoulder_tilt_deg)
            threshold = criteria['primary_conditions']['abs_shoulder_tilt_deg']['threshold']
            
            # 조건 확인
            triggered = shoulder_tilt > threshold
            
            # 점수 계산
            tilt_score = self._normalize_score(shoulder_tilt / threshold, min_val=0, max_val=2.0)
            
            likelihood = tilt_score
            
            logger.debug(
                f"[다리꼰자세] shoulder_tilt={shoulder_tilt:.1f}° (threshold={threshold}°), "
                f"triggered={triggered}, likelihood={likelihood:.2f}"
            )
            
            return {
                'likelihood': likelihood,
                'triggered': triggered,
                'details': {
                    'shoulder_tilt_deg': indicators.shoulder_tilt_deg,
                    'threshold': threshold
                }
            }
        
        except Exception as e:
            logger.error(f"다리 꼰 자세 판정 실패: {e}")
            return {'likelihood': 0.0, 'triggered': False, 'details': {}}
    
    def _judge_chin_rest(self, indicators: PostureIndicators) -> Dict[str, any]:
        """
        턱 괸 자세 추정 판정
        
        조건:
        - eye_line_tilt >= 임계값
        - shoulder_tilt >= 임계값
        - hand_near_face 또는 chin_occlusion > 임계값
        """
        try:
            criteria = self.config.get_posture_type_config(PostureType.CHIN_REST.value)
            
            eye_threshold = criteria['primary_conditions']['eye_line_tilt_deg']['threshold']
            shoulder_threshold = criteria['primary_conditions']['shoulder_tilt_deg']['threshold']
            
            # 조건 확인
            eye_triggered = abs(indicators.eye_line_tilt) >= eye_threshold
            shoulder_triggered = abs(indicators.shoulder_tilt_deg) >= shoulder_threshold
            hand_triggered = indicators.hand_near_face or indicators.chin_occlusion > 0.2
            
            # 점수 계산
            eye_score = self._normalize_score(
                abs(indicators.eye_line_tilt) / eye_threshold if eye_threshold > 0 else 0,
                min_val=0, max_val=2.0
            )
            shoulder_score = self._normalize_score(
                abs(indicators.shoulder_tilt_deg) / shoulder_threshold if shoulder_threshold > 0 else 0,
                min_val=0, max_val=2.0
            )
            hand_score = 1.0 if indicators.hand_near_face else min(indicators.chin_occlusion / 0.25, 1.0)
            
            likelihood = 0.35 * eye_score + 0.2 * shoulder_score + 0.45 * hand_score
            triggered = (eye_triggered or shoulder_triggered) and hand_triggered
            
            logger.debug(
                f"[턱괸자세] eye_line_tilt={abs(indicators.eye_line_tilt):.1f}° (threshold={eye_threshold}°), "
                f"hand_triggered={hand_triggered}, chin_occlusion={indicators.chin_occlusion:.2f}, "
                f"triggered={triggered}, likelihood={likelihood:.2f}"
            )
            
            return {
                'likelihood': likelihood,
                'triggered': triggered,
                'details': {
                    'eye_line_tilt': indicators.eye_line_tilt,
                    'shoulder_tilt': indicators.shoulder_tilt_deg,
                    'hand_near_face': indicators.hand_near_face,
                    'chin_occlusion': indicators.chin_occlusion
                }
            }
        
        except Exception as e:
            logger.error(f"턱 괸 자세 판정 실패: {e}")
            return {'likelihood': 0.0, 'triggered': False, 'details': {}}
    
    def accumulate_frame(self, judgment: PostureJudgmentResult):
        """
        프레임 판정 결과 누적
        
        Args:
            judgment: PostureJudgmentResult
        """
        # 각 자세별로 triggered 상태일 때만 누적
        if judgment.forward_head_triggered:
            self.posture_history[PostureType.FORWARD_HEAD.value] += 1
        else:
            self.posture_history[PostureType.FORWARD_HEAD.value] = 0
        
        if judgment.recline_triggered:
            self.posture_history[PostureType.RECLINE.value] += 1
        else:
            self.posture_history[PostureType.RECLINE.value] = 0
        
        if judgment.crossed_leg_triggered:
            self.posture_history[PostureType.CROSSED_LEG.value] += 1
        else:
            self.posture_history[PostureType.CROSSED_LEG.value] = 0
        
        if judgment.chin_rest_triggered:
            self.posture_history[PostureType.CHIN_REST.value] += 1
        else:
            self.posture_history[PostureType.CHIN_REST.value] = 0
    
    def get_confirmed_posture(self, fps: int = 30) -> Optional[str]:
        """
        지속시간 조건을 만족한 자세 반환
        
        Args:
            fps: FPS
            
        Returns:
            자세명 또는 None
        """
        confirmed = None
        max_duration = 0
        
        for posture_type in PostureType:
            frame_count = self.posture_history[posture_type.value]
            
            # 지속시간 조건 확인
            criteria = self.config.get_posture_type_config(posture_type.value)
            sustain_seconds = criteria.get('sustain_seconds', 2)
            sustain_frames = int(sustain_seconds * fps)
            
            if frame_count >= sustain_frames:
                duration = frame_count
                if duration > max_duration:
                    max_duration = duration
                    confirmed = posture_type.value
        
        if confirmed:
            logger.info(f"확정 자세: {confirmed} (지속: {max_duration / fps:.1f}초)")
        
        return confirmed
    
    def _normalize_score(
        self, 
        value: float, 
        min_val: float = 0.0, 
        max_val: float = 1.0
    ) -> float:
        """
        값을 0~1 범위로 정규화
        
        Args:
            value: 값
            min_val: 최솟값
            max_val: 최댓값
            
        Returns:
            정규화된 값 (0~1)
        """
        normalized = (value - min_val) / (max_val - min_val)
        return float(np.clip(normalized, 0.0, 1.0))
    
    def reset_history(self):
        """자세 누적 히스토리 초기화"""
        for key in self.posture_history:
            self.posture_history[key] = 0
        logger.info("자세 누적 히스토리 초기화 완료")


def create_judgment_engine(
    config: ConfigManager, 
    baseline_manager: BaselineManager
) -> JudgmentEngine:
    """판정 엔진 생성 (팩토리 함수)"""
    return JudgmentEngine(config, baseline_manager)
