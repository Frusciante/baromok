"""
V2 판정 엔진

V2 자세 감지 로직 구현.
V1(JudgmentEngine)과의 차이:
  - 5개 자세 지원 (forward_head_only, forward_head_full, recline, head_tilt, chin_rest)
  - Δ% 기반 판정 (neutral 평균/표준편차 대비)
  - 자세 충돌 시 deviation_score 최대 자세 하나만 표시
  - 어깨 검출률에 따라 보조 지표 동적 활성화
  - 민감도 설정에 따라 confidence 표시 임계 조정

참고: docs/posture_logic_v2_spec.md
"""

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Tuple

import numpy as np

from src.config import ConfigManager
from src.core.calibration_v2 import (
    CalibrationV2Manager,
    IndicatorStats,
    SHOULDER_AVAILABLE_THRESHOLD,
)
from src.core.indicator_calculator import PostureIndicators
from src.utils.helpers import EMAFilter
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 자세 가드 상수 (V1 시스템과 동일 기준)
GUARD_MAX_EYE_TILT_DEG = 12.0
GUARD_MAX_SHOULDER_TILT_DEG = 10.0
GUARD_MAX_EYE_SYMMETRY = 0.15
GUARD_MAX_CHEEK_SYMMETRY = 0.15
GUARD_MAX_CHIN_ALIGNMENT = 0.05

# chin_rest 평가 정규화 분모 (V1 기존값)
CHIN_REST_EYE_NORM_DEG = 8.0
CHIN_REST_SHOULDER_NORM_DEG = 6.0
CHIN_REST_NECK_NORM = 0.05
CHIN_REST_HAND_THRESHOLD = 0.3

# 자세 콜백 타입 — debug recorder 등 외부 hook용
# 운영 환경에서 콜백을 None 으로 두면 추가 오버헤드 없음
FrameCallback = Callable[[PostureIndicators, "JudgmentResultV2"], None]


class PostureTypeV2(Enum):
    """V2 자세 유형"""
    NEUTRAL = "neutral"
    FORWARD_HEAD_ONLY = "forward_head_only"
    FORWARD_HEAD_FULL = "forward_head_full"
    RECLINE = "recline"
    HEAD_TILT = "head_tilt"
    CHIN_REST = "chin_rest"


# 표시 라벨 (V2 spec section 3.1)
DISPLAY_LABELS: Dict[str, str] = {
    PostureTypeV2.NEUTRAL.value: "바른 자세",
    PostureTypeV2.FORWARD_HEAD_ONLY.value: "거북목 경향",
    PostureTypeV2.FORWARD_HEAD_FULL.value: "몸 기울어진 거북목 의심",
    PostureTypeV2.RECLINE.value: "기댄 자세 의심",
    PostureTypeV2.HEAD_TILT.value: "고개 기울임 의심",
    PostureTypeV2.CHIN_REST.value: "턱 괸 자세 의심",
}

# 자세별 지속 시간 (V2 spec section 6.2)
SUSTAIN_SECONDS: Dict[str, float] = {
    PostureTypeV2.FORWARD_HEAD_ONLY.value: 1.5,
    PostureTypeV2.FORWARD_HEAD_FULL.value: 1.5,
    PostureTypeV2.RECLINE.value: 1.5,
    PostureTypeV2.HEAD_TILT.value: 1.5,
    PostureTypeV2.CHIN_REST.value: 2.0,
}

# 민감도별 confidence 표시 임계 (V2 spec section 6.3)
SENSITIVITY_FLOORS: Dict[str, float] = {
    "high": 0.30,    # 예민
    "medium": 0.50,  # 보통
    "low": 0.70,     # 둔감
}

# 상태 머신 임계값 (기존 baromok 시스템과 호환)
WARNING_THRESHOLD = 0.45
BAD_POSTURE_THRESHOLD = 0.60

# 어깨 검출률 최근 윈도우 (초)
SHOULDER_WINDOW_SECONDS = 5.0


