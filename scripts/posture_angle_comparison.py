#!/usr/bin/env python3
"""
자세 × 화면각도 교차 비교 스크립트

posture_variance_experiment.py 를 여러 화면 각도에서 돌린 결과 디렉토리들을
읽어서, 같은 자세일 때 각도가 달라지면 지표가 얼마나 바뀌는지 비교한다.

핵심 질문:
  1. neutral 자세에서 각도가 바뀌면 지표 절대값이 얼마나 달라지는가?
     → 달라진다면, 각도에 따라 threshold를 다르게 잡아야 한다.
  2. forward_head_only / recline 등의 자세를 각도별로 구분 가능한가?
     → 구분 가능하면 해당 지표를 threshold 후보로 확정.

사용법:
  py -3 scripts/posture_angle_comparison.py
  py -3 scripts/posture_angle_comparison.py --exp-dir debug_logs/posture_experiment
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

METRICS = [
    "cheek_distance",
    "eye_distance",
    "cheek_eye_ratio",
    "vh_ratio",
    "face_center_y",
    "face_center_x",
    "shoulder_width",
    "eye_line_tilt",
]


def load_run(run_dir: Path) -> dict:
    meta_path = run_dir / "metadata.json"
    summary_path = run_dir / "summary.json"
    if not meta_path.exists() or not summary_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return {"meta": meta, "summary": summary, "dir": str(run_dir)}


def pct_change(val, base):
    if base is None or base == 0 or val is None:
        return None
    return (val - base) / abs(base) * 100


def sep(char="=", width=110):
    print(char * width)


def main():
    parser = argparse.ArgumentParser(description="자세 × 화면각도 교차 비교")
    parser.add_argument(
        "--exp-dir",
        type=str,
        default=str(PROJECT_ROOT / "debug_logs" / "posture_experiment"),
        help="posture_variance_experiment 결과들이 있는 상위 디렉토리",
    )
    parser.add_argument(
        "--postures",
        nargs="+",
        default=["neutral", "forward_head_only", "recline"],
        help="비교할 자세 목록",
    )
    args = parser.parse_args()

    exp_dir = Path(args.exp_dir)
    if not exp_dir.exists():
        print(f"디렉토리 없음: {exp_dir}")
        return 1

    # 실험 결과 디렉토리 목록 수집
    runs = []
    for d in sorted(exp_dir.iterdir()):
        if not d.is_dir():
            continue
        r = load_run(d)
        if r is None:
            continue
        runs.append(r)

    if not runs:
        print(f"결과 없음: {exp_dir}")
        print("posture_variance_experiment.py 를 먼저 여러 각도에서 실행하세요.")
        return 1

    # 각도 태그별로 그룹핑
    by_angle = {}
    for r in runs:
        angle = r["meta"].get("screen_angle", "unknown")
        by_angle.setdefault(angle, []).append(r)

    # 각 angle 에서 가장 최신 run 만 사용
    latest = {}
    for angle, rlist in by_angle.items():
        latest[angle] = sorted(rlist, key=lambda x: x["dir"])[-1]

    angle_tags = sorted(latest.keys())

    sep()
    print(" 자세 × 화면각도 교차 비교")
    print(f" 실험 디렉토리: {exp_dir}")
    print(f" 발견된 각도 태그: {angle_tags}")
    print(f" 비교 자세: {args.postures}")
    sep()

    if len(angle_tags) < 2:
        print("\n 각도 태그가 1개뿐입니다. 최소 2개 이상의 각도에서 실험을 돌려야 비교가 가능합니다.")
        print("\n 예시:")
        print("   py -3 scripts/posture_variance_experiment.py --postures neutral forward_head_only recline --duration 15 --screen-angle minus10")
        print("   py -3 scripts/posture_variance_experiment.py --postures neutral forward_head_only recline --duration 15 --screen-angle 0deg")
        print("   py -3 scripts/posture_variance_experiment.py --postures neutral forward_head_only recline --duration 15 --screen-angle plus10")
        return 0

    # ── Section 1: 각도별 neutral 지표 절대값 비교 ──────────────────────────────
    print("\n[1] 각도별 neutral 지표 절대값 (각도 변화가 baseline 자체를 얼마나 바꾸는가)")
    print(f"\n  {'지표':<22}", end="")
    for tag in angle_tags:
        print(f"  {tag:>14}", end="")
    print(f"  {'최대 Δ%':>10}  해석")
    print("  " + "-" * (22 + 16 * len(angle_tags) + 22))

    for metric in METRICS:
        vals = {}
        for tag in angle_tags:
            run = latest[tag]
            for cond in run["summary"]:
                if cond["label"] == "neutral":
                    m = (cond.get("metrics") or {}).get(metric)
                    vals[tag] = m["mean"] if m else None
                    break

        valid_vals = [v for v in vals.values() if v is not None]
        if not valid_vals:
            continue

        ref = valid_vals[0]
        max_dpct = max((abs(pct_change(v, ref) or 0) for v in valid_vals), default=0)
        flag = "★ 각도 영향 큼" if max_dpct > 10 else ("주의" if max_dpct > 5 else "안정")

        print(f"  {metric:<22}", end="")
        for tag in angle_tags:
            v = vals.get(tag)
            print(f"  {v:>14.5f}" if v is not None else f"  {'N/A':>14}", end="")
        print(f"  {max_dpct:>9.1f}%  {flag}")

    # ── Section 2: 자세별, 각도별 Δ% (neutral 대비) ────────────────────────────
    print("\n")
    sep("-")
    print("[2] 자세별 Δ% — 각도가 달라져도 방향/크기가 일관하는가")
    sep("-")

    for posture in args.postures:
        if posture == "neutral":
            continue

        print(f"\n  ▸ {posture} (vs neutral, 각 각도의 baseline 기준)")
        print(f"    {'지표':<22}", end="")
        for tag in angle_tags:
            print(f"  {tag:>14}", end="")
        print(f"  {'방향 일치':>10}")
        print("    " + "-" * (22 + 16 * len(angle_tags) + 12))

        for metric in METRICS:
            dpcts = {}
            for tag in angle_tags:
                run = latest[tag]
                neutral_mean = None
                posture_mean = None
                for cond in run["summary"]:
                    m = (cond.get("metrics") or {}).get(metric)
                    if m is None:
                        continue
                    if cond["label"] == "neutral":
                        neutral_mean = m["mean"]
                    elif cond["label"] == posture:
                        posture_mean = m["mean"]
                dpcts[tag] = pct_change(posture_mean, neutral_mean)

            valid = [v for v in dpcts.values() if v is not None]
            if not valid:
                continue

            # 방향 일치: 모두 양수 또는 모두 음수인지
            all_pos = all(v > 2 for v in valid)
            all_neg = all(v < -2 for v in valid)
            consistent = "✓ 일치" if (all_pos or all_neg) else ("△ 혼재" if len(valid) > 1 else "—")

            print(f"    {metric:<22}", end="")
            for tag in angle_tags:
                v = dpcts.get(tag)
                print(f"  {v:>+13.1f}%" if v is not None else f"  {'N/A':>14}", end="")
            print(f"  {consistent:>10}")

    # ── Section 3: 결론 ────────────────────────────────────────────────────────
    print("\n")
    sep()
    print("[3] 판정 가이드")
    sep()
    print("""
  [1] 결과 해석:
    - neutral에서 각도별 Δ% > 10% 인 지표 → 각도가 바뀌면 baseline 자체가 달라짐
      → 해당 지표로 자세 판정 시 각도별로 threshold 별도 설정 or 비율 지표로 대체 필요
    - Δ% < 5% 인 지표 → 각도에 강건 → 단일 threshold 사용 가능

  [2] 결과 해석:
    - 방향 일치(✓): 화면 각도가 달라도 자세 변화 시 지표가 같은 방향으로 움직임
      → 각도 무관하게 해당 지표로 자세 판정 가능 (threshold 값은 달라질 수 있음)
    - 방향 혼재(△): 각도에 따라 자세의 영향이 반전됨 → 해당 지표 단독 사용 위험

  권장 지표 선별:
    neutral Δ% < 5% (각도 강건) + 자세 방향 일치(✓) → 최우선 threshold 후보
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
