"""
Baseline 관리자

바른자세 수집, 저장, 비교 기능 제공
"""

import json
import time
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from src.config import ConfigManager
from src.core.indicator_calculator import PostureIndicators
from src.utils.helpers import RansacQuadraticModel
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

        # MediaPipe 3개 모델을 동시에 돌리면 실제 처리 FPS가 낮을 수 있으므로,
        # 6단계(총 30초 수집) 데이터를 충분히 확보하기 위해 최소 유효 프레임을 설정에서 가져온다.
        baseline_config = self.config.get_baseline_config()
        capture_config = baseline_config.get("capture", {})
        self.minimum_valid_frame_count = capture_config.get(
            "minimum_valid_frames", 60
        )

        self.ransac_model = RansacQuadraticModel(
            min_samples=10, residual_threshold=0.01
        )
        self.max_inlier_deviation = 0.05
        self.mean_inlier_deviation = 0.02
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

        if indicators is None:
            logger.debug("Baseline 수집 프레임에 indicators가 없어 제외")
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

        actual_duration = time.time() - self.collection_start_time
        frame_count = len(self.collection_frames)

        baseline_config = self.config.get_baseline_config()
        capture_config = baseline_config.get("capture", {})
        expected_samples = capture_config.get("expected_samples", 20)

        logger.info(
            f"Baseline 수집 완료: {frame_count} 프레임 "
            f"(설정 샘플 단계: {expected_samples}, 최소 필요 {self.minimum_valid_frame_count})"
        )

        if frame_count < self.minimum_valid_frame_count:
            logger.warning(
                f"Baseline 프레임 부족: {frame_count} < {self.minimum_valid_frame_count}. "
                "Baseline을 저장하지 않습니다."
            )
            self.baseline_metrics = None
            return False

        # RANSAC 적합을 위한 데이터 준비 및 훈련
        # 독립 변수 (X): shoulder_width, 종속 변수 (y): cheek_distance
        x_data = []
        y_data = []
        s_data = []
        for frame in self.collection_frames:
            if (
                getattr(frame, "shoulder_width", 0) > 0
                and getattr(frame, "cheek_distance", 0) > 0
            ):
                x_data.append(frame.shoulder_width)
                y_data.append(frame.cheek_distance)
                s_data.append(getattr(frame, "step_index", 0))

        if self.ransac_model.fit(x_data, y_data):
            logger.info(f"자세 맞춤 완료 (샘플 수: {len(x_data)})")

            # 오차 측정 (최대 편차 계산)
            y_pred = [self.ransac_model.predict(x) for x in x_data]
            deviations = [
                abs(actual - pred) / max(1e-6, pred)
                for actual, pred in zip(y_data, y_pred)
            ]

            # RANSAC 인라이어(Inliers)에 대해서만 오차 계산 (이상치 제외한 노이즈 수준 파악)
            try:
                ransac = self.ransac_model.model.named_steps["ransacregressor"]
                inlier_mask = ransac.inlier_mask_
                inlier_deviations = [
                    d for d, is_inlier in zip(deviations, inlier_mask) if is_inlier
                ]

                if inlier_deviations:
                    self.max_inlier_deviation = float(np.max(inlier_deviations))
                    self.mean_inlier_deviation = float(np.mean(inlier_deviations))
                    logger.info(
                        f"자세 맞춤 노이즈 수준: Max Dev={self.max_inlier_deviation:.4f}, Mean Dev={self.mean_inlier_deviation:.4f}"
                    )
                else:
                    self.max_inlier_deviation = 0.05  # 기본값
            except Exception as e:
                logger.warning(f"오차 분석 실패: {e}")
                self.max_inlier_deviation = 0.05

            self._save_debug_plot(x_data, y_data, step_indices=s_data)
        else:
            logger.warning(
                f"자세 맞춤 실패 (샘플 수 부족 또는 분산 부족: {len(x_data)})"
            )
            self.max_inlier_deviation = 0.05

        try:
            self.baseline_metrics = self._compute_baseline_metrics(
                actual_duration,
                frame_count,
            )

            if not self.is_baseline_valid():
                logger.warning("Baseline 필수 지표가 부족하여 저장하지 않습니다.")
                self.baseline_metrics = None
                return False

            self.save_baseline_to_file()

            logger.info("Baseline 메트릭 계산 및 저장 완료")
            return True

        except Exception as e:
            logger.error(f"Baseline 계산 실패: {e}")
            self.baseline_metrics = None
            return False

    def _compute_baseline_metrics(
        self,
        duration: float,
        frame_count: int,
    ) -> BaselineMetrics:
        """
        Baseline 메트릭 계산
        """
        metrics = {}
        indicator_names = [
            "cheek_distance",
            "eye_distance",
            "face_vertical_length",
            "shoulder_width",
            "shoulder_tilt_deg",
            "neck_offset",
            "eye_line_tilt",
            "chin_occlusion",
        ]

        for name in indicator_names:
            values = []

            for frame in self.collection_frames:
                value = getattr(frame, name, None)
                if value is not None:
                    values.append(value)

            if values:
                # 중앙값 사용 (이상값 영향 최소화)
                median_value = float(np.median(values))
                metrics[name] = median_value
                logger.debug(f"{name}: median={median_value:.4f}, count={len(values)}")

        # 샘플 데이터 보존 (RANSAC 모델 복원용)
        x_samples = []
        y_samples = []
        s_samples = []  # step indices
        for frame in self.collection_frames:
            if (
                getattr(frame, "shoulder_width", 0) > 0
                and getattr(frame, "cheek_distance", 0) > 0
            ):
                x_samples.append(frame.shoulder_width)
                y_samples.append(frame.cheek_distance)
                s_samples.append(getattr(frame, "step_index", 0))

        metrics["ransac_x_samples"] = x_samples
        metrics["ransac_y_samples"] = y_samples
        metrics["ransac_s_samples"] = s_samples

        return BaselineMetrics(
            timestamp=datetime.now().isoformat(),
            collection_duration_seconds=duration,
            frame_count=frame_count,
            metrics=metrics,
        )

    def save_baseline_to_file(self, filepath: Optional[str] = None) -> bool:
        """Baseline 메트릭을 JSON으로 저장"""
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
                "timestamp": self.baseline_metrics.timestamp,
                "collection_duration_seconds": (
                    self.baseline_metrics.collection_duration_seconds
                ),
                "frame_count": self.baseline_metrics.frame_count,
                "metrics": self.baseline_metrics.metrics,
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Baseline 저장 완료: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Baseline 저장 실패: {e}")
            return False

    def load_baseline_from_file(self, filepath: Optional[str] = None) -> bool:
        """저장된 baseline 로드"""
        if filepath is None:
            filepath = self.data_dir / "baseline.json"
        else:
            filepath = Path(filepath)

        if not filepath.exists():
            logger.warning(f"Baseline 파일 없음: {filepath}")
            return False

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.baseline_metrics = BaselineMetrics(
                timestamp=data.get("timestamp", ""),
                collection_duration_seconds=data.get("collection_duration_seconds", 0),
                frame_count=data.get("frame_count", 0),
                metrics=data.get("metrics", {}),
            )

            logger.info(f"Baseline 로드 완료: {filepath}")

            # RANSAC 모델 복원
            if (
                "ransac_x_samples" in self.baseline_metrics.metrics
                and "ransac_y_samples" in self.baseline_metrics.metrics
            ):
                x_data = self.baseline_metrics.metrics["ransac_x_samples"]
                y_data = self.baseline_metrics.metrics["ransac_y_samples"]
                if self.ransac_model.fit(x_data, y_data):
                    logger.info(
                        f"Baseline 로드: RANSAC 모델 복원 성공 (샘플: {len(x_data)})"
                    )
                else:
                    logger.warning("Baseline 로드: RANSAC 모델 복원 실패")
            else:
                logger.info("Baseline 로드: RANSAC 샘플 데이터 없음 (기본값 사용)")

            return True

        except Exception as e:
            logger.error(f"Baseline 로드 실패: {e}")
            return False

    def baseline_file_exists(self) -> bool:
        """저장된 baseline.json 파일 존재 여부"""
        return (self.data_dir / "baseline.json").exists()

    def get_baseline_metrics(self) -> Optional[BaselineMetrics]:
        """현재 baseline 메트릭 반환"""
        return self.baseline_metrics

    def get_expected_cheek(self, shoulder_width: float) -> float:
        """
        RANSAC 모델을 통해 현재 어깨 너비에 대한 예상 광대 거리(Cheek Distance) 산출
        """
        if self.ransac_model.is_fitted:
            return self.ransac_model.predict(shoulder_width)

        # 모델이 없으면 기본 베이스라인(중앙값) 광대 거리 반환
        if self.baseline_metrics and "cheek_distance" in self.baseline_metrics.metrics:
            return self.baseline_metrics.metrics["cheek_distance"]

        return 0.0

    def get_expected_ratio(self, shoulder_width: float) -> float:
        """
        [DEPRECATED] 비율 대신 광대 거리를 직접 사용하세요.
        """
        expected_cheek = self.get_expected_cheek(shoulder_width)
        if shoulder_width > 0:
            return expected_cheek / shoulder_width
        return 0.0

    def calculate_change_percentage(
        self,
        current_value: float,
        metric_name: str,
    ) -> float:
        """Baseline 대비 변화율 (%) 계산"""
        if (
            self.baseline_metrics is None
            or metric_name not in self.baseline_metrics.metrics
        ):
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
        Baseline이 충분한 데이터로 설정되었는지 검증

        검사 항목:
        1. baseline_metrics 존재 및 구조 검증
        2. frame_count 최소 기준
        3. RANSAC 모델 복원 및 적합 여부
        4. 메트릭 값 유효성 (NaN/Inf/범위)
        5. 타임스탬프 신선도 및 편차 임계값

        Returns:
            유효 여부
        """
        import math
        from datetime import datetime, timedelta

        # 1. baseline_metrics 존재 및 필수 구조 검증
        if self.baseline_metrics is None:
            logger.warning("Baseline이 로드되지 않음")
            return False

        if (
            not hasattr(self.baseline_metrics, "metrics")
            or self.baseline_metrics.metrics is None
        ):
            logger.warning("Baseline 메트릭 딕셔너리가 없음")
            return False

        metrics = self.baseline_metrics.metrics

        # 필수 키 검증
        required_metrics = [
            "cheek_distance",
            "shoulder_width",
        ]
        for metric_name in required_metrics:
            if metric_name not in metrics:
                logger.warning(f"필수 지표 부재: {metric_name}")
                return False

        # 2. frame_count 최소 기준 검증
        frame_count = getattr(self.baseline_metrics, "frame_count", 0)
        if frame_count < self.minimum_valid_frame_count:
            logger.warning(
                f"Baseline 프레임 부족: {frame_count} < {self.minimum_valid_frame_count}"
            )
            return False

        # 3. RANSAC 모델 복원 및 적합 여부 검증
        if not self.ransac_model.is_fitted:
            # RANSAC 샘플 데이터 존재 확인 후 재복원 시도
            if (
                "ransac_x_samples" in metrics
                and "ransac_y_samples" in metrics
                and len(metrics.get("ransac_x_samples", [])) > 0
                and len(metrics.get("ransac_y_samples", [])) > 0
            ):
                x_data = metrics["ransac_x_samples"]
                y_data = metrics["ransac_y_samples"]
                try:
                    if not self.ransac_model.fit(x_data, y_data):
                        logger.warning("RANSAC 모델 재복원 실패")
                        return False
                except Exception as e:
                    logger.warning(f"RANSAC 복원 중 예외: {e}")
                    return False
            else:
                logger.warning("RANSAC 샘플 데이터 부족 또는 없음")
                return False

        # RANSAC 인라이어 수 최소 검증 (권장: >= 10)
        try:
            ransac = self.ransac_model.model.named_steps["ransacregressor"]
            inlier_mask = ransac.inlier_mask_
            inlier_count = int(np.sum(inlier_mask)) if inlier_mask is not None else 0
            if inlier_count < 10:
                logger.warning(f"RANSAC 인라이어 부족: {inlier_count} < 10")
                return False
        except Exception as e:
            logger.debug(f"RANSAC 인라이어 검증 중 예외 (무시): {e}")

        # 4. 메트릭 값 유효성 검증 (NaN/Inf/범위)
        for metric_name in required_metrics:
            value = metrics.get(metric_name, 0)
            # NaN/Inf 체크
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                logger.warning(f"메트릭 값 무효 (NaN/Inf): {metric_name} = {value}")
                return False
            # 범위 검증 (0 < value <= 1 가정)
            if value <= 0 or value > 1:
                logger.warning(
                    f"메트릭 범위 초과: {metric_name} = {value} (범위: 0 < x <= 1)"
                )
                return False

        # 5. 타임스탬프 신선도 및 편차 임계값 검증
        timestamp_str = getattr(self.baseline_metrics, "timestamp", None)
        if timestamp_str:
            try:
                baseline_time = datetime.fromisoformat(timestamp_str)
                age_days = (datetime.now() - baseline_time).days
                # 신선도: 30일 이내 권장
                if age_days > 30:
                    logger.warning(f"Baseline이 오래됨: {age_days}일 (권장: 30일 이내)")
                    # 경고만 하고 실패하지 않음 (사용자 판단)
            except Exception as e:
                logger.debug(f"타임스탬프 파싱 실패 (무시): {e}")

        # 편차 임계값 검증
        max_deviation = self.max_inlier_deviation
        if max_deviation > 0.2:
            logger.warning(
                f"RANSAC 편차 너무 큼: {max_deviation:.4f} > 0.2 (낮은 신뢰도)"
            )
            # 경고만 하고 실패하지 않음

        logger.info("Baseline 유효성 검증 완료: 모든 조건 통과")
        return True

    def reset(self):
        """Baseline 초기화"""
        self.baseline_metrics = None
        self.collection_frames = []
        self.is_collecting = False
        self.collection_start_time = 0.0
        logger.info("Baseline 초기화 완료")

    def _save_debug_plot(self, x_data, y_data, step_indices=None):
        """RANSAC 피팅 결과 시각화 및 저장"""
        if not x_data or not y_data:
            return

        try:
            # Use a non-interactive backend to avoid GUI operations when called
            # from background threads (prevents blocking or failures).
            import matplotlib
            try:
                matplotlib.use("Agg")
            except Exception:
                # If backend switch fails, continue; saving may still work.
                pass
            import matplotlib.pyplot as plt

            plot_dir = Path("debug_plots")
            plot_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = plot_dir / f"ransac_fit_{timestamp}.png"

            plt.figure(figsize=(12, 7))

            if step_indices:
                # 세션(단계) 수에 따라 무지개색(빨-보) 기준 균일한 색상 할당
                unique_steps = sorted(list(set(step_indices)))
                num_steps = len(unique_steps)
                # 'rainbow' 또는 'hsv' 컬러맵 사용 (0.0=빨강, 1.0=보라에 가까움)
                import matplotlib.cm as cm

                for idx, step in enumerate(unique_steps):
                    sx = [x for x, s in zip(x_data, step_indices) if s == step]
                    sy = [y for y, s in zip(y_data, step_indices) if s == step]
                    if sx:
                        # 0.0(빨강) ~ 0.8(보라/청보라) 범위로 할당하여 가시성 확보
                        color_val = idx / max(1, num_steps - 1) * 0.8
                        plt.scatter(
                            sx,
                            sy,
                            color=cm.rainbow(color_val),
                            alpha=0.6,
                            label=f"Step {step}",
                        )
            else:
                plt.scatter(x_data, y_data, color="gray", alpha=0.5, label="Samples")

            if self.ransac_model.is_fitted:
                x_min, x_max = min(x_data), max(x_data)
                x_range = np.linspace(x_min * 0.9, x_max * 1.1, 100)
                y_pred = [self.ransac_model.predict(x) for x in x_range]
                plt.plot(
                    x_range,
                    y_pred,
                    color="red",
                    linewidth=3,
                    label="RANSAC Fit (Quadratic)",
                )

                try:
                    ransac = self.ransac_model.model.named_steps["ransacregressor"]
                    plt.title(f"RANSAC: Shoulder Width vs Cheek Distance")
                except Exception:
                    plt.title("RANSAC Calibration")

            plt.xlabel("Shoulder Width (Normalized)")
            plt.ylabel("Cheek Distance (Normalized)")
            plt.legend(ncol=2, fontsize="small")
            plt.grid(True, linestyle="--", alpha=0.7)

            plt.savefig(str(filename))
            plt.close()
            logger.info(f"디버그 그래프 저장 완료: {filename}")

        except ImportError:
            logger.warning(
                "matplotlib이 설치되지 않아 디버그 그래프를 저장할 수 없습니다."
            )
        except Exception as e:
            logger.error(f"디버그 그래프 저장 실패: {e}")


def create_baseline_manager(
    config: ConfigManager, data_dir: str = "data"
) -> BaselineManager:
    """Baseline 관리자 생성 (팩토리 함수)"""
    return BaselineManager(config, data_dir)
