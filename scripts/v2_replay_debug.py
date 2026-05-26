#!/usr/bin/env python3
"""
V2 자세 감지 리플레이 디버그 스크립트

╔════════════════════════════════════════════════════════════════════╗
║  ⚠ DEBUG ONLY — REMOVE BEFORE PRODUCTION RELEASE                  ║
╚════════════════════════════════════════════════════════════════════╝

저장된 실험 데이터(frames_*.csv)를 가지고 V2 로직을 다시 돌려서
판정 결과를 확인. 라이브 카메라 없이도 V2 튜닝 가능.

사용법:
  py -3 scripts/v2_replay_debug.py debug_logs/posture_experiment/20260521_173837_107deg
  py -3 scripts/v2_replay_debug.py <dir> --sensitivity high
  py -3 scripts/v2_replay_debug.py <dir> --print-every 1   # 매 프레임 출력
"""

import argparse
import csv
import sys
from pathlib import Path

# Windows 콘솔(cp949)에서 한국어 라벨 출력 시 UnicodeEncodeError 방지
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ConfigManager
from src.core.calibration_v2 import CalibrationV2Manager
from src.core.indicator_calculator import PostureIndicators
from src.core.judgment_engine_v2 import JudgmentEngineV2
from src.core.v2_debug import V2DebugRecorder


def load_csv_frames(path: Path):
    """CSV → PostureIndicators 리스트 (검출 실패 프레임 제외)"""
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                cd = float(row.get("cheek_distance") or 0)
                if cd <= 0:
                    continue
                ind = PostureIndicators(
                    cheek_distance=cd,
                    eye_distance=float(row.get("eye_distance") or 0),
                    face_vertical_length=float(row.get("face_vertical_length") or 0),
                    shoulder_width=float(row.get("shoulder_width") or 0),
                    shoulder_tilt_deg=float(row.get("shoulder_tilt_deg") or 0),
                    neck_offset=0.0,
                    eye_line_tilt=float(row.get("eye_line_tilt") or 0),
                    chin_occlusion=float(row.get("chin_occlusion") or 0),
                    hand_near_face=False,
                    hand_face_score=float(row.get("hand_face_score") or 0),
                    eye_symmetry_ratio=float(row.get("eye_symmetry_ratio") or 0),
                    cheek_symmetry_ratio=float(row.get("cheek_symmetry_ratio") or 0),
                    chin_alignment_offset=float(row.get("chin_alignment_offset") or 0),
                    timestamp=float(row.get("elapsed_s") or 0),
                )
                out.append(ind)
            except (ValueError, TypeError):
                continue
    return out


def main():
    parser = argparse.ArgumentParser(description="V2 리플레이 디버그")
    parser.add_argument("data_dir", help="실험 데이터 폴더 (frames_*.csv 포함)")
    parser.add_argument("--sensitivity", choices=["high", "medium", "low"], default="medium")
    parser.add_argument("--print-every", type=int, default=5)
    parser.add_argument("--postures", nargs="*",
                        default=["forward_head_only", "recline"],
                        help="평가할 자세 CSV (기본: forward_head_only, recline)")
    parser.add_argument("--min-frames", type=int, default=20,
                        help="캘리브 최소 프레임 (테스트용 완화값. 운영 기본값은 100)")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"[오류] 폴더 없음: {data_dir}")
        return 1

    # 1. neutral 프레임으로 캘리브레이션
    neutral_frames = load_csv_frames(data_dir / "frames_neutral.csv")
    if not neutral_frames:
        print(f"[오류] frames_neutral.csv 없음/유효 데이터 없음")
        return 1

    config = ConfigManager()
    cal_mgr = CalibrationV2Manager(config)
    cal_mgr.minimum_valid_frames = args.min_frames

    cal_mgr.start_collection()
    for f in neutral_frames:
        cal_mgr.add_frame(f)
    if not cal_mgr.finish_collection():
        print("[오류] 캘리브레이션 실패")
        return 1

    cal = cal_mgr.calibration
    print(f"\n[캘리브레이션 결과]")
    print(f"  프레임 수: {cal.frame_count}")
    print(f"  품질: {cal.calibration_quality}")
    print(f"  어깨 검출률: {cal.shoulder_detection_rate*100:.1f}%")
    print(f"  자동 임계값:")
    for k, v in cal.auto_thresholds.items():
        print(f"    {k}: {v}")

    # 2. 디버그 기록기 + V2 엔진 연결
    with V2DebugRecorder(live_console=True, console_every_n=args.print_every) as rec:
        label = f"replay_{data_dir.name}"
        session_dir = rec.start_session(label=label)
        rec.record_calibration(cal)

        engine = JudgmentEngineV2(
            config, cal_mgr,
            sensitivity=args.sensitivity,
            on_frame=rec.on_frame,
        )

        # 어깨 검출 이력 사전 채움 (neutral 마지막 30 프레임)
        # — public API 사용 (private _update_shoulder_history 직접 호출 금지)
        engine.preload_shoulder_history(neutral_frames[-30:])

        # 3. 자세별 리플레이
        for posture in args.postures:
            csv_path = data_dir / f"frames_{posture}.csv"
            frames = load_csv_frames(csv_path)
            if not frames:
                print(f"\n[건너뜀] {csv_path.name} 없음/유효 데이터 없음")
                continue

            print(f"\n[리플레이] {posture} ({len(frames)} 프레임)")
            print("-" * 60)
            counts = {}
            for f in frames:
                result = engine.judge(f)
                counts[result.detected_posture] = counts.get(result.detected_posture, 0) + 1

            print(f"\n  → 판정 분포 (기대 자세: {posture}):")
            total = sum(counts.values())
            for k, v in sorted(counts.items(), key=lambda x: -x[1]):
                marker = "*" if k == posture else " "
                print(f"    {marker} {k:<22} {v:>4} ({v/total*100:5.1f}%)")

        print(f"\n[완료] 디버그 결과: {session_dir / 'frames.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
