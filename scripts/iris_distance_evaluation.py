#!/usr/bin/env python3
"""
홍채 거리 알고리즘 오차 평가 스크립트

실측 데이터셋(data_test/iris_distance/d{거리}_{순번}_{조건}.jpg)을 운영 코드
(LandmarkExtractor -> IndicatorCalculator)에 그대로 통과시켜 계산 거리와 실측 거리를 비교한다.
같은 랜드마크로 홍채 지름 계산 방식 후보들도 함께 계산해 한 표로 비교한다.

출력 (data_test/iris_distance/results/):
  evaluation_{시간}.csv          이미지별 실측/계산 거리
  evaluation_{시간}_summary.txt  방식별/조건별/거리별 오차 요약
  evaluation_{시간}.png          실측 vs 계산 산점도

실행: python scripts/iris_distance_evaluation.py [--dataset-directory 경로]
"""

import argparse
import csv
import math
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from iris_distance_common import (  # noqa: E402
    CONDITIONS,
    DATASET_DIRECTORY,
    SampleInformation,
    parse_sample_file_name,
    read_image_unicode_safe,
)

# ── 평가 기준 (계획서 7장 확정 사항) ──────────────────────────────
TARGET_MEAN_ABSOLUTE_ERROR_CM = 3.0
TARGET_MEAN_PERCENT_ERROR = 5.0

# ── MediaPipe FaceMesh 홍채 인덱스 (첫 번째 = 중심, 나머지 4개 = 외곽) ──
FIRST_IRIS_INDICES = (468, 469, 470, 471, 472)
SECOND_IRIS_INDICES = (473, 474, 475, 476, 477)

# VIDEO 모드 추적 상태를 정지 이미지에 맞추기 위해 같은 이미지를 여러 번 넣는다
WARMUP_REPEAT_COUNT = 3
WARMUP_INTERVAL_SECONDS = 0.01

# 운영 코드(indicator_calculator.py)에 하드코딩된 오프셋 — 오프셋 제거 효과 비교용
LEGACY_OFFSET_CM = 20.0

PRODUCTION_APPLICATION = "production_app"
PRODUCTION_WITHOUT_OFFSET = "production_without_offset"
DIAMETER_METHODS = (
    "legacy",
    "contour_mean_radius",
    "horizontal",
    "vertical",
    "max_horizontal_vertical",
)
COMBINE_METHODS = ("min", "mean")


# ════════════════════════════════════════════════════════════════
# 데이터셋
# ════════════════════════════════════════════════════════════════
def discover_samples(directory: Path) -> List[Tuple[Path, SampleInformation]]:
    """규칙에 맞는 파일만 거리/조건/순번 순서로 모은다."""
    samples = []
    for path in sorted(directory.iterdir()):
        information = parse_sample_file_name(path.name)
        if information is not None:
            samples.append((path, information))
        elif path.is_file():
            print(f"[건너뜀] 파일명 규칙 불일치: {path.name}")
    samples.sort(key=lambda item: (item[1].distance_cm, item[1].condition, item[1].sequence))
    return samples


# ════════════════════════════════════════════════════════════════
# 운영 파이프라인 실행
# ════════════════════════════════════════════════════════════════
def prepare_ascii_model_directory() -> str:
    """MediaPipe는 비ASCII 경로의 .task 파일을 열지 못하므로 필요하면 ASCII 임시 경로로 복사한다."""
    from src.utils.paths import MODELS_DIR

    models_directory = Path(MODELS_DIR)
    if str(models_directory).isascii():
        return str(models_directory)
    ascii_directory = Path(tempfile.gettempdir()) / "baromok_iris_evaluation_models"
    if not str(ascii_directory).isascii():
        raise RuntimeError(f"ASCII 임시 경로를 확보하지 못했습니다: {ascii_directory}")
    ascii_directory.mkdir(parents=True, exist_ok=True)
    for task_file in models_directory.glob("*.task"):
        target = ascii_directory / task_file.name
        if not target.exists() or target.stat().st_size != task_file.stat().st_size:
            shutil.copy2(task_file, target)
    print(f"[안내] 모델 경로에 한글이 있어 임시 경로로 복사해 사용합니다: {ascii_directory}")
    return str(ascii_directory)


