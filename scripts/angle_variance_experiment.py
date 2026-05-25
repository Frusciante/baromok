#!/usr/bin/env python3
"""
화면 각도 변화 영향 측정 실험

노트북 화면 각도가 변할 때 자세 지표가 얼마나 흔들리는지 정량 측정한다.
사용자에게 같은 자세를 유지한 채 여러 각도(기본: 0°, ±5°, ±10°, ±20°)에서
각각 30초씩 녹화하도록 안내하고, 지표별 평균/표준편차/변동계수와
0° 대비 변화율을 비교한 리포트를 생성한다.

산출물 (debug_logs/angle_experiment/{timestamp}/)
  - metadata.json        실험 설정 (각도 목록, 측정시간, 해상도 등)
  - frames_{label}.csv   조건별 원시 프레임 데이터 (시각 + 지표)
  - summary.json         조건 × 지표 집계
  - report.txt           사람이 읽는 비교 표
  - variance_plot.png    조건별 평균±표준편차 그래프 (matplotlib 있을 때)

사용 예
  python scripts/angle_variance_experiment.py
  python scripts/angle_variance_experiment.py --angles -20 -10 0 10 20 --duration 30
  python scripts/angle_variance_experiment.py --output-dir D:/temp/exp
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ConfigManager
from src.core.indicator_calculator import IndicatorCalculator, PostureIndicators
from src.core.landmark_extractor import create_landmark_extractor
from src.utils.logger import get_logger

logger = get_logger(__name__, "INFO")

DEFAULT_ANGLES = [-20, -10, -5, 0, 5, 10, 20]
DEFAULT_DURATION_S = 30.0
DEFAULT_SETTLE_S = 3.0
PROGRESS_INTERVAL_S = 1.0

METRIC_KEYS = [
    "cheek_distance",
    "eye_distance",
    "face_vertical_length",
    "shoulder_width",
    "vh_ratio",
    "cheek_eye_ratio",
    "shoulder_tilt_deg",
    "eye_line_tilt",
    "face_center_x",
    "face_center_y",
]

CSV_FIELDS = [
    "timestamp_iso",
    "elapsed_s",
    "frame_idx",
    "face_detected",
    "shoulder_detected",
    "cheek_distance",
    "eye_distance",
    "face_vertical_length",
    "shoulder_width",
    "vh_ratio",
    "cheek_eye_ratio",
    "shoulder_tilt_deg",
    "eye_line_tilt",
    "face_center_x",
    "face_center_y",
    "avg_face_conf",
    "avg_shoulder_conf",
]


def angle_label(deg: int) -> str:
    sign = "+" if deg >= 0 else "-"
    return f"{sign}{abs(deg):02d}deg"


def banner(text: str) -> None:
    bar = "=" * 78
    print()
    print(bar)
    print(text)
    print(bar)


def countdown(seconds: int, prefix: str) -> None:
    for i in range(seconds, 0, -1):
        print(f"\r  {prefix}... {i}초 ", end="", flush=True)
        time.sleep(1.0)
    print("\r  시작!" + " " * 40)


def open_camera(camera_id: int, width: int, height: int) -> cv2.VideoCapture:
    backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else 0
    cap = cv2.VideoCapture(camera_id, backend)
    if not cap.isOpened():
        raise RuntimeError(f"카메라 {camera_id}을(를) 열 수 없습니다")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info(f"카메라 열림: {actual_w}x{actual_h}")
    return cap


def reset_filters(extractor, indicator_calc) -> None:
    """조건간 EMA/One Euro 캐리오버 차단."""
    extractor.one_euro_filter = None
    for attr in ("ema_filters_x", "ema_filters_y", "one_euro_filters"):
        if hasattr(extractor, attr):
            delattr(extractor, attr)
    for f in indicator_calc.ema_filters.values():
        if hasattr(f, "reset"):
            f.reset()
    indicator_calc._shoulder_tilt_history.clear()


def capture_condition(
    cap: cv2.VideoCapture,
    extractor,
    indicator_calc: IndicatorCalculator,
    label: str,
    duration_s: float,
    csv_path: Path,
    confidence_threshold: float,
) -> List[dict]:
    """한 조건에서 duration_s 동안 프레임을 수집, CSV로 저장하고 행 목록 반환."""
    rows: List[dict] = []
    start_t = time.time()
    last_progress_t = start_t
    frame_idx = 0
    miss = 0

    with open(csv_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_FIELDS)
        writer.writeheader()

        while True:
            elapsed = time.time() - start_t
            if elapsed >= duration_s:
                break

            ret, frame = cap.read()
            if not ret:
                miss += 1
                continue

            h, w = frame.shape[:2]
            extracted = extractor.extract_landmarks(frame)
            lm = extractor.get_relevant_landmarks(
                extracted, w, h, confidence_threshold
            )
            lm_norm = extractor.normalize_landmarks(
                lm, w, h, timestamp_ms=int(time.time() * 1000)
            )
            indicators: Optional[PostureIndicators] = (
                indicator_calc.calculate_all_indicators(lm_norm, timestamp=time.time())
            )

            face_det = lm.get("face_center") is not None
            shoulder_det = (
                lm.get("left_shoulder") is not None
                and lm.get("right_shoulder") is not None
            )
            face_conf_vals = [
                v
                for k, v in lm.get("confidences", {}).items()
                if k in ("face_center", "eye_a", "eye_b", "cheek_a", "cheek_b", "chin")
            ]
            sh_conf_vals = [
                v
                for k, v in lm.get("confidences", {}).items()
                if k in ("left_shoulder", "right_shoulder")
            ]
            face_center_norm = lm_norm.get("face_center")

            row = {
                "timestamp_iso": datetime.now().isoformat(timespec="milliseconds"),
                "elapsed_s": round(elapsed, 3),
                "frame_idx": frame_idx,
                "face_detected": face_det,
                "shoulder_detected": shoulder_det,
                "cheek_distance": None,
                "eye_distance": None,
                "face_vertical_length": None,
                "shoulder_width": None,
                "vh_ratio": None,
                "cheek_eye_ratio": None,
                "shoulder_tilt_deg": None,
                "eye_line_tilt": None,
                "face_center_x": (
                    round(float(face_center_norm[0]), 6)
                    if face_center_norm
                    else None
                ),
                "face_center_y": (
                    round(float(face_center_norm[1]), 6)
                    if face_center_norm
                    else None
                ),
                "avg_face_conf": (
                    round(float(np.mean(face_conf_vals)), 4)
                    if face_conf_vals
                    else None
                ),
                "avg_shoulder_conf": (
                    round(float(np.mean(sh_conf_vals)), 4) if sh_conf_vals else None
                ),
            }

            if indicators is not None:
                eye_d = indicators.eye_distance
                row.update(
                    {
                        "cheek_distance": round(indicators.cheek_distance, 6),
                        "eye_distance": round(eye_d, 6),
                        "face_vertical_length": round(indicators.face_vertical_length, 6),
                        "shoulder_width": round(indicators.shoulder_width, 6),
                        "vh_ratio": (
                            round(indicators.face_vertical_length / eye_d, 6)
                            if eye_d
                            else None
                        ),
                        "cheek_eye_ratio": (
                            round(indicators.cheek_distance / eye_d, 6) if eye_d else None
                        ),
                        "shoulder_tilt_deg": round(indicators.shoulder_tilt_deg, 4),
                        "eye_line_tilt": round(indicators.eye_line_tilt, 4),
                    }
                )

            writer.writerow(row)
            rows.append(row)
            frame_idx += 1

            now = time.time()
            if now - last_progress_t >= PROGRESS_INTERVAL_S:
                last_progress_t = now
                remaining = max(0.0, duration_s - elapsed)
                fps = frame_idx / max(elapsed, 1e-6)
                vh = row.get("vh_ratio")
                vh_str = f"{vh:.3f}" if vh is not None else "  N/A"
                print(
                    f"\r  [{label}] 남은시간 {remaining:5.1f}s | "
                    f"frames={frame_idx} ({fps:.1f}fps) | "
                    f"face={int(face_det)} sh={int(shoulder_det)} | vh={vh_str}  ",
                    end="",
                    flush=True,
                )

    print()
    print(
        f"  → 수집 {frame_idx} 프레임 / 캡처 실패 {miss} / 저장 {csv_path.name}"
    )
    return rows


def summarize_condition(label: str, rows: List[dict]) -> dict:
    n = len(rows)
    face_det = sum(1 for r in rows if r["face_detected"])
    shoulder_det = sum(1 for r in rows if r["shoulder_detected"])
    metrics_out: dict = {}
    for key in METRIC_KEYS:
        vals = [r[key] for r in rows if r[key] is not None]
        if not vals:
            metrics_out[key] = None
            continue
        arr = np.array(vals, dtype=float)
        mean = float(arr.mean())
        std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
        cv = float(std / abs(mean)) if abs(mean) > 1e-9 else None
        metrics_out[key] = {
            "n": len(vals),
            "mean": round(mean, 6),
            "std": round(std, 6),
            "cv": round(cv, 6) if cv is not None else None,
            "min": round(float(arr.min()), 6),
            "max": round(float(arr.max()), 6),
            "range": round(float(arr.max() - arr.min()), 6),
        }
    return {
        "label": label,
        "n_frames": n,
        "face_detection_rate": round(face_det / max(n, 1), 4),
        "shoulder_detection_rate": round(shoulder_det / max(n, 1), 4),
        "metrics": metrics_out,
    }


def build_report(summaries: List[dict], baseline_label: str) -> str:
    baseline = next((s for s in summaries if s["label"] == baseline_label), None)
    lines: List[str] = []

    lines.append("=" * 90)
    lines.append(" 화면 각도 변화 영향 측정 — 요약 리포트")
    lines.append(f" 생성 시각: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f" 기준 조건: {baseline_label}")
    lines.append("=" * 90)
    lines.append("")

    lines.append("[검출률]")
    lines.append(
        f"  {'조건':<10} {'N':>6} {'face_det%':>12} {'shoulder_det%':>16}"
    )
    for s in summaries:
        lines.append(
            f"  {s['label']:<10} {s['n_frames']:>6} "
            f"{s['face_detection_rate']*100:>11.1f}% "
            f"{s['shoulder_detection_rate']*100:>15.1f}%"
        )
    lines.append("")

    for mk in METRIC_KEYS:
        lines.append(f"[{mk}]  (Δ% = 기준 대비 평균 변화율, CV = std/|mean|)")
        lines.append(
            f"  {'조건':<10} {'mean':>14} {'std':>14} {'CV':>10} {'Δ%':>10}"
        )
        base_mean = (
            baseline["metrics"][mk]["mean"]
            if baseline and baseline["metrics"].get(mk)
            else None
        )
        for s in summaries:
            m = s["metrics"].get(mk)
            if m is None:
                lines.append(f"  {s['label']:<10}    데이터 없음")
                continue
            cv_str = (
                f"{m['cv']*100:>8.2f}%" if m.get("cv") is not None else "     N/A"
            )
            if s["label"] == baseline_label:
                delta_str = "    base"
            elif base_mean and abs(base_mean) > 1e-9:
                delta = (m["mean"] - base_mean) / abs(base_mean) * 100
                delta_str = f"{delta:>+8.2f}%"
            else:
                delta_str = "     N/A"
            lines.append(
                f"  {s['label']:<10} {m['mean']:>14.5f} {m['std']:>14.5f} "
                f"{cv_str:>10} {delta_str:>10}"
            )
        lines.append("")

    lines.append("=" * 90)
    lines.append(" 하이라이트 — 각도 변화에 가장 민감한 지표")
    lines.append("=" * 90)
    sensitivity: List[tuple] = []
    for mk in METRIC_KEYS:
        if not baseline or not baseline["metrics"].get(mk):
            continue
        base = baseline["metrics"][mk]["mean"]
        if abs(base) < 1e-9:
            continue
        worst = 0.0
        worst_label = ""
        for s in summaries:
            if s["label"] == baseline_label:
                continue
            m = s["metrics"].get(mk)
            if m is None:
                continue
            delta = (m["mean"] - base) / abs(base) * 100
            if abs(delta) > abs(worst):
                worst = delta
                worst_label = s["label"]
        sensitivity.append((mk, worst, worst_label))
    sensitivity.sort(key=lambda r: abs(r[1]), reverse=True)
    for mk, worst, lbl in sensitivity:
        lines.append(f"  {mk:<22}  최대 Δ% = {worst:+8.2f}%   at {lbl}")
    lines.append("")
    lines.append("해석 팁:")
    lines.append("  - |Δ%| > 5% 이면 EMA/One Euro 잡음 수준을 넘어 의미 있는 변화")
    lines.append("  - CV > 5% 이면 그 조건에서 지표 자체가 불안정 (랜드마크 흔들림)")
    lines.append("  - face_center_x/y 가 크게 변하면 카메라 평행이동 효과")
    lines.append("  - vh_ratio / cheek_eye_ratio 변화는 자세 판정에 직접 영향")
    return "\n".join(lines)


def plot_summary(summaries: List[dict], output_path: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        logger.warning(f"matplotlib 사용 불가 — plot 생략: {e}")
        return

    plot_keys = [
        "cheek_distance",
        "eye_distance",
        "face_vertical_length",
        "vh_ratio",
        "cheek_eye_ratio",
        "shoulder_width",
    ]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes = axes.flatten()
    x = list(range(len(summaries)))
    xticks = [s["label"] for s in summaries]

    for i, mk in enumerate(plot_keys):
        ax = axes[i]
        means: List[Optional[float]] = []
        stds: List[float] = []
        for s in summaries:
            m = s["metrics"].get(mk)
            if m is None:
                means.append(None)
                stds.append(0.0)
            else:
                means.append(m["mean"])
                stds.append(m["std"])
        valid_x = [xi for xi, m in zip(x, means) if m is not None]
        valid_m = [m for m in means if m is not None]
        valid_s = [sd for sd, m in zip(stds, means) if m is not None]
        ax.errorbar(
            valid_x, valid_m, yerr=valid_s, marker="o", capsize=4, color="steelblue"
        )
        ax.set_title(mk, fontsize=10)
        ax.set_xticks(x)
        ax.set_xticklabels(xticks, rotation=30, ha="right", fontsize=8)
        ax.grid(True, alpha=0.3)

    fig.suptitle("Screen angle vs posture metrics (mean ± std)", fontsize=12)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    logger.info(f"플롯 저장: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="화면 각도 변화에 따른 자세 지표 흔들림 측정"
    )
    parser.add_argument("--camera-id", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument(
        "--angles",
        type=int,
        nargs="+",
        default=DEFAULT_ANGLES,
        help="측정 각도 목록 (음수=앞으로 기울임, 양수=뒤로 기울임, 0=기준)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION_S,
        help="조건별 측정 시간(초)",
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=DEFAULT_SETTLE_S,
        help="조건 시작 전 안정화 대기(초)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "debug_logs" / "angle_experiment"),
        help="결과 저장 디렉토리 (기본: debug_logs/angle_experiment)",
    )
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    args = parser.parse_args()

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir) / run_ts
    out_dir.mkdir(parents=True, exist_ok=True)

    banner(" 화면 각도 변화 영향 측정 실험")
    print(f"  실행 시각:       {datetime.now().isoformat(timespec='seconds')}")
    print(f"  저장 경로:       {out_dir}")
    print(f"  측정 각도:       {args.angles}")
    print(f"  조건별 측정시간: {args.duration:.0f}초  (+안정화 {args.settle:.0f}초)")
    print(f"  카메라:          id={args.camera_id}, {args.width}x{args.height}")
    print()
    print("  실험 절차:")
    print("    1) 의자에 평소 작업 자세로 앉습니다.")
    print("    2) 안내된 각도로 노트북 화면을 조정합니다.")
    print("    3) 같은 자세를 유지한 채 측정을 마칩니다 (몸을 움직이지 마세요).")
    print("    4) 다음 각도가 안내되면 화면만 조정합니다.")
    print()
    input("  준비되었으면 Enter를 누르세요... ")

    config = ConfigManager()
    extractor = create_landmark_extractor()
    indicator_calc = IndicatorCalculator(config=config)

    cap = open_camera(args.camera_id, args.width, args.height)
    try:
        meta = {
            "started_at": datetime.now().isoformat(),
            "angles_deg": args.angles,
            "duration_per_condition_s": args.duration,
            "settle_s": args.settle,
            "camera_id": args.camera_id,
            "frame_width": args.width,
            "frame_height": args.height,
            "confidence_threshold": args.confidence_threshold,
        }
        with open(out_dir / "metadata.json", "w", encoding="utf-8") as fp:
            json.dump(meta, fp, ensure_ascii=False, indent=2)

        summaries: List[dict] = []
        for deg in args.angles:
            label = angle_label(deg)
            banner(f" 조건 {deg:+d}°   ({label})")
            print(f"  화면 각도를 {deg:+d}°로 맞춰 주세요.")
            print(f"  (0°는 평소 작업 시 화면 각도. 음수=화면을 사용자 쪽으로,")
            print(f"   양수=화면을 뒤로 기울입니다.)")
            print(f"  같은 자세를 유지하고 준비되면 Enter를 누르세요.")
            input("  >> Enter ")
            reset_filters(extractor, indicator_calc)
            countdown(int(args.settle), prefix="자세 안정화")
            csv_path = out_dir / f"frames_{label}.csv"
            rows = capture_condition(
                cap,
                extractor,
                indicator_calc,
                label,
                duration_s=args.duration,
                csv_path=csv_path,
                confidence_threshold=args.confidence_threshold,
            )
            summary = summarize_condition(label, rows)
            summaries.append(summary)
            face_pct = summary["face_detection_rate"] * 100
            shoulder_pct = summary["shoulder_detection_rate"] * 100
            print(
                f"  요약: face_det={face_pct:.1f}% / shoulder_det={shoulder_pct:.1f}%"
            )
            if face_pct < 80.0:
                print(
                    "  ! 경고: 얼굴 검출률이 낮습니다. 다음 조건 전에 자세/조명을 점검하세요."
                )

        with open(out_dir / "summary.json", "w", encoding="utf-8") as fp:
            json.dump(summaries, fp, ensure_ascii=False, indent=2)
        baseline = angle_label(0) if 0 in args.angles else summaries[0]["label"]
        report = build_report(summaries, baseline_label=baseline)
        with open(out_dir / "report.txt", "w", encoding="utf-8") as fp:
            fp.write(report)
        plot_summary(summaries, out_dir / "variance_plot.png")

        banner(" 실험 완료")
        print(report)
        print()
        print(f"  모든 산출물 저장 경로:")
        print(f"    {out_dir}")
        print()
        return 0
    finally:
        cap.release()


if __name__ == "__main__":
    sys.exit(main())
