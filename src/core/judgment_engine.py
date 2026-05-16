"""
판정 엔진

자세 판정 로직 구현 (4가지 자세)
"""

import numpy as np
from typing import Any, Dict, Optional
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

        # 자세별 프레임 누적 횟수
        # 기존 코드와 호환되도록 유지한다.
        self.posture_history: Dict[str, int] = {
            PostureType.FORWARD_HEAD.value: 0,
            PostureType.RECLINE.value: 0,
            PostureType.CROSSED_LEG.value: 0,
            PostureType.CHIN_REST.value: 0,
        }

        # 자세별 실제 지속 시간 계산용 타임스탬프
        # 설정 FPS가 아니라 실제 프레임 처리 시각 기준으로 자세 지속 시간을 계산한다.
        self.posture_start_times: Dict[str, Optional[float]] = {
            PostureType.FORWARD_HEAD.value: None,
            PostureType.RECLINE.value: None,
            PostureType.CROSSED_LEG.value: None,
            PostureType.CHIN_REST.value: None,
        }

        self.posture_active_durations: Dict[str, float] = {
            PostureType.FORWARD_HEAD.value: 0.0,
            PostureType.RECLINE.value: 0.0,
            PostureType.CROSSED_LEG.value: 0.0,
            PostureType.CHIN_REST.value: 0.0,
        }

        self.last_confirmed_posture: Optional[str] = None

        logger.info("JudgmentEngine 초기화 완료")

    def judge_single_frame(
        self, indicators: PostureIndicators
    ) -> PostureJudgmentResult:
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

        # triggered된 자세들만 dominant_posture 후보로 사용
        # likelihood만 보고 dominant_posture를 고르면 조건이 실제로 발동되지 않은 자세가
        # 화면에 표시될 수 있으므로, triggered=True인 자세만 후보로 삼는다.
        candidates = {
            PostureType.FORWARD_HEAD.value: forward_head_result,
            PostureType.RECLINE.value: recline_result,
            PostureType.CROSSED_LEG.value: crossed_leg_result,
            PostureType.CHIN_REST.value: chin_rest_result,
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
            forward_head_likelihood=forward_head_result["likelihood"],
            forward_head_triggered=forward_head_result["triggered"],
            recline_likelihood=recline_result["likelihood"],
            recline_triggered=recline_result["triggered"],
            crossed_leg_likelihood=crossed_leg_result["likelihood"],
            crossed_leg_triggered=crossed_leg_result["triggered"],
            chin_rest_likelihood=chin_rest_result["likelihood"],
            chin_rest_triggered=chin_rest_result["triggered"],
            dominant_posture=dominant_posture,
            timestamp=indicators.timestamp,
        )

    def _judge_forward_head(self, indicators: PostureIndicators) -> Dict[str, Any]:
        """
        거북목 자세 판정

        조건:
        - cheek_distance 증가 (얼굴이 카메라에 가까워짐)
        - face_shoulder_ratio 증가
        """
        try:
            criteria = self.config.get_posture_type_config(
                PostureType.FORWARD_HEAD.value
            )

            cheek_change = self.baseline_manager.calculate_change_percentage(
                indicators.cheek_distance,
                "cheek_distance",
            )

            ratio_change = self.baseline_manager.calculate_change_percentage(
                indicators.face_shoulder_ratio,
                "face_shoulder_ratio",
            )

            # 임계값
            cheek_threshold = criteria["primary_conditions"][
                "cheek_distance_baseline_change_percent"
            ]["threshold_percent"]
            ratio_threshold = criteria["primary_conditions"][
                "face_shoulder_ratio_baseline_change_percent"
            ]["threshold_percent"]

            # 조건 확인
            cheek_triggered = cheek_change >= cheek_threshold
            ratio_triggered = ratio_change >= ratio_threshold

            # 점수 계산 (0~1)
            cheek_score = self._normalize_score(
                cheek_change / cheek_threshold,
                min_val=0,
                max_val=2.0,
            )
            ratio_score = self._normalize_score(
                ratio_change / ratio_threshold,
                min_val=0,
                max_val=2.0,
            )

            likelihood = 0.7 * cheek_score + 0.3 * ratio_score

            side_tilt_excessive = abs(indicators.eye_line_tilt) > 12  # 눈이 12° 이상 기울어지면 좌우 기울임
            shoulder_tilt_excessive = abs(indicators.shoulder_tilt_deg) > 10  # 어깨가 10° 이상 기울어지면 거부
            eye_distance_change = self.baseline_manager.calculate_change_percentage(
                indicators.eye_distance,
                "eye_distance",
            )
            eye_distance_ok = eye_distance_change >= -7  # 측면 회전 시 눈 간 거리 감소를 걸러냄

            triggered = (
                cheek_triggered
                and ratio_triggered
                and eye_distance_ok
                and not side_tilt_excessive  # 과도한 눈 기울임 없음
                and not shoulder_tilt_excessive  # 과도한 어깨 기울임 없음
            )

            logger.debug(
                f"[거북목] cheek_change={cheek_change:.1f}% "
                f"(threshold={cheek_threshold}%), "
                f"ratio_change={ratio_change:.1f}% "
                f"(threshold={ratio_threshold}%), "
                f"eye_distance_change={eye_distance_change:.1f}% (ok={eye_distance_ok}), "
                f"eye_line_tilt={indicators.eye_line_tilt:.1f}° (excessive={side_tilt_excessive}), "
                f"shoulder_tilt={indicators.shoulder_tilt_deg:.1f}° (excessive={shoulder_tilt_excessive}), "
                f"triggered={triggered}, likelihood={likelihood:.2f}"
            )

            return {
                "likelihood": likelihood,
                "triggered": triggered,
                "details": {
                    "cheek_change_percent": cheek_change,
                    "ratio_change_percent": ratio_change,
                    "cheek_threshold": cheek_threshold,
                    "ratio_threshold": ratio_threshold,
                },
            }

        except Exception as e:
            logger.error(f"거북목 판정 실패: {e}")
            return {"likelihood": 0.0, "triggered": False, "details": {}}

    def _judge_recline(self, indicators: PostureIndicators) -> Dict[str, Any]:
        """
        기댄 자세 판정

        조건:
        - cheek_distance 감소 (얼굴이 카메라에서 멀어짐)
        """
        try:
            criteria = self.config.get_posture_type_config(PostureType.RECLINE.value)

            cheek_change = self.baseline_manager.calculate_change_percentage(
                indicators.cheek_distance,
                "cheek_distance",
            )

            # 임계값 (음수)
            cheek_threshold = criteria["primary_conditions"][
                "cheek_distance_baseline_change_percent"
            ]["threshold_percent"]

            ratio_change = self.baseline_manager.calculate_change_percentage(
                indicators.face_shoulder_ratio,
                "face_shoulder_ratio",
            )
            eye_distance_change = self.baseline_manager.calculate_change_percentage(
                indicators.eye_distance,
                "eye_distance",
            )

            side_tilt_excessive = abs(indicators.eye_line_tilt) > 12
            shoulder_tilt_excessive = abs(indicators.shoulder_tilt_deg) > 10
            eye_distance_ok = eye_distance_change >= -8

            # 조건 확인 (음수여야 함)
            triggered = (
                cheek_change <= -cheek_threshold
                and not side_tilt_excessive
                and not shoulder_tilt_excessive
                and eye_distance_ok
            )

            # 점수 계산
            cheek_score = self._normalize_score(
                abs(cheek_change) / cheek_threshold,
                min_val=0,
                max_val=2.0,
            )

            likelihood = cheek_score

            logger.debug(
                f"[기댄자세] cheek_change={cheek_change:.1f}% "
                f"(threshold=-{cheek_threshold}%), "
                f"ratio_change={ratio_change:.1f}%, "
                f"eye_distance_change={eye_distance_change:.1f}% (ok={eye_distance_ok}), "
                f"eye_line_tilt={indicators.eye_line_tilt:.1f}° (excessive={side_tilt_excessive}), "
                f"shoulder_tilt={indicators.shoulder_tilt_deg:.1f}° (excessive={shoulder_tilt_excessive}), "
                f"triggered={triggered}, likelihood={likelihood:.2f}"
            )

            return {
                "likelihood": likelihood,
                "triggered": triggered,
                "details": {
                    "cheek_change_percent": cheek_change,
                    "threshold": cheek_threshold,
                },
            }

        except Exception as e:
            logger.error(f"기댄 자세 판정 실패: {e}")
            return {"likelihood": 0.0, "triggered": False, "details": {}}

    def _judge_crossed_leg(self, indicators: PostureIndicators) -> Dict[str, Any]:
        """
        다리 꼰 자세 추정 판정

        조건:
        - abs(shoulder_tilt_deg) > 임계값
        """
        try:
            criteria = self.config.get_posture_type_config(
                PostureType.CROSSED_LEG.value
            )

            threshold = criteria["primary_conditions"]["abs_shoulder_tilt_deg"][
                "threshold"
            ]

            baseline = self.baseline_manager.get_baseline_metrics()

            # baseline이 있으면 현재 어깨 기울기의 절댓값이 아니라,
            # baseline 대비 어깨 기울기 변화량을 우선 사용한다.
            if baseline is not None and baseline.metrics:
                baseline_tilt = baseline.metrics.get("shoulder_tilt_deg", 0.0)
                shoulder_tilt = abs(indicators.shoulder_tilt_deg - baseline_tilt)
            else:
                baseline_tilt = 0.0
                shoulder_tilt = abs(indicators.shoulder_tilt_deg)

            # 점수 계산
            tilt_score = self._normalize_score(
                shoulder_tilt / threshold,
                min_val=0,
                max_val=2.0,
            )

            likelihood = tilt_score

            head_tilt_excessive = abs(indicators.eye_line_tilt) > 12
            eye_distance_change = self.baseline_manager.calculate_change_percentage(
                indicators.eye_distance,
                "eye_distance",
            )
            eye_turn_excessive = eye_distance_change < -8

            # neck_offset은 baseline이 있을 때만 보조 조건으로 활용한다.
            neck_offset_change = 0.0
            has_valid_neck_offset_baseline = (
                baseline is not None
                and baseline.metrics
                and baseline.metrics.get("neck_offset", 0.0) not in (0, None)
            )

            if has_valid_neck_offset_baseline:
                neck_offset_change = self.baseline_manager.calculate_change_percentage(
                    indicators.neck_offset,
                    "neck_offset",
                )

                # 어깨 기울기 변화 + 목/어깨 정렬 변화가 함께 있을 때만 다리 꼬움 추정
                triggered = (
                    shoulder_tilt > threshold
                    and neck_offset_change > 10
                    and not head_tilt_excessive
                    and not eye_turn_excessive
                )
            else:
                # neck_offset baseline이 없으면 어깨 기울기 변화만 사용하되,
                # 단일 프레임 오탐을 줄이기 위해 기존 threshold보다 조금 더 보수적으로 판단한다.
                triggered = (
                    shoulder_tilt > max(threshold, 8)
                    and not head_tilt_excessive
                    and not eye_turn_excessive
                )

            logger.debug(
                f"[다리꼰자세] current_shoulder_tilt="
                f"{indicators.shoulder_tilt_deg:.1f}°, "
                f"baseline_shoulder_tilt={baseline_tilt:.1f}°, "
                f"tilt_delta={shoulder_tilt:.1f}° (threshold={threshold}°), "
                f"neck_offset_change={neck_offset_change:.1f}%, "
                f"eye_distance_change={eye_distance_change:.1f}% (turn_excessive={eye_turn_excessive}), "
                f"eye_line_tilt={indicators.eye_line_tilt:.1f}° (tilt_excessive={head_tilt_excessive}), "
                f"triggered={triggered}, likelihood={likelihood:.2f}"
            )

            return {
                "likelihood": likelihood,
                "triggered": triggered,
                "details": {
                    "shoulder_tilt_deg": indicators.shoulder_tilt_deg,
                    "baseline_shoulder_tilt_deg": baseline_tilt,
                    "tilt_delta": shoulder_tilt,
                    "neck_offset_change_percent": neck_offset_change,
                    "threshold": threshold,
                },
            }

        except Exception as e:
            logger.error(f"다리 꼰 자세 판정 실패: {e}")
            return {"likelihood": 0.0, "triggered": False, "details": {}}

    def _judge_chin_rest(self, indicators: PostureIndicators) -> Dict[str, Any]:
        """
        턱 괸 자세 추정 판정

        조건:
        - eye_line_tilt >= 임계값
        - shoulder_tilt >= 임계값
        - hand_near_face 또는 chin_occlusion > 임계값
        """
        try:
            criteria = self.config.get_posture_type_config(PostureType.CHIN_REST.value)

            eye_threshold = criteria["primary_conditions"]["eye_line_tilt_deg"][
                "threshold"
            ]
            shoulder_threshold = criteria["primary_conditions"]["shoulder_tilt_deg"][
                "threshold"
            ]

            # 손 관련 트리거: 손이 얼굴 근처이거나 턱 가림이 충분히 큰 경우로 제한
            hand_triggered = (
                indicators.hand_near_face or indicators.chin_occlusion > 0.25
            )

            # 턱 괸 자세는 손/턱 가림 신호가 없으면 아예 후보에서 제외한다.
            # 이 처리를 하지 않으면 눈 기울기나 어깨 기울기만으로 턱 괸 자세가 표시될 수 있다.
            if not hand_triggered:
                logger.debug(
                    f"[턱괸자세] 손/턱 가림 신호 없음: "
                    f"hand_near_face={indicators.hand_near_face}, "
                    f"chin_occlusion={indicators.chin_occlusion:.2f}"
                )

                return {
                    "likelihood": 0.0,
                    "triggered": False,
                    "details": {
                        "reason": "no_hand_or_chin_occlusion",
                        "eye_line_tilt": indicators.eye_line_tilt,
                        "shoulder_tilt": indicators.shoulder_tilt_deg,
                        "hand_near_face": indicators.hand_near_face,
                        "chin_occlusion": indicators.chin_occlusion,
                    },
                }

            # 조건 확인
            eye_triggered = abs(indicators.eye_line_tilt) >= eye_threshold
            shoulder_triggered = abs(indicators.shoulder_tilt_deg) >= shoulder_threshold

            # 점수 계산
            eye_score = self._normalize_score(
                (
                    abs(indicators.eye_line_tilt) / eye_threshold
                    if eye_threshold > 0
                    else 0
                ),
                min_val=0,
                max_val=2.0,
            )
            shoulder_score = self._normalize_score(
                (
                    abs(indicators.shoulder_tilt_deg) / shoulder_threshold
                    if shoulder_threshold > 0
                    else 0
                ),
                min_val=0,
                max_val=2.0,
            )
            hand_score = (
                1.0
                if indicators.hand_near_face
                else min(indicators.chin_occlusion / 0.25, 1.0)
            )

            likelihood = 0.35 * eye_score + 0.2 * shoulder_score + 0.45 * hand_score
            triggered = hand_triggered and (eye_triggered or shoulder_triggered)

            logger.debug(
                f"[턱괸자세] eye_line_tilt={abs(indicators.eye_line_tilt):.1f}° "
                f"(threshold={eye_threshold}°), "
                f"shoulder_tilt={abs(indicators.shoulder_tilt_deg):.1f}° "
                f"(threshold={shoulder_threshold}°), "
                f"hand_triggered={hand_triggered}, "
                f"chin_occlusion={indicators.chin_occlusion:.2f}, "
                f"triggered={triggered}, likelihood={likelihood:.2f}"
            )

            return {
                "likelihood": likelihood,
                "triggered": triggered,
                "details": {
                    "eye_line_tilt": indicators.eye_line_tilt,
                    "shoulder_tilt": indicators.shoulder_tilt_deg,
                    "hand_near_face": indicators.hand_near_face,
                    "chin_occlusion": indicators.chin_occlusion,
                },
            }

        except Exception as e:
            logger.error(f"턱 괸 자세 판정 실패: {e}")
            return {"likelihood": 0.0, "triggered": False, "details": {}}

    def accumulate_frame(
        self,
        judgment: PostureJudgmentResult,
        current_timestamp: Optional[float] = None,
    ):
        """
        프레임 판정 결과 누적

        Args:
            judgment: PostureJudgmentResult
            current_timestamp: 현재 프레임의 실제 timestamp.
                               None이면 judgment.timestamp를 사용한다.
        """
        if current_timestamp is None:
            current_timestamp = judgment.timestamp

        triggered_map = {
            PostureType.FORWARD_HEAD.value: judgment.forward_head_triggered,
            PostureType.RECLINE.value: judgment.recline_triggered,
            PostureType.CROSSED_LEG.value: judgment.crossed_leg_triggered,
            PostureType.CHIN_REST.value: judgment.chin_rest_triggered,
        }

        for posture_type, is_triggered in triggered_map.items():
            if is_triggered:
                self.posture_history[posture_type] += 1

                if self.posture_start_times[posture_type] is None:
                    self.posture_start_times[posture_type] = current_timestamp

                start_time = self.posture_start_times[posture_type]
                self.posture_active_durations[posture_type] = max(
                    0.0,
                    current_timestamp - start_time,
                )
            else:
                self.posture_history[posture_type] = 0
                self.posture_start_times[posture_type] = None
                self.posture_active_durations[posture_type] = 0.0

    def get_confirmed_posture(
        self,
        fps: int = 30,
        current_timestamp: Optional[float] = None,
    ) -> Optional[str]:
        """
        지속시간 조건을 만족한 자세 반환

        Args:
            fps: FPS. 기존 호출부와의 호환성을 위해 유지한다.
                 현재 구현에서는 실제 시간 기반 판단을 우선 사용한다.
            current_timestamp: 현재 프레임의 실제 timestamp.
                               None이면 마지막으로 누적된 duration을 사용한다.

        Returns:
            자세명 또는 None
        """
        confirmed = None
        max_duration_seconds = 0.0

        for posture_type in PostureType:
            posture_key = posture_type.value

            # 지속시간 조건 확인
            criteria = self.config.get_posture_type_config(posture_key)
            sustain_seconds = criteria.get("sustain_seconds", 2)

            duration_seconds = self.posture_active_durations.get(posture_key, 0.0)
            start_time = self.posture_start_times.get(posture_key)

            if current_timestamp is not None and start_time is not None:
                duration_seconds = max(
                    duration_seconds,
                    current_timestamp - start_time,
                )

            if duration_seconds >= sustain_seconds:
                if duration_seconds > max_duration_seconds:
                    max_duration_seconds = duration_seconds
                    confirmed = posture_key

        if confirmed and confirmed != self.last_confirmed_posture:
            logger.info(
                f"확정 자세: {confirmed} " f"(지속: {max_duration_seconds:.1f}초)"
            )

        self.last_confirmed_posture = confirmed

        return confirmed

    def _normalize_score(
        self,
        value: float,
        min_val: float = 0.0,
        max_val: float = 1.0,
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
            self.posture_start_times[key] = None
            self.posture_active_durations[key] = 0.0

        self.last_confirmed_posture = None

        logger.debug("자세 누적 히스토리 초기화 완료")


def create_judgment_engine(
    config: ConfigManager,
    baseline_manager: BaselineManager,
) -> JudgmentEngine:
    """판정 엔진 생성 (팩토리 함수)"""
    return JudgmentEngine(config, baseline_manager)
