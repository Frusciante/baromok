"""
V2 캘리브레이션 모듈

V2 자세 감지 로직용 baseline 수집/관리.

V1(BaselineManager)와의 차이:
  - 단일 자세(neutral)만 수집하지만 표준편차까지 저장
  - 자세별 임계값을 캘리브레이션 시 자동 도출 (mean + 3*std, 최소 5% 보장)
  - 어깨 검출률을 기록하여 보조 지표 사용 가능 여부 판단

참고: docs/posture_logic_v2_spec.md
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.config import ConfigManager
from src.core.indicator_calculator import PostureIndicators
from src.utils.logger import get_logger

logger = get_logger(__name__)


# V2가 캘리브레이션에서 추적하는 지표
PRIMARY_INDICATORS: List[str] = [
    "cheek_distance",
    "eye_distance",
    "cheek_eye_ratio",
    "face_center_y",
    "eye_line_tilt",
    "eye_symmetry_ratio",
    "cheek_symmetry_ratio",
]

# 어깨 검출이 가능할 때만 사용하는 보조 지표
AUXILIARY_INDICATORS: List[str] = [
    "shoulder_width",
    "shoulder_tilt_deg",
]

# 어깨를 보조 지표로 활용할지 결정하는 검출률 기준
SHOULDER_AVAILABLE_THRESHOLD = 0.70

# 임계값 안전장치 (방법 3): 최소 변화량 보장
MIN_DELTA_PCT_SAFETY = 5.0  # %
HEAD_TILT_MIN_DEG = 5.0     # head_tilt 최소 임계 각도


@dataclass
class IndicatorStats:
    """단일 지표의 통계량"""
    mean: float
    std: float
    available: bool = True


@dataclass
class CalibrationV2:
    """V2 캘리브레이션 데이터"""
    version: str = "v2.0"
    timestamp: str = ""
    collection_duration_seconds: float = 0.0
    frame_count: int = 0
    shoulder_detection_rate: float = 0.0
    calibration_quality: str = "unknown"  # good | warning | bad
    quality_messages: List[str] = field(default_factory=list)

    # 지표별 통계 (mean, std)
    neutral: Dict[str, IndicatorStats] = field(default_factory=dict)

    # 자동 도출된 임계값
    auto_thresholds: Dict[str, float] = field(default_factory=dict)


class CalibrationV2Manager:
    """V2 캘리브레이션 관리자"""

    def __init__(self, config: ConfigManager, data_dir: str = "data"):
        self.config = config
        self.data_dir = Path(data_dir)
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            logger.error(f"V2 데이터 디렉토리 생성 실패 ({self.data_dir}): {e}")
            # save() 호출 시 실패하지만, in-memory 캘리브로 동작은 가능
        self.baseline_file = self.data_dir / "baseline_v2.json"

        # 수집 상태
        self._is_collecting = False
        self._collection_start_time: float = 0.0
        self._frames: List[PostureIndicators] = []

        # 로드된 캘리브레이션
        self.calibration: Optional[CalibrationV2] = None

        # 수집 파라미터 (V2 spec section 4.2)
        baseline_config = self.config.get_baseline_config() if hasattr(self.config, "get_baseline_config") else {}
        capture = baseline_config.get("capture", {}) if isinstance(baseline_config, dict) else {}
        self.wait_seconds: float = float(capture.get("wait_seconds_v2", 3.0))
        self.collect_seconds: float = float(capture.get("collect_seconds_v2", 10.0))
        self.minimum_valid_frames: int = int(capture.get("minimum_valid_frames_v2", 100))

        self.total_frames_seen: int = 0
        self.valid_frames_seen: int = 0

        self.progress: float = 0.0
        self.quality_score: float = 0.0

        logger.info(
            f"CalibrationV2Manager 초기화 (wait={self.wait_seconds}s, collect={self.collect_seconds}s, "
            f"min_frames={self.minimum_valid_frames})"
        )

    # ─── 수집 ──────────────────────────────────────────────────────────

    def start_collection(self) -> None:
        """neutral 자세 수집 시작"""
        logger.warning("V2 START_COLLECTION CALLED")
        self._is_collecting = True
        self._frames = []
        self.total_frames_seen = 0
        self.valid_frames_seen = 0

        self.progress = 0.0
        self.quality_score = 0.0
        self._collection_start_time = time.time()
        logger.info("V2 캘리브레이션 수집 시작")

    
    def add_frame(self, indicators: PostureIndicators) -> None:
        """수집 중 프레임 추가"""

        if not self._is_collecting:
            return

        self.total_frames_seen += 1

        if indicators is None:
            return

        self._frames.append(indicators)
        self.valid_frames_seen += 1

        # 진행률 계산
        self.progress = min(
            1.0,
            self.valid_frames_seen / self.minimum_valid_frames
        )

        # 품질 점수 계산
        if self.total_frames_seen > 0:
            self.quality_score = (
                self.valid_frames_seen / self.total_frames_seen
            )
        else:
            self.quality_score = 0.0

    def finish_collection(self) -> bool:
        """
        수집 종료 → 통계 계산 → 임계값 도출.

        Returns:
            성공 여부 (최소 프레임 수 + 검증 통과)
        """
        if not self._is_collecting:
            logger.warning("수집 중이 아닌데 종료 호출됨")
            return False

        self._is_collecting = False
        duration = time.time() - self._collection_start_time

        if len(self._frames) < self.minimum_valid_frames:
            logger.warning(
                f"수집된 프레임 부족: {len(self._frames)} < {self.minimum_valid_frames}"
            )
            return False
    
        logger.info(
            f"V2 calibration completed successfully "
            f"({len(self._frames)} frames, {duration:.2f}s)"
        )

        # 통계 계산
        calibration = self._compute_statistics(duration)
        if calibration is None:
            return False

        # 임계값 자동 도출
        calibration.auto_thresholds = self._derive_thresholds(calibration.neutral)

        # 품질 평가
        self._evaluate_quality(calibration)

        self.calibration = calibration
        logger.info(
            f"V2 캘리브레이션 완료 (frames={calibration.frame_count}, "
            f"quality={calibration.calibration_quality}, "
            f"shoulder_rate={calibration.shoulder_detection_rate:.2f})"
        )
        return True
    
    def get_collection_status(self) -> dict:
        return {
            "progress": self.progress,
            "quality_score": self.quality_score,
            "valid_frames": self.valid_frames_seen,
            "required_frames": self.minimum_valid_frames,
        }

    # ─── 통계 ──────────────────────────────────────────────────────────

    def _compute_statistics(self, duration: float) -> Optional[CalibrationV2]:
        """수집된 프레임으로 평균/표준편차 계산"""
        frames = self._frames

        # 어깨 검출률 계산 (shoulder_width > 0 인 프레임 비율)
        shoulder_valid = sum(1 for f in frames if getattr(f, "shoulder_width", 0) > 0)
        shoulder_rate = shoulder_valid / len(frames) if frames else 0.0

        neutral: Dict[str, IndicatorStats] = {}

        # 주요 지표
        # face_center_y 는 IndicatorCalculator 에 노출되지 않은 경우가 있어
        # 추출 실패해도 silently 누락 처리한다.
        OPTIONAL_PRIMARY = {"face_center_y"}
        for key in PRIMARY_INDICATORS:
            values = self._extract_values(frames, key)
            if not values:
                if key not in OPTIONAL_PRIMARY:
                    logger.warning(f"지표 '{key}' 추출 실패")
                continue
            arr = np.array(values, dtype=np.float64)
            neutral[key] = IndicatorStats(
                mean=float(np.mean(arr)),
                std=float(np.std(arr)),
                available=True,
            )

        # 보조 지표 (어깨 — 검출률 충분할 때만 available=True)
        # NOTE: shoulder_tilt_deg 는 음수가 정상값(좌측 기울기)이므로 추가 `v > 0` 필터링 금지.
        # 0/음수 제외는 _extract_values 가 _NONZERO_REQUIRED 기반으로 처리.
        for key in AUXILIARY_INDICATORS:
            values = self._extract_values(frames, key)
            available = (
                shoulder_rate >= SHOULDER_AVAILABLE_THRESHOLD
                and len(values) >= self.minimum_valid_frames * 0.7
            )
            if values:
                arr = np.array(values, dtype=np.float64)
                neutral[key] = IndicatorStats(
                    mean=float(np.mean(arr)),
                    std=float(np.std(arr)),
                    available=available,
                )
            else:
                neutral[key] = IndicatorStats(mean=0.0, std=0.0, available=False)

        return CalibrationV2(
            version="v2.0",
            timestamp=datetime.now().isoformat(),
            collection_duration_seconds=duration,
            frame_count=len(frames),
            shoulder_detection_rate=shoulder_rate,
            neutral=neutral,
        )

    # 0 값을 "검출 실패"로 간주해 통계에서 제외할 지표
    _NONZERO_REQUIRED = {
        "cheek_distance", "eye_distance", "shoulder_width",
        "cheek_eye_ratio", "face_vertical_length",
    }

    @classmethod
    def _extract_values(cls, frames: List[PostureIndicators], key: str) -> List[float]:
        """프레임 리스트에서 특정 지표 값 추출 (cheek_eye_ratio, face_center_y 등 파생 포함)"""
        out: List[float] = []
        for f in frames:
            v = None
            if key == "cheek_eye_ratio":
                eye = getattr(f, "eye_distance", 0)
                cheek = getattr(f, "cheek_distance", 0)
                if eye and eye > 0 and cheek and cheek > 0:
                    v = cheek / eye
            elif key == "face_center_y":
                v = getattr(f, "face_center_y", None)
            else:
                v = getattr(f, key, None)
            if v is None or not np.isfinite(v):
                continue
            # 거리 기반 지표는 0이면 검출 실패로 보고 제외
            if key in cls._NONZERO_REQUIRED and v == 0:
                continue
            out.append(float(v))
        return out

    # ─── 임계값 자동 도출 ────────────────────────────────────────────────

    def _derive_thresholds(self, neutral: Dict[str, IndicatorStats]) -> Dict[str, float]:
        """
        neutral 통계로부터 자세별 임계값 자동 도출.

        방법 2 (표준편차 기반) + 방법 3 (최소 변화량 보장):
          threshold = max(mean + 3*std, mean * (1 + MIN_DELTA_PCT_SAFETY/100))

        Returns:
            Dict with keys:
              forward_cheek_delta_pct
              recline_cheek_delta_pct
              forward_shoulder_delta_pct
              head_tilt_deg_abs
        """
        thresholds: Dict[str, float] = {}

        # cheek_distance 기반: forward_head_only / recline 공통 베이스
        # 실험 데이터: forward Δ% +3~+12% (U1), recline Δ% +15~+42% (U1)
        # → forward 와 recline 의 간격을 forward_th × 3 정도로 두면 자연 분리됨
        FORWARD_RECLINE_RATIO = 3.0
        cheek = neutral.get("cheek_distance")
        if cheek and cheek.mean > 0:
            std_based_pct = (3.0 * cheek.std) / abs(cheek.mean) * 100.0
            forward_th = max(std_based_pct, MIN_DELTA_PCT_SAFETY)
            recline_th = max(forward_th * FORWARD_RECLINE_RATIO,
                             MIN_DELTA_PCT_SAFETY * FORWARD_RECLINE_RATIO)
            thresholds["forward_cheek_delta_pct"] = round(forward_th, 2)
            thresholds["recline_cheek_delta_pct"] = round(recline_th, 2)
        else:
            thresholds["forward_cheek_delta_pct"] = MIN_DELTA_PCT_SAFETY
            thresholds["recline_cheek_delta_pct"] = MIN_DELTA_PCT_SAFETY * FORWARD_RECLINE_RATIO

        # shoulder_width — forward_head_full 구분용 (어깨 검출 가능 시만)
        shoulder = neutral.get("shoulder_width")
        if shoulder and shoulder.available and shoulder.mean > 0:
            std_based_pct = (3.0 * shoulder.std) / abs(shoulder.mean) * 100.0
            thresholds["forward_shoulder_delta_pct"] = round(
                max(std_based_pct, MIN_DELTA_PCT_SAFETY), 2
            )
        # else: 어깨 비활용 시 키 자체를 생략 — JSON 표준 위반(Infinity) 회피.
        # 소비자는 .get(...) 의 기본값/누락 체크로 어깨 비활용 여부 판단.

        # eye_line_tilt — head_tilt 임계 각도
        eye_tilt = neutral.get("eye_line_tilt")
        if eye_tilt:
            std_based_deg = 3.0 * eye_tilt.std
            thresholds["head_tilt_deg_abs"] = round(max(std_based_deg, HEAD_TILT_MIN_DEG), 2)
        else:
            thresholds["head_tilt_deg_abs"] = HEAD_TILT_MIN_DEG

        # chin_rest score 임계값 (V2 spec 기본값)
        thresholds["chin_rest_score_threshold"] = 0.5

        return thresholds

    # ─── 품질 평가 ─────────────────────────────────────────────────────

    def _evaluate_quality(self, cal: CalibrationV2) -> None:
        """캘리브레이션 품질 평가 및 메시지 생성.

        quality 분류:
          - good             : 모든 검증 통과
          - good_face_only   : 얼굴 지표는 안정적이나 어깨 비활성 (UI 에서 명시 필요)
          - warning          : 1개 경고 (프레임 부족 OR 흔들림)
          - bad              : 2개 이상 경고
        """
        messages: List[str] = []
        warnings = 0

        # 1. 프레임 수
        if cal.frame_count < self.minimum_valid_frames * 1.5:
            messages.append(f"프레임 수가 적습니다 ({cal.frame_count}). 조명/카메라를 확인하세요.")
            warnings += 1

        # 2. 안정성 (CV)
        cheek = cal.neutral.get("cheek_distance")
        if cheek and cheek.mean > 0:
            cv = cheek.std / abs(cheek.mean)
            if cv > 0.1:
                messages.append(f"측정 중 흔들림이 컸습니다 (CV={cv:.3f}). 가만히 앉아주세요.")
                warnings += 1

        # 3. 어깨 검출률 — quality 등급에는 반영하되 warnings 카운트엔 미산입
        #    (어깨 없이도 얼굴 지표로 자세 감지가 가능하므로 "fatal" 아님)
        shoulder_low = cal.shoulder_detection_rate < SHOULDER_AVAILABLE_THRESHOLD
        if shoulder_low:
            messages.append(
                f"어깨 검출률이 낮습니다 ({cal.shoulder_detection_rate*100:.1f}%). "
                "어깨 기반 자세 구분(forward_head_full 등)이 비활성화됩니다."
            )

        cal.quality_messages = messages
        if warnings >= 2:
            cal.calibration_quality = "bad"
        elif warnings == 1:
            cal.calibration_quality = "warning"
        elif shoulder_low:
            cal.calibration_quality = "good_face_only"
        else:
            cal.calibration_quality = "good"

    # ─── 저장/로드 ─────────────────────────────────────────────────────

    def save(self) -> bool:
        """현재 캘리브레이션을 baseline_v2.json 으로 저장"""
        if self.calibration is None:
            logger.warning("저장할 V2 캘리브레이션이 없음")
            return False

        try:
            payload = self._serialize(self.calibration)
            with open(self.baseline_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logger.info(f"V2 baseline 저장: {self.baseline_file}")
            return True
        except Exception as e:
            logger.error(f"V2 baseline 저장 실패: {e}")
            return False

    def load(self) -> bool:
        """baseline_v2.json 로드"""
        if not self.baseline_file.exists():
            logger.warning(f"V2 baseline 파일 없음: {self.baseline_file}")
            return False

        try:
            with open(self.baseline_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            neutral_raw = data.get("neutral", {})
            neutral = {
                k: IndicatorStats(
                    mean=float(v.get("mean", 0)),
                    std=float(v.get("std", 0)),
                    available=bool(v.get("available", True)),
                )
                for k, v in neutral_raw.items()
            }

            self.calibration = CalibrationV2(
                version=data.get("version", "v2.0"),
                timestamp=data.get("timestamp", ""),
                collection_duration_seconds=float(data.get("collection_duration_seconds", 0)),
                frame_count=int(data.get("frame_count", 0)),
                shoulder_detection_rate=float(data.get("shoulder_detection_rate", 0)),
                calibration_quality=data.get("calibration_quality", "unknown"),
                quality_messages=data.get("quality_messages", []),
                neutral=neutral,
                auto_thresholds=dict(data.get("auto_thresholds", {})),
            )
            logger.info(f"V2 baseline 로드 완료: quality={self.calibration.calibration_quality}")
            return True
        except Exception as e:
            logger.error(f"V2 baseline 로드 실패: {e}")
            return False

    @staticmethod
    def _serialize(cal: CalibrationV2) -> Dict[str, Any]:
        """직렬화용 dict 변환"""
        return {
            "version": cal.version,
            "timestamp": cal.timestamp,
            "collection_duration_seconds": cal.collection_duration_seconds,
            "frame_count": cal.frame_count,
            "shoulder_detection_rate": cal.shoulder_detection_rate,
            "calibration_quality": cal.calibration_quality,
            "quality_messages": cal.quality_messages,
            "neutral": {k: asdict(v) for k, v in cal.neutral.items()},
            "auto_thresholds": cal.auto_thresholds,
        }

    # ─── 조회 ──────────────────────────────────────────────────────────

    def is_loaded(self) -> bool:
        return self.calibration is not None

    def shoulder_available(self) -> bool:
        """어깨 보조 지표 사용 가능 여부"""
        if self.calibration is None:
            return False
        sw = self.calibration.neutral.get("shoulder_width")
        return bool(sw and sw.available)

    # ─── 진행 상황 조회 (UI/디버그용 — _frames 직접 접근 대체) ────────────

    @property
    def collected_frame_count(self) -> int:
        """현재 수집된 프레임 수 (수집 중에 진행도 표시용)"""
        return len(self._frames)

    @property
    def is_collecting(self) -> bool:
        return self._is_collecting

    def get_collected_frames(self) -> List[PostureIndicators]:
        """수집된 프레임 리스트의 얕은 복사 반환 (외부에서 분석/디버그 용도)"""
        return list(self._frames)