class ProductionPipelineRunner:
    """앱(CameraWorker.process_frame)과 같은 순서로 운영 코드를 호출한다."""

    def __init__(self):
        from src.config import get_config
        from src.core.indicator_calculator import IndicatorCalculator
        from src.core.landmark_extractor import LandmarkExtractor

        self.config = get_config()
        self.landmark_extractor = LandmarkExtractor(model_base_path=prepare_ascii_model_directory())
        if self.landmark_extractor.face_landmarker is None:
            raise RuntimeError("Face Landmarker를 불러오지 못했습니다. 모델 파일을 확인하세요.")
        self.indicator_calculator = IndicatorCalculator(self.config)

    def read_eye_monitoring_settings(self) -> dict:
        """거리 계산에 쓰이는 설정값을 운영 코드와 같은 키로 읽는다."""
        eye_configuration = self.config.get_posture_criteria().get("eye_monitoring", {})
        return {
            "iris_diameter_mm": float(eye_configuration.get("iris_diameter_mm", 11.5)),
            "camera_horizontal_fov_deg": float(eye_configuration.get("camera_horizontal_fov_deg", 60.0)),
            "configured_frame_width": int(self.config.get_app_setting("camera_resolution_width", 1280)),
        }

    def _reset_temporal_state(self):
        """이전 이미지의 고스트/필터 값이 다음 이미지에 섞이지 않도록 초기화한다 (실험 전용)."""
        self.landmark_extractor._ghost_windows.clear()
        self.landmark_extractor._one_euro_filters.clear()
        self.indicator_calculator._eye_close_start_time = None

    def run(self, image: np.ndarray) -> dict:
        self._reset_temporal_state()
        extracted = None
        for _ in range(WARMUP_REPEAT_COUNT):
            extracted = self.landmark_extractor.extract_landmarks(image)
            time.sleep(WARMUP_INTERVAL_SECONDS)

        frame_height, frame_width = image.shape[:2]
        relevant = self.landmark_extractor.get_relevant_landmarks(
            extracted, frame_width=frame_width, frame_height=frame_height
        )
        normalized = self.landmark_extractor.normalize_landmarks(
            relevant, frame_width=frame_width, frame_height=frame_height,
            timestamp_ms=extracted.frame_timestamp_ms, baseline_mode=True,
        )
        indicators = self.indicator_calculator.calculate_all_indicators(
            normalized, timestamp=time.time(), baseline_mode=True
        )
        return {
            "frame_width": frame_width,
            "frame_height": frame_height,
            "face_landmarks": extracted.face.landmarks if extracted.face is not None else None,
            "legacy_diameters": (
                relevant.get("left_iris_diameter_px"),
                relevant.get("right_iris_diameter_px"),
            ),
            "production_distance_cm": indicators.eye_screen_distance_cm if indicators else None,
        }


# ════════════════════════════════════════════════════════════════
# 홍채 지름 / 거리 계산 후보
# ════════════════════════════════════════════════════════════════
def extract_iris_points_px(face_landmarks, indices, frame_width, frame_height) -> Optional[np.ndarray]:
    """정규화 좌표를 실수 px 좌표로 변환한다 (int 절사 없음)."""
    if face_landmarks is None or len(face_landmarks) <= max(indices):
        return None
    return np.array(
        [(face_landmarks[i][0] * frame_width, face_landmarks[i][1] * frame_height) for i in indices],
        dtype=np.float64,
    )


