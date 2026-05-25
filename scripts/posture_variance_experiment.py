#!/usr/bin/env python3
"""
자세별 지표 변화 측정 실험

목적: 사용자가 자세별로 의도적으로 취했을 때 각 지표가 baseline(바른자세) 대비
어떻게 변하는지 정량 측정한다. 결과로 "어떤 지표가 어떤 자세를 잘 구별하는지"
와 "임계값 후보"를 산출한다.

기본 자세 세트:
  1. neutral             — 바른 자세 (baseline 기준)
  2. forward_head_full   — 거북목 (몸 + 머리 동시에 앞으로)
  3. forward_head_only   — 머리만 앞으로 (몸은 그대로) ※노트북 핵심 케이스
  4. recline             — 기댄 자세 (몸·머리 뒤로)
  5. chin_rest           — 턱괴기 (한쪽 손으로)
  6. yaw_turn            — 고개 좌우 회전 (오탐 회피 검증용)

각 자세 30초 측정 → 평균/표준편차/CV + neutral 대비 Δ% 산출.
실험 절차: 측정 시작 안내 → 자세 잡고 Enter → 안정화 3초 → 30초 캡처.

산출물 (debug_logs/posture_experiment/{timestamp}/)
  - metadata.json
  - frames_{posture}.csv
  - summary.json
  - report.txt        (사람이 읽는 비교 표 + 자세 판별 매트릭스)
  - variance_plot.png

사용 예
  python scripts/posture_variance_experiment.py
  python scripts/posture_variance_experiment.py --postures neutral forward_head_only recline --duration 30
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

DEFAULT_POSTURES = [
    "neutral",
    "forward_head_full",
    "forward_head_only",
    "recline",
    "chin_rest",
    "yaw_turn",
]
DEFAULT_DURATION_S = 30.0
DEFAULT_SETTLE_S = 3.0
PROGRESS_INTERVAL_S = 1.0

POSTURE_INSTRUCTIONS = {
    "neutral": (
        "바른 자세 (기준)",
        [
            "의자에 등을 기대고 척추를 곧게 세웁니다.",
            "양 어깨는 수평, 턱은 살짝 당겨 시선이 화면 중앙을 향하게 하세요.",
            "30초 동안 같은 자세를 유지합니다.",
        ],
    ),
    "forward_head_full": (
        "거북목 (몸·머리 동시 앞으로)",
        [
            "엉덩이를 의자 앞으로 빼고 상체를 화면 쪽으로 기울이세요.",
            "이때 머리도 살짝 숙이고 앞으로 빠지는 거북목 자세를 만듭니다.",
            "30초 동안 같은 자세를 유지합니다.",
        ],
    ),
    "forward_head_only": (
        "머리만 앞으로 (몸은 등받이에)",
        [
            "엉덩이와 등은 등받이에 붙인 채 그대로 둡니다.",
            "목만 앞으로 빼서 머리를 화면 쪽으로 내미세요. (시선은 화면 정면)",
            "30초 동안 같은 자세를 유지합니다.",
        ],
    ),
    "recline": (
        "기댄 자세",
        [
            "의자에 깊숙이 기대어 상체와 머리를 살짝 뒤로 젖힙니다.",
            "시선은 화면 위쪽을 보는 듯한 각도가 됩니다.",
            "30초 동안 같은 자세를 유지합니다.",
        ],
    ),
    "chin_rest": (
        "턱괴기",
        [
            "한쪽 팔꿈치를 책상에 올리고 손바닥/주먹으로 턱을 받칩니다.",
            "고개가 자연스럽게 그쪽으로 살짝 기울도록 두세요.",
            "30초 동안 같은 자세를 유지합니다.",
        ],
    ),
    "yaw_turn": (
        "고개 좌우 회전 (오탐 회피 검증)",
        [
            "몸은 그대로, 고개만 한쪽(편한 쪽)으로 30~45° 정도 돌립니다.",
            "30초 동안 같은 각도를 유지합니다.",
            "(이 자세는 '자세 불량'이 아니라, 시스템이 잘못 판정하지",
            " 않는지 확인하는 대조군입니다.)",
        ],
    ),
}

METRIC_KEYS = [
    "cheek_distance",
    "eye_distance",
    "face_vertical_length",
    "shoulder_width",
    "vh_ratio",
    "cheek_eye_ratio",
    "shoulder_tilt_deg",
    "eye_line_tilt",
    "chin_occlusion",
    "hand_face_score",
    "eye_symmetry_ratio",
    "cheek_symmetry_ratio",
    "chin_alignment_offset",
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
    "chin_occlusion",
    "hand_face_score",
    "eye_symmetry_ratio",
    "cheek_symmetry_ratio",
    "chin_alignment_offset",
    "face_center_x",
    "face_center_y",
    "avg_face_conf",
    "avg_shoulder_conf",
]


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

            row = {field: None for field in CSV_FIELDS}
            row.update(
                {
                    "timestamp_iso": datetime.now().isoformat(timespec="milliseconds"),
                    "elapsed_s": round(elapsed, 3),
                    "frame_idx": frame_idx,
                    "face_detected": face_det,
                    "shoulder_detected": shoulder_det,
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
                        round(float(np.mean(sh_conf_vals)), 4)
                        if sh_conf_vals
                        else None
                    ),
                }
            )

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
                        "chin_occlusion": round(indicators.chin_occlusion, 6),
                        "hand_face_score": round(indicators.hand_face_score, 6),
                        "eye_symmetry_ratio": round(indicators.eye_symmetry_ratio, 6),
                        "cheek_symmetry_ratio": round(
                            indicators.cheek_symmetry_ratio, 6
                        ),
                        "chin_alignment_offset": round(
                            indicators.chin_alignment_offset, 6
                        ),
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
                ce = row.get("cheek_eye_ratio")
                vh_str = f"{vh:.3f}" if vh is not None else "  N/A"
                ce_str = f"{ce:.3f}" if ce is not None else "  N/A"
                print(
                    f"\r  [{label:<20}] 남은시간 {remaining:5.1f}s | "
                    f"frames={frame_idx} ({fps:.1f}fps) | "
                    f"face={int(face_det)} sh={int(shoulder_det)} | "
                    f"vh={vh_str} ce={ce_str}  ",
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


def _delta_pct(value: float, baseline: float) -> Optional[float]:
    if baseline is None or abs(baseline) < 1e-9:
        return None
    return (value - baseline) / abs(baseline) * 100


def build_report(summaries: List[dict], baseline_label: str, screen_angle: str = "0deg") -> str:
    baseline = next((s for s in summaries if s["label"] == baseline_label), None)
    lines: List[str] = []

    lines.append("=" * 100)
    lines.append(" 자세별 지표 변화 측정 — 요약 리포트")
    lines.append(f" 생성 시각: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f" 화면 각도 태그: {screen_angle}")
    lines.append(f" 기준(baseline) 자세: {baseline_label}")
    lines.append("=" * 100)
    lines.append("")

    lines.append("[검출률]")
    lines.append(
        f"  {'자세':<22} {'N':>6} {'face_det%':>12} {'shoulder_det%':>16}"
    )
    for s in summaries:
        lines.append(
            f"  {s['label']:<22} {s['n_frames']:>6} "
            f"{s['face_detection_rate']*100:>11.1f}% "
            f"{s['shoulder_detection_rate']*100:>15.1f}%"
        )
    lines.append("")

    for mk in METRIC_KEYS:
        lines.append(f"[{mk}]  (Δ% = baseline 대비 평균 변화율, CV = std/|mean|)")
        lines.append(
            f"  {'자세':<22} {'mean':>14} {'std':>14} {'CV':>10} {'Δ%':>12}"
        )
        base_mean = (
            baseline["metrics"][mk]["mean"]
            if baseline and baseline["metrics"].get(mk)
            else None
        )
        for s in summaries:
            m = s["metrics"].get(mk)
            if m is None:
                lines.append(f"  {s['label']:<22}     데이터 없음")
                continue
            cv_str = (
                f"{m['cv']*100:>8.2f}%" if m.get("cv") is not None else "     N/A"
            )
            if s["label"] == baseline_label:
                delta_str = "      base"
            else:
                d = _delta_pct(m["mean"], base_mean)
                delta_str = f"{d:>+10.2f}%" if d is not None else "       N/A"
            lines.append(
                f"  {s['label']:<22} {m['mean']:>14.5f} {m['std']:>14.5f} "
                f"{cv_str:>10} {delta_str:>12}"
            )
        lines.append("")

    lines.append("=" * 100)
    lines.append(" 자세 판별 매트릭스 — 각 자세에서 가장 크게 변한 지표 (Top 5)")
    lines.append("=" * 100)
    for s in summaries:
        if s["label"] == baseline_label:
            continue
        deltas: List[tuple] = []
        for mk in METRIC_KEYS:
            if not baseline or not baseline["metrics"].get(mk):
                continue
            m = s["metrics"].get(mk)
            if m is None:
                continue
            base_mean = baseline["metrics"][mk]["mean"]
            d = _delta_pct(m["mean"], base_mean)
            if d is None:
                continue
            cv = m.get("cv") or 0.0
            deltas.append((mk, d, cv))
        deltas.sort(key=lambda r: abs(r[1]), reverse=True)
        lines.append(f"\n  ▸ {s['label']}")
        lines.append(f"    {'지표':<26} {'Δ%':>10} {'CV':>10}  안정성")
        for mk, d, cv in deltas[:5]:
            stable = "안정" if cv < 0.05 else ("불안정" if cv > 0.15 else "보통")
            lines.append(
                f"    {mk:<26} {d:>+9.2f}% {cv*100:>8.2f}%  {stable}"
            )

    lines.append("")
    lines.append("=" * 100)
    lines.append(" 임계값 후보 — |Δ%| > 10% 이고 CV < 5% 인 지표 (판정 신호로 적합)")
    lines.append("=" * 100)
    for s in summaries:
        if s["label"] == baseline_label:
            continue
        candidates: List[tuple] = []
        for mk in METRIC_KEYS:
            if not baseline or not baseline["metrics"].get(mk):
                continue
            m = s["metrics"].get(mk)
            if m is None:
                continue
            base_mean = baseline["metrics"][mk]["mean"]
            d = _delta_pct(m["mean"], base_mean)
            cv = m.get("cv")
            if d is None or cv is None:
                continue
            if abs(d) > 10.0 and cv < 0.05:
                candidates.append((mk, d, cv, m["mean"], base_mean))
        if not candidates:
            lines.append(f"\n  ▸ {s['label']}: 적합한 지표 없음")
            continue
        lines.append(f"\n  ▸ {s['label']}")
        lines.append(
            f"    {'지표':<26} {'baseline':>12} {'관측':>12} {'Δ%':>10} {'CV':>10}"
        )
        candidates.sort(key=lambda r: abs(r[1]), reverse=True)
        for mk, d, cv, mean, base_mean in candidates:
            lines.append(
                f"    {mk:<26} {base_mean:>12.5f} {mean:>12.5f} "
                f"{d:>+9.2f}% {cv*100:>8.2f}%"
            )

    lines.append("")
    lines.append("해석 팁:")
    lines.append("  - Δ% 부호가 자세 방향을 알려줍니다 (예: cheek_distance +면 가까워짐)")
    lines.append("  - 같은 자세에서 CV < 5%인 지표는 임계값 설정에 안정적")
    lines.append("  - 'forward_head_only'와 'forward_head_full'을 구별하는 지표가")
    lines.append("    있는지 확인하면 노트북 거북목 판정 로직 설계 핵심")
    lines.append("  - yaw_turn에서 |Δ%| > 10%인 지표는 yaw 게이트로 가려야 함")
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
        "cheek_eye_ratio",
        "vh_ratio",
        "eye_line_tilt",
        "hand_face_score",
        "face_center_y",
    ]
    fig, axes = plt.subplots(2, 3, figsize=(16, 8))
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

    fig.suptitle("Posture vs metrics (mean ± std)", fontsize=12)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    logger.info(f"플롯 저장: {output_path}")


def print_posture_instructions(label: str) -> None:
    info = POSTURE_INSTRUCTIONS.get(label)
    if info is None:
        print(f"  ※ '{label}' 자세에 대한 안내가 없습니다. 같은 자세를 30초 유지하세요.")
        return
    title, steps = info
    print(f"  ▸ 자세 안내: {title}")
    for i, step in enumerate(steps, 1):
        print(f"    {i}. {step}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="자세별 자세 지표 변화 측정 (임계값 근거 산출용)"
    )
    parser.add_argument("--camera-id", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument(
        "--postures",
        type=str,
        nargs="+",
        default=DEFAULT_POSTURES,
        help=(
            "측정할 자세 목록. 첫 번째 자세가 baseline으로 사용됨. "
            f"기본: {' '.join(DEFAULT_POSTURES)}. "
            f"가능 자세: {', '.join(POSTURE_INSTRUCTIONS.keys())}"
        ),
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION_S,
        help="자세별 측정 시간(초)",
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=DEFAULT_SETTLE_S,
        help="자세 잡고 안정화 대기(초)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "debug_logs" / "posture_experiment"),
        help="결과 저장 디렉토리",
    )
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    parser.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="baseline으로 쓸 자세 라벨 (지정하지 않으면 첫 자세 또는 'neutral')",
    )
    parser.add_argument(
        "--screen-angle",
        type=str,
        default="0deg",
        help="화면 각도 태그 (예: minus10, 0deg, plus10). 출력 디렉토리 이름에 포함됨.",
    )
    args = parser.parse_args()

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    angle_tag = args.screen_angle.replace("+", "plus").replace("-", "minus").replace(" ", "")
    out_dir = Path(args.output_dir) / f"{run_ts}_{angle_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline_label = args.baseline or (
        "neutral" if "neutral" in args.postures else args.postures[0]
    )
    if baseline_label not in args.postures:
        print(f"  ! baseline '{baseline_label}'이 postures 목록에 없어 첫 자세로 대체")
        baseline_label = args.postures[0]

    banner(" 자세별 지표 변화 측정 실험")
    print(f"  실행 시각:       {datetime.now().isoformat(timespec='seconds')}")
    print(f"  저장 경로:       {out_dir}")
    print(f"  화면 각도 태그:  {args.screen_angle}")
    print(f"  측정 자세:       {args.postures}")
    print(f"  baseline 자세:   {baseline_label}")
    print(f"  자세별 측정시간: {args.duration:.0f}초 (+안정화 {args.settle:.0f}초)")
    print(f"  카메라:          id={args.camera_id}, {args.width}x{args.height}")
    print()
    print(f"  ※ 화면 각도를 [{args.screen_angle}]에 맞게 설정하세요.")
    print()
    print("  실험 절차:")
    print("    1) 안내된 자세를 잡습니다.")
    print("    2) 자세 잡혔으면 Enter, 안정화 3초 후 측정 시작.")
    print("    3) 측정 중 자세를 유지합니다 (작은 움직임은 괜찮습니다).")
    print("    4) 다음 자세 안내가 나오면 자세만 바꿉니다.")
    print()
    input("  준비되었으면 Enter를 누르세요... ")

    config = ConfigManager()
    extractor = create_landmark_extractor()
    indicator_calc = IndicatorCalculator(config=config)

    cap = open_camera(args.camera_id, args.width, args.height)
    try:
        meta = {
            "started_at": datetime.now().isoformat(),
            "screen_angle": args.screen_angle,
            "postures": args.postures,
            "baseline_label": baseline_label,
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
        for label in args.postures:
            banner(f" 자세: {label}")
            print_posture_instructions(label)
            print()
            print("  자세를 잡고 준비되었으면 Enter를 누르세요.")
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
                    "  ! 경고: 얼굴 검출률 낮음. 다음 자세 전에 카메라/조명을 확인하세요."
                )

        with open(out_dir / "summary.json", "w", encoding="utf-8") as fp:
            json.dump(summaries, fp, ensure_ascii=False, indent=2)
        report = build_report(summaries, baseline_label=baseline_label, screen_angle=args.screen_angle)
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
