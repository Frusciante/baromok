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
    EYE_CLOSE = "eye_close"  # 화면과 눈 거리 가까움 (홍채 기반)
    TURNED_HEAD = "turned_head"  # 고개 돌린 자세 (Yaw)
    SIDE_TILT = "side_tilt"  # 고개 기울인 자세 (Roll)


@dataclass
class PostureJudgmentResult:
    """단일 프레임 판정 결과"""

    forward_head_likelihood: float  # 0~1
    forward_head_triggered: bool
    recline_likelihood: float
    recline_triggered: bool
    chin_rest_likelihood: float
    chin_rest_triggered: bool
    eye_close_likelihood: float
    eye_close_triggered: bool
    turned_head_likelihood: float
    turned_head_triggered: bool
    side_tilt_likelihood: float
    side_tilt_triggered: bool
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
            "chin_rest": {"eye": 0.35, "shoulder": 0.2, "neck": 0.15, "hand": 0.3},
            "eye_close": {"distance": 1.0}
        })
        
        # 기본 감도 및 보정 계수
        sensitivities = scoring_config.get("sensitivities", {})
        
        # 기술 사양서 기준: Recline 4% (0.04), Forward Head 10% (0.10)
        self.forward_head_sensitivity = sensitivities.get("forward_head", 0.10)
        self.recline_sensitivity = sensitivities.get("recline", 0.04)
        self.neck_offset_sensitivity = sensitivities.get("neck_offset", 10.0)
        
        # 스코어링 앵커 (감도 도달 시 부여할 점수)
        self.warning_anchor = scoring_config.get("warning_anchor", 0.5)

        # 자세별 프레임 누적 횟수 / 시작시간 / 활성 지속시간 초기화
        self.posture_history: Dict[str, int] = {
            pt.value: 0 for pt in PostureType
        }

        self.posture_start_times: Dict[str, Optional[float]] = {
            pt.value: None for pt in PostureType
        }

        self.posture_active_durations: Dict[str, float] = {
            pt.value: 0.0 for pt in PostureType
        }

        self.last_confirmed_posture: Optional[str] = None
        
        # EMA 필터 (설정에서 alpha 값 로드)
        ema_alpha = self.config.get_posture_criteria().get("filters", {}).get("ema", {}).get("alpha", 0.15)
        # EMA 필터을 모든 정의된 자세 유형에 대해 동적으로 생성
        self.likes_filters = {pt.value: EMAFilter(alpha=ema_alpha) for pt in PostureType}

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
            return PostureJudgmentResult(
                forward_head_likelihood=0.0,
                forward_head_triggered=False,
                recline_likelihood=0.0,
                recline_triggered=False,
                chin_rest_likelihood=0.0,
                chin_rest_triggered=False,
                eye_close_likelihood=0.0,
                eye_close_triggered=False,
                turned_head_likelihood=0.0,
                turned_head_triggered=False,
                side_tilt_likelihood=0.0,
                side_tilt_triggered=False,
                dominant_posture=None,
                timestamp=indicators.timestamp,
            )

        # RANSAC 모델을 통한 기대 광대 거리 산출
        has_shoulders = indicators.shoulder_width is not None
        expected_cheek = 0.0
        deviation = 0.0
        
        if has_shoulders:
            expected_cheek = max(1e-6, self.baseline_manager.get_expected_cheek(indicators.shoulder_width))
            measured_cheek = indicators.cheek_distance
            # 편차 계산 (Deviation)
            deviation = (measured_cheek - expected_cheek) / expected_cheek

        # 각 자세별 판정
        # 어깨가 필요한 자세는 어깨가 있을 때만 판정
        if has_shoulders:
            forward_head_raw = self._judge_forward_head(indicators, deviation)
            recline_raw = self._judge_recline(indicators, deviation)
        else:
            forward_head_raw = {"likelihood": 0.0, "triggered": False}
            recline_raw = {"likelihood": 0.0, "triggered": False}
            
        chin_rest_raw = self._judge_chin_rest(indicators)
        eye_close_raw = self._judge_eye_close(indicators)
        turned_head_raw = self._judge_turned_head(indicators)
        side_tilt_raw = self._judge_side_tilt(indicators)
        
        # Likelihood Smoothing
        forward_head_like = self.likes_filters[PostureType.FORWARD_HEAD.value].process(forward_head_raw["likelihood"])
        recline_like = self.likes_filters[PostureType.RECLINE.value].process(recline_raw["likelihood"])
        chin_rest_like = self.likes_filters[PostureType.CHIN_REST.value].process(chin_rest_raw["likelihood"])
        eye_close_like = self.likes_filters[PostureType.EYE_CLOSE.value].process(eye_close_raw["likelihood"])
        turned_head_like = self.likes_filters[PostureType.TURNED_HEAD.value].process(turned_head_raw["likelihood"])
        side_tilt_like = self.likes_filters[PostureType.SIDE_TILT.value].process(side_tilt_raw["likelihood"])

        warning_threshold = self.config.get_state_machine_config().get("thresholds", {}).get("warning", 0.45)

        candidates = {
            PostureType.FORWARD_HEAD.value: {"likelihood": forward_head_like, "triggered": forward_head_like >= warning_threshold},
            PostureType.RECLINE.value: {"likelihood": recline_like, "triggered": recline_like >= warning_threshold},
            PostureType.CHIN_REST.value: {"likelihood": chin_rest_like, "triggered": chin_rest_like >= warning_threshold},
            PostureType.EYE_CLOSE.value: {"likelihood": eye_close_like, "triggered": eye_close_like >= warning_threshold},
            PostureType.TURNED_HEAD.value: {"likelihood": turned_head_like, "triggered": turned_head_like >= warning_threshold},
            PostureType.SIDE_TILT.value: {"likelihood": side_tilt_like, "triggered": side_tilt_like >= warning_threshold},
        }

        triggered_candidates = {
            posture_type: result["likelihood"]
            for posture_type, result in candidates.items()
            if result["triggered"]
        }

        dominant_posture = None
        if triggered_candidates:
            # 여러 자세가 트리거된 경우 가장 높은 확률 선택
            dominant_posture = max(triggered_candidates, key=triggered_candidates.get)
        else:
            # 트리거되지 않았더라도 정보 제공을 위해 가장 높은 가능성 선택 (0.2 이상)
            likes = {
                PostureType.FORWARD_HEAD.value: forward_head_like,
                PostureType.RECLINE.value: recline_like,
                PostureType.CHIN_REST.value: chin_rest_like,
                PostureType.EYE_CLOSE.value: eye_close_like,
                PostureType.TURNED_HEAD.value: turned_head_like,
                PostureType.SIDE_TILT.value: side_tilt_like,
            }
            best_posture = max(likes, key=likes.get)
            if likes[best_posture] >= 0.2:
                dominant_posture = best_posture

        return PostureJudgmentResult(
            forward_head_likelihood=forward_head_like,
            forward_head_triggered=candidates[PostureType.FORWARD_HEAD.value]["triggered"],
            recline_likelihood=recline_like,
            recline_triggered=candidates[PostureType.RECLINE.value]["triggered"],
            chin_rest_likelihood=chin_rest_like,
            chin_rest_triggered=candidates[PostureType.CHIN_REST.value]["triggered"],
            eye_close_likelihood=eye_close_like,
            eye_close_triggered=candidates[PostureType.EYE_CLOSE.value]["triggered"],
            turned_head_likelihood=turned_head_like,
            turned_head_triggered=candidates[PostureType.TURNED_HEAD.value]["triggered"],
            side_tilt_likelihood=side_tilt_like,
            side_tilt_triggered=candidates[PostureType.SIDE_TILT.value]["triggered"],
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
            
            # 눈/광대 대칭 확인 (0.08 -> 0.12로 완화하여 너무 민감하게 차단되지 않도록 함)
            eye_sym_excessive = indicators.eye_symmetry_ratio > guards.get("max_eye_symmetry_ratio", 0.12)
            cheek_sym_excessive = indicators.cheek_symmetry_ratio > guards.get("max_cheek_symmetry_ratio", 0.12)
            chin_offset_excessive = indicators.chin_alignment_offset > guards.get("max_chin_alignment_offset", 0.15)

            if side_tilt_excessive or shoulder_tilt_excessive or eye_sym_excessive or cheek_sym_excessive or chin_offset_excessive:
                return {"likelihood": 0.0, "triggered": False}

            # 3. 기댄 자세 오판 방지 가드
            # 어깨가 baseline 대비 크게 감소한 경우 → 몸 전체가 뒤로 빠진 기댄 자세일 가능성이 높음.
            # 이때 양수 deviation은 머리가 앞으로 나온 게 아니라 어깨가 뒤로 빠진 결과이므로 거북목으로 판정하지 않음.
            if indicators.shoulder_width is not None:
                sw_change_pct = self.baseline_manager.calculate_change_percentage(
                    indicators.shoulder_width, "shoulder_width"
                )
                recline_sw_threshold = guards.get("max_shoulder_decrease_pct", -15.0)
                if sw_change_pct < recline_sw_threshold:
                    return {"likelihood": 0.0, "triggered": False}

            # 4. 점수 계산
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
            
            # 눈/광대 대칭 및 턱 정렬 확인 (0.08 -> 0.12로 완화)
            eye_sym_excessive = indicators.eye_symmetry_ratio > guards.get("max_eye_symmetry_ratio", 0.12)
            cheek_sym_excessive = indicators.cheek_symmetry_ratio > guards.get("max_cheek_symmetry_ratio", 0.12)
            chin_offset_excessive = indicators.chin_alignment_offset > guards.get("max_chin_alignment_offset", 0.15)

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
            
            # 어깨 관련 임계값 (어깨가 있을 때만 사용)
            shoulder_threshold = criteria["primary_conditions"].get("shoulder_tilt_deg", {}).get("threshold", 10.0)

            # 손 관련 트리거
            hand_triggered = (indicators.hand_near_face or indicators.chin_occlusion > 0.25)
            if not hand_triggered:
                return {"likelihood": 0.0, "triggered": False}

            eye_score = self._normalize_score(abs(indicators.eye_line_tilt) / eye_threshold, min_val=0, max_val=2.0)
            
            # 어깨 기반 지표 (Optional 처리)
            shoulder_score = 0.0
            neck_offset_score = 0.0
            
            if indicators.shoulder_tilt_deg is not None:
                shoulder_score = self._normalize_score(abs(indicators.shoulder_tilt_deg) / shoulder_threshold, min_val=0, max_val=2.0)
            
            if indicators.neck_offset is not None:
                neck_offset_change = self.baseline_manager.calculate_change_percentage(indicators.neck_offset, "neck_offset")
                if neck_offset_change > 0:
                    neck_offset_score = self._normalize_score(neck_offset_change / self.neck_offset_sensitivity, min_val=0.0, max_val=2.0)
            
            w = self.weights.get("chin_rest", {})
            
            # 가중치 재계산 (어깨가 없으면 얼굴/손 비중을 높임)
            has_sh = indicators.shoulder_width is not None
            w_eye = w.get("eye", 0.35)
            w_sh = w.get("shoulder", 0.2) if has_sh else 0.0
            w_neck = w.get("neck", 0.15) if has_sh else 0.0
            w_hand = w.get("hand", 0.3)
            
            total_w = w_eye + w_sh + w_neck + w_hand
            if total_w > 0:
                likelihood = (w_eye * eye_score + w_sh * shoulder_score + w_neck * neck_offset_score + w_hand * indicators.hand_face_score) / total_w
            else:
                likelihood = 0.0

            return {"likelihood": float(np.clip(likelihood, 0.0, 1.0)), "triggered": False}

        except Exception as e:
            logger.error(f"턱 괸 자세 판정 실패: {e}")
            return {"likelihood": 0.0, "triggered": False}

    def _judge_eye_close(self, indicators: PostureIndicators) -> Dict[str, Any]:
        """화면과 눈 거리 가까움 판단 (홍채 기반 거리 측정)"""
        try:
            # 즉시 경고 플래그가 켜져 있으면 높은 우선순위
            if indicators.eye_close_warning:
                return {"likelihood": 1.0, "triggered": True}

            dist_cm = indicators.eye_screen_distance_cm
            # 구성에서 임계값 확인
            try:
                cfg = self.config.get_posture_criteria().get("eye_monitoring", {})
                threshold = float(cfg.get("distance_threshold_cm", 45.0))
            except Exception:
                threshold = 45.0

            if dist_cm is None:
                return {"likelihood": 0.0, "triggered": False}

            # 거리 임계값보다 작을수록 심각: normalize (threshold - d)/threshold
            severity = max(0.0, (threshold - float(dist_cm)) / max(1e-6, threshold))
            return {"likelihood": float(np.clip(severity, 0.0, 1.0)), "triggered": False}

        except Exception as e:
            logger.error(f"eye_close 판정 실패: {e}")
            return {"likelihood": 0.0, "triggered": False}

    def _judge_turned_head(self, indicators: PostureIndicators) -> Dict[str, Any]:
        """고개 돌린 자세 판정 (Yaw)"""
        try:
            # 설정에서 임계값 로드 (없으면 기본값 사용)
            criteria = self.config.get_posture_type_config(PostureType.TURNED_HEAD.value)
            th_config = criteria.get("thresholds", {})
            
            eye_th = th_config.get("eye_symmetry", 0.4)
            cheek_th = th_config.get("cheek_symmetry", 0.4)
            chin_th = th_config.get("chin_alignment", 0.3)
            
            # 각 지표별 점수 계산
            eye_score = self._normalize_score(indicators.eye_symmetry_ratio / eye_th, min_val=0.0, max_val=2.0)
            cheek_score = self._normalize_score(indicators.cheek_symmetry_ratio / cheek_th, min_val=0.0, max_val=2.0)
            chin_score = self._normalize_score(indicators.chin_alignment_offset / chin_th, min_val=0.0, max_val=2.0)
            
            # 가중 합산 (전체적인 균형 중시)
            likelihood = 0.4 * eye_score + 0.4 * cheek_score + 0.2 * chin_score
            
            return {"likelihood": float(np.clip(likelihood, 0.0, 1.0)), "triggered": False}

        except Exception as e:
            logger.error(f"고개 돌린 자세 판정 실패: {e}")
            return {"likelihood": 0.0, "triggered": False}

    def _judge_side_tilt(self, indicators: PostureIndicators) -> Dict[str, Any]:
        """고개 기울인 자세 판정 (Roll)"""
        try:
            # 설정에서 임계값 로드
            criteria = self.config.get_posture_type_config(PostureType.SIDE_TILT.value)
            primary_th = criteria.get("primary_conditions", {}).get("eye_line_tilt_deg", {}).get("threshold", 10.0)
            
            tilt = abs(indicators.eye_line_tilt)
            
            if tilt < 3.0: # 미세한 기울임은 무시
                return {"likelihood": 0.0, "triggered": False}
                
            # 점수 계산 (임계값 대비 비율)
            score = tilt / primary_th
            
            return {"likelihood": float(np.clip(score, 0.0, 1.0)), "triggered": False}

        except Exception as e:
            logger.error(f"고개 기울인 자세 판정 실패: {e}")
            return {"likelihood": 0.0, "triggered": False}

    def accumulate_frame(self, judgment: PostureJudgmentResult, current_timestamp: Optional[float] = None):
        """프레임 판정 결과 누적"""
        if current_timestamp is None:
            current_timestamp = judgment.timestamp

        triggered_map = {
            PostureType.FORWARD_HEAD.value: judgment.forward_head_triggered,
            PostureType.RECLINE.value: judgment.recline_triggered,
            PostureType.CHIN_REST.value: judgment.chin_rest_triggered,
            PostureType.EYE_CLOSE.value: judgment.eye_close_triggered,
            PostureType.TURNED_HEAD.value: judgment.turned_head_triggered,
            PostureType.SIDE_TILT.value: judgment.side_tilt_triggered,
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
        denom = max_val - min_val
        if abs(denom) < 1e-9:
            return 0.0
        normalized = (value - min_val) / denom
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
