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
from src.utils.helpers import RansacLinearModel
from src.utils.logger import get_logger
from src.utils.paths import DATA_DIR

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

    def __init__(self, config: ConfigManager, data_dir: Optional[Path] = None):
        """
        초기화

        Args:
            config: 설정 관리자
            data_dir: 데이터 저장 디렉토리 (None이면 DATA_DIR 사용)
        """
        self.config = config
        self.data_dir = data_dir if data_dir is not None else DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.baseline_metrics: Optional[BaselineMetrics] = None
        self.collection_frames: list = []
        self.is_collecting = False
        self.collection_start_time = 0.0

        # MediaPipe 3개 모델을 동시에 돌리면 실제 처리 FPS가 낮을 수 있으므로,
        # 6단계(총 30초 수집) 데이터를 충분히 확보하기 위해 최소 유효 프레임을 설정에서 가져온다.
        baseline_config = self.config.get_baseline_config()
        self.minimum_valid_frame_count = baseline_config.get(
            "minimum_valid_frames", 30
        )

        # RANSAC 모델 3종 초기화
        self.shoulder_cheek_model = RansacLinearModel(
            min_samples=10, residual_threshold=0.01
        )
        self.shoulder_height_model = RansacLinearModel(
            min_samples=10, residual_threshold=0.01
        )
        self.eye_height_model = RansacLinearModel(
            min_samples=10, residual_threshold=0.01
        )

        self.max_inlier_deviation = 0.05
        self.mean_inlier_deviation = 0.02
        self.max_height_inlier_deviation = 0.05
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

        # 1. Shoulder-Cheek 모델 피팅
        sc_x, sc_y, s_indices = [], [], []
        for frame in self.collection_frames:
            if getattr(frame, "shoulder_width", 0) > 0 and getattr(frame, "cheek_distance", 0) > 0:
                sc_x.append(frame.shoulder_width)
                sc_y.append(frame.cheek_distance)
                s_indices.append(getattr(frame, "step_index", 0))

        if self.shoulder_cheek_model.fit(sc_x, sc_y):
            logger.info(f"Shoulder-Cheek 모델 피팅 완료 ({len(sc_x)} 샘플)")
            self._save_debug_plot(sc_x, sc_y, step_indices=s_indices, subdir="shoulder_cheek", title="Shoulder Width vs Cheek Distance")
        else:
            logger.warning("Shoulder-Cheek 모델 피팅 실패")

        # 2. Shoulder-Height 모델 피팅
        sh_x, sh_y = [], []
        for frame in self.collection_frames:
            if getattr(frame, "shoulder_width", 0) > 0 and getattr(frame, "head_height", 0) > 0:
                sh_x.append(frame.shoulder_width)
                sh_y.append(frame.head_height)

        if self.shoulder_height_model.fit(sh_x, sh_y):
            logger.info(f"Shoulder-Height 모델 피팅 완료 ({len(sh_x)} 샘플)")
            self._save_debug_plot(sh_x, sh_y, step_indices=s_indices if len(sh_x)==len(s_indices) else None, 
                                 subdir="shoulder_height", title="Shoulder Width vs Head Height")
        else:
            logger.warning("Shoulder-Height 모델 피팅 실패")

        # 3. Eye-Height 모델 피팅
        eh_x, eh_y = [], []
        for frame in self.collection_frames:
            if getattr(frame, "eye_distance", 0) > 0 and getattr(frame, "head_height", 0) > 0:
                eh_x.append(frame.eye_distance)
                eh_y.append(frame.head_height)

        if self.eye_height_model.fit(eh_x, eh_y):
            logger.info(f"Eye-Height 모델 피팅 완료 ({len(eh_x)} 샘플)")
            self._save_debug_plot(eh_x, eh_y, step_indices=s_indices if len(eh_x)==len(s_indices) else None, 
                                 subdir="eye_height", title="Eye Distance vs Head Height")
        else:
            logger.warning("Eye-Height 모델 피팅 실패")

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
            "head_height",
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

        # 1. Shoulder-Cheek 샘플
        sc_x, sc_y, s_samples = [], [], []
        for frame in self.collection_frames:
            if getattr(frame, "shoulder_width", 0) > 0 and getattr(frame, "cheek_distance", 0) > 0:
                sc_x.append(frame.shoulder_width)
                sc_y.append(frame.cheek_distance)
                s_samples.append(getattr(frame, "step_index", 0))
        metrics["ransac_x_samples"] = sc_x
        metrics["ransac_y_samples"] = sc_y
        metrics["ransac_s_samples"] = s_samples

        # 2. Shoulder-Height 샘플
        sh_x, sh_y = [], []
        for frame in self.collection_frames:
            if getattr(frame, "shoulder_width", 0) > 0 and getattr(frame, "head_height", 0) > 0:
                sh_x.append(frame.shoulder_width)
                sh_y.append(frame.head_height)
        metrics["ransac_shx_samples"] = sh_x
        metrics["ransac_shy_samples"] = sh_y

        # 3. Eye-Height 샘플
        eh_x, eh_y = [], []
        for frame in self.collection_frames:
            if getattr(frame, "eye_distance", 0) > 0 and getattr(frame, "head_height", 0) > 0:
                eh_x.append(frame.eye_distance)
                eh_y.append(frame.head_height)
        metrics["ransac_ehx_samples"] = eh_x
        metrics["ransac_ehy_samples"] = eh_y

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

            # RANSAC 원시 샘플 리스트 저장 (모델 복원을 위해 필요)
            _SAMPLE_KEYS = {
                "ransac_x_samples", "ransac_y_samples", "ransac_s_samples",
                "ransac_shx_samples", "ransac_shy_samples",
                "ransac_ehx_samples", "ransac_ehy_samples"
            }
            
            metrics_to_save = self.baseline_metrics.metrics
            data = {
                "timestamp": self.baseline_metrics.timestamp,
                "collection_duration_seconds": (
                    self.baseline_metrics.collection_duration_seconds
                ),
                "frame_count": self.baseline_metrics.frame_count,
                "metrics": metrics_to_save,
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

            # 1. Shoulder-Cheek 모델 복원
            if "ransac_x_samples" in self.baseline_metrics.metrics:
                self.shoulder_cheek_model.fit(
                    self.baseline_metrics.metrics["ransac_x_samples"],
                    self.baseline_metrics.metrics["ransac_y_samples"]
                )

            # 2. Shoulder-Height 모델 복원
            if "ransac_shx_samples" in self.baseline_metrics.metrics:
                self.shoulder_height_model.fit(
                    self.baseline_metrics.metrics["ransac_shx_samples"],
                    self.baseline_metrics.metrics["ransac_shy_samples"]
                )

            # 3. Eye-Height 모델 복원
            if "ransac_ehx_samples" in self.baseline_metrics.metrics:
                self.eye_height_model.fit(
                    self.baseline_metrics.metrics["ransac_ehx_samples"],
                    self.baseline_metrics.metrics["ransac_ehy_samples"]
                )

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
        if self.shoulder_cheek_model.is_fitted:
            return self.shoulder_cheek_model.predict(shoulder_width)

        if self.baseline_metrics and "cheek_distance" in self.baseline_metrics.metrics:
            return self.baseline_metrics.metrics["cheek_distance"]

        return 0.0

    def get_expected_height(self, distance_proxy: float, is_shoulder: bool = True) -> float:
        """
        RANSAC 모델을 통해 현재 거리(어깨 너비 또는 눈 거리)에 대한 예상 머리 높이 산출
        """
        model = self.shoulder_height_model if is_shoulder else self.eye_height_model
        
        if model.is_fitted:
            return model.predict(distance_proxy)
            
        if self.baseline_metrics and "head_height" in self.baseline_metrics.metrics:
            return self.baseline_metrics.metrics["head_height"]
        
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
        """
        if self.baseline_metrics is None:
            logger.warning("Baseline이 로드되지 않음")
            return False

        metrics = self.baseline_metrics.metrics

        # 필수 키 검증
        required_metrics = ["cheek_distance", "shoulder_width"]
        for metric_name in required_metrics:
            if metric_name not in metrics:
                logger.warning(f"필수 지표 부재: {metric_name}")
                return False

        # frame_count 최소 기준 검증
        frame_count = getattr(self.baseline_metrics, "frame_count", 0)
        if frame_count < self.minimum_valid_frame_count:
            logger.warning(f"Baseline 프레임 부족: {frame_count} < {self.minimum_valid_frame_count}")
            return False

        # RANSAC 모델 복원 여부 확인 (최소한 shoulder_cheek은 있어야 함)
        if not self.shoulder_cheek_model.is_fitted:
            if "ransac_x_samples" in metrics:
                self.shoulder_cheek_model.fit(metrics["ransac_x_samples"], metrics["ransac_y_samples"])

        if not self.shoulder_cheek_model.is_fitted:
            logger.warning("필수 RANSAC 모델(Shoulder-Cheek)이 적합되지 않음")
            return False

        logger.info("Baseline 유효성 검증 완료")
        return True

    def reset(self):
        """Baseline 초기화"""
        self.baseline_metrics = None
        self.collection_frames = []
        self.is_collecting = False
        self.collection_start_time = 0.0
        logger.info("Baseline 초기화 완료")

    def _save_debug_plot(self, x_data, y_data, step_indices=None, subdir="others", title="RANSAC Plot"):
        """RANSAC 피팅 결과 시각화 및 저장"""
        if not x_data or not y_data:
            return

        try:
            import matplotlib
            try: matplotlib.use("Agg")
            except Exception: pass
            import matplotlib.pyplot as plt

            # 디렉토리 구조 생성: {data_dir}/debug_plots/{subdir}/
            base_plot_dir = self.data_dir / "debug_plots"
            target_dir = base_plot_dir / subdir
            target_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = target_dir / f"fit_{timestamp}.png"

            plt.figure(figsize=(10, 6))

            if step_indices:
                unique_steps = sorted(list(set(step_indices)))
                import matplotlib.cm as cm
                for idx, step in enumerate(unique_steps):
                    sx = [x for x, s in zip(x_data, step_indices) if s == step]
                    sy = [y for y, s in zip(y_data, step_indices) if s == step]
                    if sx:
                        color_val = idx / max(1, len(unique_steps) - 1) * 0.8
                        plt.scatter(sx, sy, color=cm.rainbow(color_val), alpha=0.6, label=f"Step {step}")
            else:
                plt.scatter(x_data, y_data, color="gray", alpha=0.5, label="Samples")

            # subdir에 따른 적절한 모델 선택
            target_model = None
            if subdir == "shoulder_cheek": target_model = self.shoulder_cheek_model
            elif subdir == "shoulder_height": target_model = self.shoulder_height_model
            elif subdir == "eye_height": target_model = self.eye_height_model

            if target_model and target_model.is_fitted:
                x_min, x_max = min(x_data), max(x_data)
                x_range = np.linspace(x_min * 0.9, x_max * 1.1, 100)
                y_pred = [target_model.predict(x) for x in x_range]
                plt.plot(x_range, y_pred, color="red", linewidth=2, label="RANSAC Fit")

            plt.title(title)
            plt.xlabel("X (Normalized)")
            plt.ylabel("Y (Normalized)")
            plt.legend(ncol=2, fontsize="small")
            plt.grid(True, linestyle="--", alpha=0.5)

            plt.savefig(str(filename))
            plt.close()
            logger.info(f"디버그 그래프 저장 완료: {filename}")

        except Exception as e:
            logger.error(f"디버그 그래프 저장 실패: {e}")


def create_baseline_manager(
    config: ConfigManager, data_dir: Optional[Path] = None
) -> BaselineManager:
    """Baseline 관리자 생성 (팩토리 함수)"""
    return BaselineManager(config, data_dir)