def calculate_diameter_candidates(iris_points: np.ndarray) -> Dict[str, float]:
    """중심점을 제외한 외곽 4점으로 지름 후보를 계산한다."""
    contour = iris_points[1:5]
    first_pair = contour[0] - contour[2]
    second_pair = contour[1] - contour[3]
    # 가로/세로 판정은 인덱스 가정 대신 실제 방향으로 결정
    if abs(first_pair[0]) >= abs(second_pair[0]):
        horizontal_vector, vertical_vector = first_pair, second_pair
    else:
        horizontal_vector, vertical_vector = second_pair, first_pair
    horizontal = float(np.linalg.norm(horizontal_vector))
    vertical = float(np.linalg.norm(vertical_vector))
    centroid = contour.mean(axis=0)
    return {
        "contour_mean_radius": 2.0 * float(np.mean(np.linalg.norm(contour - centroid, axis=1))),
        "horizontal": horizontal,
        "vertical": vertical,
        "max_horizontal_vertical": max(horizontal, vertical),
    }


def calculate_focal_length_px(frame_width: int, horizontal_fov_deg: float) -> float:
    return float(frame_width) / (2.0 * math.tan(math.radians(horizontal_fov_deg) / 2.0))


def calculate_distance_cm(diameter_px: Optional[float], focal_length_px: float, iris_diameter_mm: float) -> Optional[float]:
    if not diameter_px or diameter_px <= 0:
        return None
    return (iris_diameter_mm * focal_length_px / diameter_px) / 10.0


def combine_eye_distances(distances: List[Optional[float]], combine_method: str) -> Optional[float]:
    valid = [value for value in distances if value is not None]
    if not valid:
        return None
    return min(valid) if combine_method == "min" else float(np.mean(valid))


def estimate_all_methods(pipeline_result: dict, settings: dict) -> Dict[str, Optional[float]]:
    """운영 결과 + 지름 후보 x 양안 결합 방식별 거리 추정치를 계산한다."""
    frame_width = pipeline_result["frame_width"]
    frame_height = pipeline_result["frame_height"]
    iris_mm = settings["iris_diameter_mm"]
    fov_deg = settings["camera_horizontal_fov_deg"]
    actual_focal = calculate_focal_length_px(frame_width, fov_deg)
    configured_focal = calculate_focal_length_px(settings["configured_frame_width"], fov_deg)

    estimates: Dict[str, Optional[float]] = {PRODUCTION_APPLICATION: pipeline_result["production_distance_cm"]}

    legacy_left, legacy_right = pipeline_result["legacy_diameters"]
    estimates[PRODUCTION_WITHOUT_OFFSET] = combine_eye_distances(
        [calculate_distance_cm(d, configured_focal, iris_mm) for d in (legacy_left, legacy_right)], "min"
    )

    per_eye_diameters: Dict[str, List[Optional[float]]] = {"legacy": [legacy_left, legacy_right]}
    for indices in (FIRST_IRIS_INDICES, SECOND_IRIS_INDICES):
        points = extract_iris_points_px(pipeline_result["face_landmarks"], indices, frame_width, frame_height)
        candidates = calculate_diameter_candidates(points) if points is not None else {}
        for method in DIAMETER_METHODS[1:]:
            per_eye_diameters.setdefault(method, []).append(candidates.get(method))

    for method in DIAMETER_METHODS:
        distances = [calculate_distance_cm(d, actual_focal, iris_mm) for d in per_eye_diameters[method]]
        for combine_method in COMBINE_METHODS:
            estimates[f"{method}_{combine_method}"] = combine_eye_distances(distances, combine_method)
    return estimates