@dataclass
class PostureCandidate:
    """자세 candidate (충돌 처리용)"""
    posture: str
    deviation_score: float        # Δ% 누적 절대값 평균
    raw_score: float              # 정규화 전 점수
    threshold_ratio: float        # 임계값 대비 비율 (1.0 = 정확히 임계 도달)


@dataclass
class JudgmentResultV2:
    """V2 판정 결과"""
    timestamp: float
    frame_state: str              # NORMAL | WARNING | BAD_POSTURE
    detected_posture: str         # 자세 키 (DISPLAY_LABELS 키)
    display_label: str
    confidence: float             # 0.0 ~ 1.0
    deviation_score: float        # 선택된 자세의 deviation
    duration_in_state_s: float    # 현재 상태 지속 시간
    deltas: Dict[str, float]      # 디버그용 Δ% / Δ°
    candidates: List[PostureCandidate]  # 모든 후보 (디버그용)


def _pct_change(value: float, baseline_mean: float) -> Optional[float]:
    """안전한 Δ% 계산.

    None/0 baseline 뿐 아니라 NaN/Inf 입력도 None 으로 거른다.
    잘못된 값이 EMA/confidence 까지 전파되는 것을 막는다.
    """
    if baseline_mean is None or baseline_mean == 0:
        return None
    if value is None:
        return None
    if not np.isfinite(value) or not np.isfinite(baseline_mean):
        return None
    return (value - baseline_mean) / abs(baseline_mean) * 100.0


