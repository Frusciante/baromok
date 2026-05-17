"""
판정 엔진

자세 판정 로직 구현 (3가지 자세)
"""

import numpy as np
from typing import Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum

from src.config import ConfigManager
from src.core.indicator_calculator import PostureIndicators
from src.core.baseline_manager import BaselineManager
from src.utils.logger import get_logger
from src.utils.helpers import NormalizationHelper, EMAFilter

logger = get_logger(__name__)


class PostureType(Enum):
    """자세 유형"""

    FORWARD_HEAD = "forward_head"  # 거북목
    RECLINE = "recline"  # 기댄 자세
    CHIN_REST = "chin_rest_estimated"  # 턱 괸 자세


@dataclass
class PostureJudgmentResult:
    """단일 프레임 판정 결과"""

    forward_head_likelihood: float  # 0~1
    forward_head_triggered: bool
    recline_likelihood: float
    recline_triggered: bool
    chin_rest_likelihood: float
    chin_rest_triggered: bool
    dominant_posture: Optional[str]  # triggered된 자세 중 가장 확률이 높은 자세
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

        # 설정에서 가중치 및 임계값 로드
        scoring_config = self.config.get_frame_scoring_config()
        self.weights = scoring_config.get("likelihood_weights", {
            "forward_head": {"deviation": 1.0},
            "recline": {"deviation": 1.0},
            "chin_rest": {"eye": 0.35, "shoulder": 0.2, "neck": 0.15, "hand": 0.3}
        })
        
        # 기본 감도 및 보정 계수
        sensitivities = scoring_config.get("sensitivities", {})
        
        # 기술 사양서 기준: Recline 4% (0.04), Forward Head 10% (0.10)
        self.forward_head_sensitivity = sensitivities.get("forward_head", 0.10)
        self.recline_sensitivity = sensitivities.get("recline", 0.04)
        self.neck_offset_sensitivity = sensitivities.get("neck_offset", 10.0)
        
        # 스코어링 앵커 (감도 도달 시 부여할 점수)
        self.warning_anchor = scoring_config.get("warning_anchor", 0.5)

        # 자세별 프레임 누적 횟수
        self.posture_history: Dict[str, int] = {
            PostureType.FORWARD_HEAD.value: 0,
            PostureType.RECLINE.value: 0,
            PostureType.CHIN_REST.value: 0,
        }

        # 자세별 실제 지속 시간 계산용 타임스탬프
        self.posture_start_times: Dict[str, Optional[float]] = {
            PostureType.FORWARD_HEAD.value: None,
            PostureType.RECLINE.value: None,
            PostureType.CHIN_REST.value: None,
        }

        self.posture_active_durations: Dict[str, float] = {
            PostureType.FORWARD_HEAD.value: 0.0,
            PostureType.RECLINE.value: 0.0,
            PostureType.CHIN_REST.value: 0.0,
        }

        self.last_confirmed_posture: Optional[str] = None
        
        # EMA 필터 (설정에서 alpha 값 로드)
        ema_alpha = self.config.get_posture_criteria().get("filters", {}).get("ema", {}).get("alpha", 0.15)
        self.likes_filters = {
            PostureType.FORWARD_HEAD.value: EMAFilter(alpha=ema_alpha),
            PostureType.RECLINE.value: EMAFilter(alpha=ema_alpha),
            PostureType.CHIN_REST.value: EMAFilter(alpha=ema_alpha),
        }

        logger.info("JudgmentEngine 초기화 완료")

    def update_sensitivities(self, forward_head: float, recline: float):
        """사용자 정의 감도 업데이트"""
        self.forward_head_sensitivity = forward_head
        self.recline_sensitivity = recline
        logger.info(f"판정 엔진 감도 업데이트: 거북목={forward_head:.3f}, 기댄자세={recline:.3f}")

    def judge_single_frame(
        self, indicators: PostureIndicators
    ) -> PostureJudgmentResult:
        """
        단일 프레임에 대한 자세 판정
        """
        # Baseline 정보
        baseline = self.baseline_manager.get_baseline_metrics()
        if not baseline or not baseline.metrics:
            return PostureJudgmentResult(0, False, 0, False, 0, False, None, indicators.timestamp)

        # RANSAC 모델을 통한 기대 광대 거리 산출
        expected_cheek = max(1e-6, self.baseline_manager.get_expected_cheek(indicators.shoulder_width))
        measured_cheek = indicators.cheek_distance
        
        # 편차 계산 (Deviation)
        deviation = (measured_cheek - expected_cheek) / expected_cheek

        # 각 자세별 판정
        forward_head_raw = self._judge_forward_head(indicators, deviation)
        recline_raw = self._judge_recline(indicators, deviation)
        chin_rest_raw = self._judge_chin_rest(indicators)
        
        # Likelihood Smoothing
        forward_head_like = self.likes_filters[PostureType.FORWARD_HEAD.value].process(forward_head_raw["likelihood"])
        recline_like = self.likes_filters[PostureType.RECLINE.value].process(recline_raw["likelihood"])
        chin_rest_like = self.likes_filters[PostureType.CHIN_REST.value].process(chin_rest_raw["likelihood"])

        warning_threshold = self.config.get_state_machine_config().get("thresholds", {}).get("warning", 0.45)

        candidates = {
            PostureType.FORWARD_HEAD.value: {"likelihood": forward_head_like, "triggered": forward_head_like >= warning_threshold},
            PostureType.RECLINE.value: {"likelihood": recline_like, "triggered": recline_like >= warning_threshold},
            PostureType.CHIN_REST.value: {"likelihood": chin_rest_like, "triggered": chin_rest_like >= warning_threshold},
        }

        triggered_candidates = {
            posture_type: result["likelihood"]
            for posture_type, result in candidates.items()
            if result["triggered"]
        }

        dominant_posture = None
        if triggered_candidates:
            dominant_posture = max(triggered_candidates, key=triggered_candidates.get)

        return PostureJudgmentResult(
            forward_head_likelihood=forward_head_like,
            forward_head_triggered=candidates[PostureType.FORWARD_HEAD.value]["triggered"],
            recline_likelihood=recline_like,
            recline_triggered=candidates[PostureType.RECLINE.value]["triggered"],
            chin_rest_likelihood=chin_rest_like,
            chin_rest_triggered=candidates[PostureType.CHIN_REST.value]["triggered"],
            dominant_posture=dominant_posture,
            timestamp=indicators.timestamp,
        )

    def _judge_forward_head(self, indicators: PostureIndicators, deviation: float) -> Dict[str, Any]:
        """거북목 자세 판정"""
        try:
            criteria = self.config.get_posture_type_config(PostureType.FORWARD_HEAD.value)
            primary_th = criteria["primary_conditions"]["deviation"]["threshold"]
            guards = criteria.get("guards", {})

            # 1. 기본 방향 확인
            if deviation <= primary_th:
                return {"likelihood": 0.0, "triggered": False}
                
            # 2. 고개 기울임 및 중앙 정렬(Symmetry) 가드
            side_tilt_excessive = abs(indicators.eye_line_tilt) > guards.get("max_eye_tilt", 12.0)
            shoulder_tilt_excessive = abs(indicators.shoulder_tilt_deg) > guards.get("max_shoulder_tilt", 10.0)
            
            # 눈/광대 대칭 확인
            eye_sym_excessive = indicators.eye_symmetry_ratio > guards.get("max_eye_symmetry_ratio", 0.15)
            cheek_sym_excessive = indicators.cheek_symmetry_ratio > guards.get("max_cheek_symmetry_ratio", 0.15)
            chin_offset_excessive = indicators.chin_alignment_offset > guards.get("max_chin_alignment_offset", 0.05)
            
            if side_tilt_excessive or shoulder_tilt_excessive or eye_sym_excessive or cheek_sym_excessive or chin_offset_excessive:
                return {"likelihood": 0.0, "triggered": False}

            # 3. 점수 계산
            score = (deviation / self.forward_head_sensitivity) * self.warning_anchor
            
            return {"likelihood": float(np.clip(score, 0.0, 1.0)), "triggered": False}

        except Exception as e:
            logger.error(f"거북목 판정 실패: {e}")
            return {"likelihood": 0.0, "triggered": False}

    def _judge_recline(self, indicators: PostureIndicators, deviation: float) -> Dict[str, Any]:
        """기댄 자세 판정"""
        try:
            criteria = self.config.get_posture_type_config(PostureType.RECLINE.value)
            primary_th = criteria["primary_conditions"]["deviation"]["threshold"]
            guards = criteria.get("guards", {})

            # 1. 기본 방향 확인
            if deviation >= primary_th:
                return {"likelihood": 0.0, "triggered": False}
                
            # 2. 고개 기울임 및 중앙 정렬(Symmetry) 가드
            side_tilt_excessive = abs(indicators.eye_line_tilt) > guards.get("max_eye_tilt", 12.0)
            shoulder_tilt_excessive = abs(indicators.shoulder_tilt_deg) > guards.get("max_shoulder_tilt", 10.0)
            
            # 눈/광대 대칭 및 턱 정렬 확인
            eye_sym_excessive = indicators.eye_symmetry_ratio > guards.get("max_eye_symmetry_ratio", 0.15)
            cheek_sym_excessive = indicators.cheek_symmetry_ratio > guards.get("max_cheek_symmetry_ratio", 0.15)
            chin_offset_excessive = indicators.chin_alignment_offset > guards.get("max_chin_alignment_offset", 0.05)

            if side_tilt_excessive or shoulder_tilt_excessive or eye_sym_excessive or cheek_sym_excessive or chin_offset_excessive:
                return {"likelihood": 0.0, "triggered": False}

            # 3. 점수 계산
            score = (abs(deviation) / self.recline_sensitivity) * self.warning_anchor
            
            return {"likelihood": float(np.clip(score, 0.0, 1.0)), "triggered": False}

        except Exception as e:
            logger.error(f"기댄 자세 판정 실패: {e}")
            return {"likelihood": 0.0, "triggered": False}

    def _judge_chin_rest(self, indicators: PostureIndicators) -> Dict[str, Any]:
        """턱 괸 자세 판정"""
        try:
            criteria = self.config.get_posture_type_config(PostureType.CHIN_REST.value)
            eye_threshold = criteria["primary_conditions"]["eye_line_tilt_deg"]["threshold"]
            shoulder_threshold = criteria["primary_conditions"]["shoulder_tilt_deg"]["threshold"]

            # 손 관련 트리거
            hand_triggered = (indicators.hand_near_face or indicators.chin_occlusion > 0.25)
            if not hand_triggered:
                return {"likelihood": 0.0, "triggered": False}

            eye_score = self._normalize_score(abs(indicators.eye_line_tilt) / eye_threshold, min_val=0, max_val=2.0)
            shoulder_score = self._normalize_score(abs(indicators.shoulder_tilt_deg) / shoulder_threshold, min_val=0, max_val=2.0)
            
            neck_offset_change = self.baseline_manager.calculate_change_percentage(indicators.neck_offset, "neck_offset")
            neck_offset_score = self._normalize_score(neck_offset_change / self.neck_offset_sensitivity, min_val=0.0, max_val=2.0) if neck_offset_change > 0 else 0.0
            
            w = self.weights.get("chin_rest", {})
            likelihood = (w.get("eye", 0.35) * eye_score + 
                          w.get("shoulder", 0.2) * shoulder_score + 
                          w.get("neck", 0.15) * neck_offset_score + 
                          w.get("hand", 0.3) * indicators.hand_face_score)

            return {"likelihood": likelihood, "triggered": False}

        except Exception as e:
            logger.error(f"턱 괸 자세 판정 실패: {e}")
            return {"likelihood": 0.0, "triggered": False}

    def accumulate_frame(self, judgment: PostureJudgmentResult, current_timestamp: Optional[float] = None):
        """프레임 판정 결과 누적"""
        if current_timestamp is None:
            current_timestamp = judgment.timestamp

        triggered_map = {
            PostureType.FORWARD_HEAD.value: judgment.forward_head_triggered,
            PostureType.RECLINE.value: judgment.recline_triggered,
            PostureType.CHIN_REST.value: judgment.chin_rest_triggered,
        }

        for posture_type, is_triggered in triggered_map.items():
            if is_triggered:
                self.posture_history[posture_type] += 1
                if self.posture_start_times[posture_type] is None:
                    self.posture_start_times[posture_type] = current_timestamp
                self.posture_active_durations[posture_type] = max(0.0, current_timestamp - self.posture_start_times[posture_type])
            else:
                self.posture_history[posture_type] = 0
                self.posture_start_times[posture_type] = None
                self.posture_active_durations[posture_type] = 0.0

    def get_confirmed_posture(self, fps: int = 30, current_timestamp: Optional[float] = None) -> Optional[str]:
        """지속시간 조건을 만족한 자세 반환"""
        confirmed = None
        max_duration_seconds = 0.0

        for posture_type in PostureType:
            posture_key = posture_type.value
            criteria = self.config.get_posture_type_config(posture_key)
            sustain_seconds = criteria.get("sustain_seconds", 2)

            duration_seconds = self.posture_active_durations.get(posture_key, 0.0)
            start_time = self.posture_start_times.get(posture_key)

            if current_timestamp is not None and start_time is not None:
                duration_seconds = max(duration_seconds, current_timestamp - start_time)

            if duration_seconds >= sustain_seconds:
                if duration_seconds > max_duration_seconds:
                    max_duration_seconds = duration_seconds
                    confirmed = posture_key

        if confirmed and confirmed != self.last_confirmed_posture:
            logger.info(f"확정 자세: {confirmed} (지속: {max_duration_seconds:.1f}초)")

        self.last_confirmed_posture = confirmed
        return confirmed

    def _normalize_score(self, value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """값을 0~1 범위로 정규화"""
        normalized = (value - min_val) / (max_val - min_val)
        return float(np.clip(normalized, 0.0, 1.0))

    def reset_history(self):
        """자세 누적 히스토리 초기화"""
        for key in self.posture_history:
            self.posture_history[key] = 0
            self.posture_start_times[key] = None
            self.posture_active_durations[key] = 0.0
        self.last_confirmed_posture = None
        logger.debug("자세 누적 히스토리 초기화 완료")


def create_judgment_engine(config: ConfigManager, baseline_manager: BaselineManager) -> JudgmentEngine:
    """판정 엔진 생성"""
    return JudgmentEngine(config, baseline_manager)