# ════════════════════════════════════════════════════════════════
# 통계
# ════════════════════════════════════════════════════════════════
def calculate_error_statistics(true_values: np.ndarray, estimated_values: np.ndarray) -> Optional[dict]:
    if len(true_values) == 0:
        return None
    errors = estimated_values - true_values
    percent_errors = np.abs(errors) / true_values * 100.0
    slope, intercept = (np.polyfit(true_values, estimated_values, 1)
                        if len(np.unique(true_values)) >= 2 else (float("nan"), float("nan")))
    # 곱셈형 보정 계수 k: true ≈ k * estimated 의 최소자승 해
    best_scale = float(np.sum(true_values * estimated_values) / np.sum(estimated_values ** 2))
    scaled_errors = best_scale * estimated_values - true_values
    return {
        "count": int(len(true_values)),
        "mean_absolute_error": float(np.mean(np.abs(errors))),
        "bias": float(np.mean(errors)),
        "error_standard_deviation": float(np.std(errors)),
        "mean_percent_error": float(np.mean(percent_errors)),
        "slope": float(slope),
        "intercept": float(intercept),
        "best_scale": best_scale,
        "scaled_mean_absolute_error": float(np.mean(np.abs(scaled_errors))),
        "scaled_mean_percent_error": float(np.mean(np.abs(scaled_errors) / true_values * 100.0)),
    }


def collect_pairs(rows: List[dict], method: str, condition: Optional[str] = None,
                  distance_cm: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
    pairs = [
        (row["true_distance_cm"], row[method]) for row in rows
        if row[method] is not None
        and (condition is None or row["condition"] == condition)
        and (distance_cm is None or row["true_distance_cm"] == distance_cm)
    ]
    if not pairs:
        return np.array([]), np.array([])
    array = np.array(pairs, dtype=np.float64)
    return array[:, 0], array[:, 1]


def is_within_target(statistics: dict) -> bool:
    return (statistics["mean_absolute_error"] <= TARGET_MEAN_ABSOLUTE_ERROR_CM
            or statistics["mean_percent_error"] <= TARGET_MEAN_PERCENT_ERROR)


# ════════════════════════════════════════════════════════════════
# 보고서
# ════════════════════════════════════════════════════════════════
class ReportWriter:
    """콘솔 출력과 요약 파일 저장을 동시에 처리한다."""

    def __init__(self):
        self.lines: List[str] = []

    def write(self, text: str = ""):
        print(text)
        self.lines.append(text)

    def save(self, path: Path):
        path.write_text("\n".join(self.lines), encoding="utf-8")


def format_statistics_row(name: str, statistics: Optional[dict]) -> str:
    if statistics is None:
        return f"{name:<34} (데이터 없음)"
    return (f"{name:<34} n={statistics['count']:>3}  MAE={statistics['mean_absolute_error']:6.2f}  "
            f"bias={statistics['bias']:+7.2f}  sd={statistics['error_standard_deviation']:5.2f}  "
            f"err%={statistics['mean_percent_error']:5.1f}  slope={statistics['slope']:5.3f}  "
            f"icpt={statistics['intercept']:+6.2f}  k={statistics['best_scale']:5.3f}  "
            f"MAE(k)={statistics['scaled_mean_absolute_error']:5.2f}  err%(k)={statistics['scaled_mean_percent_error']:4.1f}")


def write_method_table(report: ReportWriter, rows: List[dict], methods: List[str], condition: Optional[str]) -> Dict[str, dict]:
    title = "전체" if condition is None else f"조건={condition}"
    report.write(f"\n[방식별 오차 — {title}] (단위 cm, k=곱셈 보정 계수, MAE(k)=k 적용 후)")
    results = {}
    for method in methods:
        statistics = calculate_error_statistics(*collect_pairs(rows, method, condition))
        results[method] = statistics
        report.write(format_statistics_row(method, statistics))
    return results


def write_distance_table(report: ReportWriter, rows: List[dict], method: str, distances: List[int]):
    report.write(f"\n[거리별 오차 — {method}]")
    report.write(f"{'실측':>6} {'조건':>8} {'n':>3} {'평균추정':>9} {'평균오차':>9} {'오차%':>7}")
    for distance_cm in distances:
        for condition in CONDITIONS:
            true_values, estimated_values = collect_pairs(rows, method, condition, distance_cm)
            if len(true_values) == 0:
                continue
            mean_error = float(np.mean(estimated_values - true_values))
            report.write(f"{distance_cm:>6} {condition:>8} {len(true_values):>3} "
                         f"{np.mean(estimated_values):>9.2f} {mean_error:>+9.2f} {mean_error / distance_cm * 100:>+7.1f}")


def write_condition_comparison(report: ReportWriter, rows: List[dict], method: str):
    """안경 착용/미착용 차이가 목표 정확도 이내인지 판정한다."""
    report.write(f"\n[안경 착용 영향 — {method}]")
    by_condition = {c: calculate_error_statistics(*collect_pairs(rows, method, c)) for c in CONDITIONS}
    if any(statistics is None for statistics in by_condition.values()):
        report.write("두 조건 데이터가 모두 있어야 비교할 수 있습니다.")
        return
    bias_difference = abs(by_condition["glasses"]["bias"] - by_condition["bare"]["bias"])
    scale_difference_percent = abs(by_condition["glasses"]["best_scale"] / by_condition["bare"]["best_scale"] - 1.0) * 100
    report.write(f"편향 차이 = {bias_difference:.2f}cm, 보정 계수 차이 = {scale_difference_percent:.1f}%")
    same_treatment = (bias_difference <= TARGET_MEAN_ABSOLUTE_ERROR_CM
                      or scale_difference_percent <= TARGET_MEAN_PERCENT_ERROR)
    report.write("판정: " + ("차이가 목표 정확도 이내 → 구분 없이 처리 가능" if same_treatment
                            else "차이가 목표 정확도 초과 → 조건별 처리 검토 필요"))


def save_rows_to_csv(rows: List[dict], fieldnames: List[str], path: Path):
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: ("" if row.get(key) is None else row.get(key)) for key in fieldnames})