class JudgmentEngineV2:
    """V2 자세 판정 엔진"""

    def __init__(
        self,
        config: ConfigManager,
        calibration_manager: CalibrationV2Manager,
        sensitivity: str = "medium",
        on_frame: Optional[FrameCallback] = None,
    ):
        """
        Args:
            on_frame: 매 프레임 (indicators, result) 받는 옵셔널 콜백. 디버그/로깅용.
                      운영 환경에서는 None 으로 두어 오버헤드를 0 으로 만든다.
        """
        self.config = config
        self.cal_mgr = calibration_manager
        self.sensitivity = sensitivity if sensitivity in SENSITIVITY_FLOORS else "medium"
        self._on_frame = on_frame

        # 어깨 검출률 슬라이딩 윈도우 (deque — O(1) append + popleft)
        self._shoulder_history: Deque[Tuple[float, bool]] = deque()

        # 자세별 EMA 필터 (likelihood 스무딩)
        ema_alpha = 0.15
        try:
            ema_alpha = (
                self.config.get_posture_criteria()
                .get("filters", {})
                .get("ema", {})
                .get("alpha", 0.15)
            )
        except Exception:
            pass

        self._filters: Dict[str, EMAFilter] = {
            p.value: EMAFilter(alpha=ema_alpha) for p in PostureTypeV2 if p != PostureTypeV2.NEUTRAL
        }

        # 자세별 지속 시간 추적
        self._posture_start_times: Dict[str, Optional[float]] = {
            p.value: None for p in PostureTypeV2
        }
        self._current_state: str = "NORMAL"
        self._state_start_time: Optional[float] = None

        logger.info(f"JudgmentEngineV2 초기화 완료 (sensitivity={self.sensitivity})")

    # ─── 공개 인터페이스 ────────────────────────────────────────────────

    def set_sensitivity(self, level: str) -> None:
        """민감도 설정 변경 (high/medium/low). 누적 EMA 상태도 리셋해 즉시 새 기준으로 판정."""
        if level not in SENSITIVITY_FLOORS or level == self.sensitivity:
            return
        self.sensitivity = level
        # 임계 기준이 바뀌었으므로 누적 confidence 추세는 stale → EMA/타이머만 리셋.
        # 어깨 검출 이력은 sensitivity 와 무관하므로 보존.
        self._reset_judgment_state()
        logger.info(f"V2 민감도 변경: {level}")

    def reset_filters(self) -> None:
        """자세별 EMA 필터, 자세 타이머, 상태 추적, 어깨 이력까지 모두 초기화.

        - 캘리브레이션 재실행 후
        - 사용자 변경/세션 재시작 시
        - 테스트에서 일관된 시작 상태가 필요할 때 호출.
        """
        self._reset_judgment_state()
        self._shoulder_history.clear()

    def _reset_judgment_state(self) -> None:
        """판정 관련 누적 상태만 초기화 (어깨 이력은 보존)."""
        for f in self._filters.values():
            f.reset()
        for key in self._posture_start_times:
            self._posture_start_times[key] = None
        self._current_state = "NORMAL"
        self._state_start_time = None

    def preload_shoulder_history(self, frames: Iterable[PostureIndicators]) -> None:
        """캘리브레이션 직후, 어깨 검출률 슬라이딩 윈도우를 미리 채워준다.

        첫 판정 프레임부터 정확한 _is_shoulder_usable() 결과를 얻기 위함.
        그렇지 않으면 5초간 빈 윈도우라 어깨 보조 지표가 비활성화된다.
        """
        for f in frames:
            self._update_shoulder_history(f.timestamp, getattr(f, "shoulder_width", 0) > 0)

    def judge(self, indicators: PostureIndicators) -> JudgmentResultV2:
        """단일 프레임 자세 판정"""
        ts = indicators.timestamp

        # 어깨 검출 이력 업데이트
        self._update_shoulder_history(ts, indicators.shoulder_width > 0)

        # 캘리브레이션 미로딩 시 NEUTRAL 반환
        if not self.cal_mgr.is_loaded() or self.cal_mgr.calibration is None:
            result = self._neutral_result(ts)
        else:
            result = self._judge_with_calibration(indicators)

        # 옵셔널 콜백 (디버그/로깅) — 운영 환경에서는 None 으로 두어 비용 0
        if self._on_frame is not None:
            try:
                self._on_frame(indicators, result)
            except Exception as e:
                logger.warning(f"on_frame callback 오류 (무시): {e}")
        return result

    def _judge_with_calibration(self, indicators: PostureIndicators) -> JudgmentResultV2:
        """캘리브레이션 데이터가 있는 정상 경로 — 자세 candidate 평가 및 선택"""
        ts = indicators.timestamp
        cal = self.cal_mgr.calibration
        thresholds = cal.auto_thresholds
        neutral = cal.neutral

        # 자세별 candidate 점수 계산
        candidates: List[PostureCandidate] = []

        # 1. chin_rest (손 신호 우선)
        chin = self._eval_chin_rest(indicators, neutral, thresholds)
        if chin is not None:
            candidates.append(chin)

        # 2. head_tilt (eye_line_tilt 절대값 기준)
        ht = self._eval_head_tilt(indicators, neutral, thresholds)
        if ht is not None:
            candidates.append(ht)

        # 3. forward_head_full (어깨 활용 가능 시)
        fhf = self._eval_forward_head_full(indicators, neutral, thresholds)
        if fhf is not None:
            candidates.append(fhf)

        # 4. recline
        rec = self._eval_recline(indicators, neutral, thresholds)
        if rec is not None:
            candidates.append(rec)

        # 5. forward_head_only
        fho = self._eval_forward_head_only(indicators, neutral, thresholds)
        if fho is not None:
            candidates.append(fho)

        # Guards 적용 → 부적합한 candidate 제거
        candidates = self._apply_guards(candidates, indicators, neutral)

        # candidate 가 없거나 모두 0이면 neutral
        if not candidates:
            return self._build_result(
                ts, "neutral", 1.0, 0.0,
                deltas=self._compute_debug_deltas(indicators, neutral),
                candidates=[],
            )

        # deviation_score 최대인 자세 1개 선택 (V2 spec section 3.2)
        best = max(candidates, key=lambda c: c.deviation_score)

        # EMA 스무딩 — 비정상 ratio 는 필터에 넣지 않고 그대로 폴스루
        if not np.isfinite(best.threshold_ratio):
            smoothed_ratio = 0.0
        else:
            smoothed_ratio = self._filters[best.posture].process(best.threshold_ratio)

        # confidence 계산 + 민감도 적용
        confidence = self._compute_confidence(smoothed_ratio)

        return self._build_result(
            ts,
            best.posture,
            confidence,
            best.deviation_score,
            deltas=self._compute_debug_deltas(indicators, neutral),
            candidates=candidates,
        )

    # ─── 자세별 평가 함수 ──────────────────────────────────────────────

    def _eval_forward_head_only(
        self, ind: PostureIndicators, neutral: Dict[str, IndicatorStats], th: Dict[str, float]
    ) -> Optional[PostureCandidate]:
        """forward_head_only 후보 평가.

        forward 임계값 ~ recline 임계값 사이의 cheek 변화일 때 후보가 됨.
        그 이상은 recline 으로 자연 이관 (자세 정의상 더 큰 cheek 변화 = 기댐).
        """
        cheek = neutral.get("cheek_distance")
        if not cheek or cheek.mean <= 0:
            return None
        cd_pct = _pct_change(ind.cheek_distance, cheek.mean)
        forward_th = th.get("forward_cheek_delta_pct", 5.0)
        recline_th = th.get("recline_cheek_delta_pct", 8.0)
        if cd_pct is None or cd_pct <= forward_th:
            return None
        if cd_pct >= recline_th:
            return None  # recline 영역 → recline 평가에 위임

        ratio = cd_pct / forward_th if forward_th > 0 else 0.0
        deviation = abs(cd_pct)

        return PostureCandidate(
            posture=PostureTypeV2.FORWARD_HEAD_ONLY.value,
            deviation_score=deviation,
            raw_score=cd_pct,
            threshold_ratio=ratio,
        )

    def _eval_forward_head_full(
        self, ind: PostureIndicators, neutral: Dict[str, IndicatorStats], th: Dict[str, float]
    ) -> Optional[PostureCandidate]:
        # 어깨 사용 불가하면 평가 불가
        if not self._is_shoulder_usable():
            return None
        cheek = neutral.get("cheek_distance")
        shoulder = neutral.get("shoulder_width")
        if not cheek or not shoulder or cheek.mean <= 0 or shoulder.mean <= 0:
            return None
        # auto_thresholds 에 forward_shoulder_delta_pct 가 없으면(=어깨 비활용) 평가 중단
        if "forward_shoulder_delta_pct" not in th:
            return None

        cd_pct = _pct_change(ind.cheek_distance, cheek.mean) or 0.0
        sw_pct = _pct_change(ind.shoulder_width, shoulder.mean) or 0.0

        # forward_full 은 어깨가 임계값의 2배 이상 변할 만큼 명확하게 같이 움직였을 때만
        forward_th = th.get("forward_cheek_delta_pct", 5.0)
        shoulder_th = th["forward_shoulder_delta_pct"] * 2.0
        if cd_pct <= forward_th or sw_pct <= shoulder_th:
            return None

        ratio = max(cd_pct / forward_th, sw_pct / shoulder_th)
        # deviation: 어깨 변화량에 더 큰 가중치 (forward_full 의 핵심 신호)
        deviation = (abs(cd_pct) * 0.4 + abs(sw_pct) * 0.6)

        return PostureCandidate(
            posture=PostureTypeV2.FORWARD_HEAD_FULL.value,
            deviation_score=deviation,
            raw_score=cd_pct,
            threshold_ratio=ratio,
        )

    def _eval_recline(
        self, ind: PostureIndicators, neutral: Dict[str, IndicatorStats], th: Dict[str, float]
    ) -> Optional[PostureCandidate]:
        """recline 후보 평가.

        forward_head_only와 동일하게 cheek_distance Δ% 기반이지만 recline_th 가 더 높음.
        deviation_score 는 cheek 변화량 그대로 사용 (1.3× 보너스 제거 — forward 범위 침범 방지).
        """
        cheek = neutral.get("cheek_distance")
        if not cheek or cheek.mean <= 0:
            return None
        cd_pct = _pct_change(ind.cheek_distance, cheek.mean)
        threshold = th.get("recline_cheek_delta_pct", 8.0)
        if cd_pct is None or cd_pct <= threshold:
            return None

        ratio = cd_pct / threshold
        deviation = abs(cd_pct)

        return PostureCandidate(
            posture=PostureTypeV2.RECLINE.value,
            deviation_score=deviation,
            raw_score=cd_pct,
            threshold_ratio=ratio,
        )

    def _eval_head_tilt(
        self, ind: PostureIndicators, neutral: Dict[str, IndicatorStats], th: Dict[str, float]
    ) -> Optional[PostureCandidate]:
        eye_tilt = neutral.get("eye_line_tilt")
        if eye_tilt is None:
            return None
        threshold_deg = th.get("head_tilt_deg_abs", 5.0)
        diff = abs(ind.eye_line_tilt - eye_tilt.mean)
        if diff <= threshold_deg:
            return None

        ratio = diff / threshold_deg if threshold_deg > 0 else 0.0
        return PostureCandidate(
            posture=PostureTypeV2.HEAD_TILT.value,
            deviation_score=diff,
            raw_score=diff,
            threshold_ratio=ratio,
        )

    def _eval_chin_rest(
        self, ind: PostureIndicators, neutral: Dict[str, IndicatorStats], th: Dict[str, float]
    ) -> Optional[PostureCandidate]:
        # V1 로직 유지: hand_face_score 가 주 신호, 다중 신호 가중치
        if ind.hand_face_score < CHIN_REST_HAND_THRESHOLD:
            return None

        # 가중치 (V1 기존 값 그대로)
        w_hand = 0.30
        w_eye = 0.35
        w_shoulder = 0.20
        w_neck = 0.15

        eye_tilt = neutral.get("eye_line_tilt")
        eye_diff_deg = abs(ind.eye_line_tilt - (eye_tilt.mean if eye_tilt else 0))
        eye_score = float(np.clip(eye_diff_deg / CHIN_REST_EYE_NORM_DEG, 0.0, 1.0))

        shoulder_score = 0.0
        if self._is_shoulder_usable():
            shoulder_score = float(np.clip(abs(ind.shoulder_tilt_deg) / CHIN_REST_SHOULDER_NORM_DEG, 0.0, 1.0))

        # neck_offset 비교 (baseline 데이터에 neck_offset이 있을 수 있음)
        neck_score = float(np.clip(abs(ind.neck_offset) / CHIN_REST_NECK_NORM, 0.0, 1.0))

        score = (
            w_hand * ind.hand_face_score
            + w_eye * eye_score
            + w_shoulder * shoulder_score
            + w_neck * neck_score
        )
        threshold = th.get("chin_rest_score_threshold", 0.5)
        if score < threshold:
            return None

        ratio = score / threshold if threshold > 0 else 0.0
        # deviation_score 스케일 통일:
        #   다른 자세는 Δ% 절대값(~5~100+%) 을 사용.
        #   chin_rest 도 동일 스케일이 되도록 (score - threshold) 의 % 표현으로 변환.
        #   예: score=0.7, threshold=0.5 → (0.7-0.5)/0.5*100 = 40 (즉 임계 대비 40% 초과)
        deviation_pct = (score - threshold) / threshold * 100.0 if threshold > 0 else score * 100.0
        return PostureCandidate(
            posture=PostureTypeV2.CHIN_REST.value,
            deviation_score=max(0.0, deviation_pct),
            raw_score=score,
            threshold_ratio=ratio,
        )

    # ─── Guards ────────────────────────────────────────────────────────

    def _apply_guards(
        self,
        candidates: List[PostureCandidate],
        ind: PostureIndicators,
        neutral: Dict[str, IndicatorStats],
    ) -> List[PostureCandidate]:
        """
        자세별 오탐 방지 가드 (V2 spec section 3.4).

        V1과 동일한 절대값 기준 사용 — 자세 변경 시 비대칭 지표가 자연스럽게
        변하므로 변화율 기준은 너무 엄격하다는 점이 V2 테스트에서 확인됨.
        """
        out: List[PostureCandidate] = []

        # 머리 기울임 = baseline 대비 차이 (캘리브 시점 머리가 살짝 기울어졌을 수 있음)
        eye_tilt_mean = neutral.get("eye_line_tilt")
        eye_tilt_deviation = abs(
            ind.eye_line_tilt - (eye_tilt_mean.mean if eye_tilt_mean else 0)
        )

        # 비대칭 지표는 절대값 기준 (V1 가드와 동일)
        eye_sym_abs = abs(ind.eye_symmetry_ratio)
        cheek_sym_abs = abs(ind.cheek_symmetry_ratio)
        chin_offset_abs = abs(ind.chin_alignment_offset)

        shoulder_tilt_abs = abs(ind.shoulder_tilt_deg) if self._is_shoulder_usable() else 0.0

        for c in candidates:
            posture = c.posture

            if posture == PostureTypeV2.FORWARD_HEAD_ONLY.value:
                # 머리/어깨 너무 기울거나 비대칭 심하면 다른 자세
                if eye_tilt_deviation > GUARD_MAX_EYE_TILT_DEG or shoulder_tilt_abs > GUARD_MAX_SHOULDER_TILT_DEG:
                    continue
                if eye_sym_abs > GUARD_MAX_EYE_SYMMETRY or cheek_sym_abs > GUARD_MAX_CHEEK_SYMMETRY:
                    continue
                if chin_offset_abs > GUARD_MAX_CHIN_ALIGNMENT:
                    continue

            elif posture == PostureTypeV2.FORWARD_HEAD_FULL.value:
                if shoulder_tilt_abs > GUARD_MAX_SHOULDER_TILT_DEG:
                    continue
                if cheek_sym_abs > GUARD_MAX_CHEEK_SYMMETRY or eye_sym_abs > GUARD_MAX_EYE_SYMMETRY:
                    continue

            elif posture == PostureTypeV2.RECLINE.value:
                if eye_tilt_deviation > GUARD_MAX_EYE_TILT_DEG or shoulder_tilt_abs > GUARD_MAX_SHOULDER_TILT_DEG:
                    continue
                if eye_sym_abs > GUARD_MAX_EYE_SYMMETRY or cheek_sym_abs > GUARD_MAX_CHEEK_SYMMETRY:
                    continue

            # head_tilt, chin_rest 는 가드 미적용 (자체적으로 신호 강함)
            out.append(c)

        return out

    # ─── 어깨 가용성 ───────────────────────────────────────────────────

    def _update_shoulder_history(self, ts: float, detected: bool) -> None:
        """O(1) 슬라이딩 윈도우. 만료된 항목만 popleft."""
        self._shoulder_history.append((ts, detected))
        cutoff = ts - SHOULDER_WINDOW_SECONDS
        while self._shoulder_history and self._shoulder_history[0][0] < cutoff:
            self._shoulder_history.popleft()

    def _is_shoulder_usable(self) -> bool:
        """최근 5초 어깨 검출률 ≥ 70%"""
        if not self._shoulder_history:
            return False
        detected = sum(1 for _, d in self._shoulder_history if d)
        rate = detected / len(self._shoulder_history)
        return rate >= SHOULDER_AVAILABLE_THRESHOLD

    # ─── confidence / 상태 ──────────────────────────────────────────────

    def _compute_confidence(self, ratio: float) -> float:
        """
        threshold_ratio → confidence (0~1) 변환.
        ratio=1.0 (임계값 정확히 도달) → 0.5
        ratio=4.0 (임계값 4배 초과) → 1.0
        """
        # NaN/Inf 방어 — np.isfinite 는 NaN/+Inf/-Inf 모두 False
        if ratio is None or not np.isfinite(ratio) or ratio <= 0:
            return 0.0
        confidence = min((ratio - 1.0) / 3.0 + 0.5, 1.0)
        floor = SENSITIVITY_FLOORS[self.sensitivity]
        if confidence < floor:
            return 0.0
        return float(max(0.0, confidence))

    def _frame_state(self, confidence: float) -> str:
        """confidence → state machine state"""
        if confidence >= BAD_POSTURE_THRESHOLD:
            return "BAD_POSTURE"
        if confidence >= WARNING_THRESHOLD:
            return "WARNING"
        return "NORMAL"

    # ─── 결과 빌더 ─────────────────────────────────────────────────────

    def _neutral_result(self, ts: float) -> JudgmentResultV2:
        return self._build_result(ts, "neutral", 1.0, 0.0, deltas={}, candidates=[])

    def _build_result(
        self,
        ts: float,
        posture: str,
        confidence: float,
        deviation_score: float,
        deltas: Dict[str, float],
        candidates: List[PostureCandidate],
    ) -> JudgmentResultV2:
        state = self._frame_state(confidence) if posture != "neutral" else "NORMAL"

        # 상태 지속 시간 추적
        if state != self._current_state:
            self._current_state = state
            self._state_start_time = ts
        duration = (ts - self._state_start_time) if self._state_start_time is not None else 0.0

        return JudgmentResultV2(
            timestamp=ts,
            frame_state=state,
            detected_posture=posture,
            display_label=DISPLAY_LABELS.get(posture, posture),
            confidence=confidence,
            deviation_score=deviation_score,
            duration_in_state_s=max(0.0, duration),
            deltas=deltas,
            candidates=candidates,
        )

    def _compute_debug_deltas(
        self, ind: PostureIndicators, neutral: Dict[str, IndicatorStats]
    ) -> Dict[str, float]:
        """디버그용 Δ% 출력"""
        deltas: Dict[str, float] = {}
        for key in ("cheek_distance", "eye_distance"):
            n = neutral.get(key)
            if n and n.mean > 0:
                val = getattr(ind, key, 0)
                deltas[f"{key}_pct"] = round(_pct_change(val, n.mean) or 0.0, 2)
        # eye_line_tilt 는 각도 차이로
        et = neutral.get("eye_line_tilt")
        if et:
            deltas["eye_line_tilt_delta_deg"] = round(ind.eye_line_tilt - et.mean, 2)
        # shoulder_width
        sw = neutral.get("shoulder_width")
        if sw and sw.available and sw.mean > 0:
            deltas["shoulder_width_pct"] = round(_pct_change(ind.shoulder_width, sw.mean) or 0.0, 2)
        return deltas

    # ─── 자세 확정 (sustain_seconds) ───────────────────────────────────

    def update_sustain(self, result: JudgmentResultV2) -> Optional[str]:
        """
        sustain_seconds 만큼 자세 유지 시 '확정 자세' 반환.

        Returns:
            확정된 자세 이름 (or None)
        """
        ts = result.timestamp
        detected = result.detected_posture

        # 모든 자세 타이머 갱신
        for posture in PostureTypeV2:
            key = posture.value
            if key == "neutral":
                continue
            if detected == key and result.confidence > 0:
                if self._posture_start_times[key] is None:
                    self._posture_start_times[key] = ts
            else:
                self._posture_start_times[key] = None

        # 확정 조건 확인
        if detected != "neutral" and result.confidence > 0:
            start = self._posture_start_times.get(detected)
            if start is not None:
                duration = ts - start
                required = SUSTAIN_SECONDS.get(detected, 1.5)
                if duration >= required:
                    return detected
        return None