def save_scatter_plot(rows: List[dict], methods: List[str], path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    column_count = min(3, len(methods))
    row_count = math.ceil(len(methods) / column_count)
    figure, axes = plt.subplots(row_count, column_count, figsize=(5 * column_count, 4.5 * row_count), squeeze=False)
    all_true = [row["true_distance_cm"] for row in rows]
    axis_limit = (min(all_true) * 0.7, max(all_true) * 1.4)
    markers = {"bare": ("o", "tab:blue"), "glasses": ("^", "tab:orange")}

    for axis, method in zip(axes.flat, methods):
        for condition in CONDITIONS:
            true_values, estimated_values = collect_pairs(rows, method, condition)
            if len(true_values):
                marker, color = markers[condition]
                axis.scatter(true_values, estimated_values, marker=marker, color=color, alpha=0.6, label=condition)
        axis.plot(axis_limit, axis_limit, "k--", linewidth=1, label="y = x")
        axis.set_xlim(axis_limit); axis.set_ylim(axis_limit)
        axis.set_title(method, fontsize=10)
        axis.set_xlabel("true distance (cm)"); axis.set_ylabel("estimated (cm)")
        axis.grid(alpha=0.3); axis.legend(fontsize=8)
    for axis in list(axes.flat)[len(methods):]:
        axis.axis("off")
    figure.tight_layout()
    figure.savefig(path, dpi=110)
    plt.close(figure)


# ════════════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════════════
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="홍채 거리 알고리즘 오차 평가")
    parser.add_argument("--dataset-directory", type=Path, default=DATASET_DIRECTORY)
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    dataset_directory: Path = arguments.dataset_directory
    if not dataset_directory.exists():
        print(f"[오류] 데이터셋 폴더가 없습니다: {dataset_directory}")
        sys.exit(1)

    samples = discover_samples(dataset_directory)
    if not samples:
        print("[오류] 평가할 이미지가 없습니다. iris_distance_capture.py로 먼저 촬영하세요.")
        sys.exit(1)

    runner = ProductionPipelineRunner()
    settings = runner.read_eye_monitoring_settings()
    method_names = [PRODUCTION_APPLICATION, PRODUCTION_WITHOUT_OFFSET] + [
        f"{method}_{combine}" for method in DIAMETER_METHODS for combine in COMBINE_METHODS
    ]

    rows: List[dict] = []
    failures: List[str] = []
    for index, (path, information) in enumerate(samples, start=1):
        image = read_image_unicode_safe(path)
        if image is None:
            failures.append(f"{path.name}: 이미지 읽기 실패")
            continue
        estimates = estimate_all_methods(runner.run(image), settings)
        if estimates[PRODUCTION_APPLICATION] is None and estimates["horizontal_mean"] is None:
            failures.append(f"{path.name}: 얼굴/홍채 미검출")
        rows.append({
            "file_name": path.name,
            "true_distance_cm": information.distance_cm,
            "condition": information.condition,
            "frame_width": image.shape[1],
            "frame_height": image.shape[0],
            **estimates,
        })
        print(f"\r처리 중 {index}/{len(samples)}", end="")
    print()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_directory = dataset_directory / "results"
    result_directory.mkdir(parents=True, exist_ok=True)
    report = ReportWriter()
    report.write(f"홍채 거리 평가 — {timestamp}")
    report.write(f"데이터셋: {dataset_directory}  (이미지 {len(samples)}장, 실패 {len(failures)}장)")
    report.write(f"설정: iris_diameter_mm={settings['iris_diameter_mm']}, "
                 f"HFOV={settings['camera_horizontal_fov_deg']}°, 설정 해상도 폭={settings['configured_frame_width']}")
    frame_widths = sorted({row["frame_width"] for row in rows})
    report.write(f"실제 이미지 폭: {frame_widths}"
                 + ("  [H5 경고] 설정 해상도 폭과 다름" if frame_widths != [settings["configured_frame_width"]] else ""))
    report.write(f"목표: MAE ≤ {TARGET_MEAN_ABSOLUTE_ERROR_CM}cm 또는 평균 오차율 ≤ {TARGET_MEAN_PERCENT_ERROR}%")
    for failure in failures:
        report.write(f"  [실패] {failure}")

    overall = write_method_table(report, rows, method_names, None)
    for condition in CONDITIONS:
        write_method_table(report, rows, method_names, condition)

    candidates = {name: stats for name, stats in overall.items()
                  if stats and name not in (PRODUCTION_APPLICATION, PRODUCTION_WITHOUT_OFFSET)}
    best_raw = min(candidates, key=lambda name: candidates[name]["mean_absolute_error"]) if candidates else None
    best_scaled = min(candidates, key=lambda name: candidates[name]["scaled_mean_absolute_error"]) if candidates else None
    report.write(f"\n보정 없이 가장 정확한 방식: {best_raw}")
    report.write(f"곱셈 보정(k) 적용 시 가장 정확한 방식: {best_scaled}")
    if best_raw:
        report.write(f"  {best_raw} 목표 달성: {'예' if is_within_target(candidates[best_raw]) else '아니오'}")

    distances = sorted({row["true_distance_cm"] for row in rows})
    for method in dict.fromkeys([PRODUCTION_APPLICATION, PRODUCTION_WITHOUT_OFFSET, best_raw, best_scaled]):
        if method:
            write_distance_table(report, rows, method, distances)
    if best_scaled:
        write_condition_comparison(report, rows, best_scaled)

    csv_path = result_directory / f"evaluation_{timestamp}.csv"
    summary_path = result_directory / f"evaluation_{timestamp}_summary.txt"
    plot_path = result_directory / f"evaluation_{timestamp}.png"
    save_rows_to_csv(rows, ["file_name", "true_distance_cm", "condition", "frame_width", "frame_height"] + method_names, csv_path)
    plot_methods = list(dict.fromkeys([PRODUCTION_APPLICATION, PRODUCTION_WITHOUT_OFFSET, "legacy_mean",
                                       best_raw, best_scaled, "max_horizontal_vertical_mean"]))
    save_scatter_plot(rows, [m for m in plot_methods if m], plot_path)

    report.write(f"\n저장: {csv_path.name}, {summary_path.name}, {plot_path.name}")
    report.save(summary_path)


if __name__ == "__main__":
    main()
