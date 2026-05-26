"""
V2 모듈 통합 테스트 - 실제 실험 데이터로 검증.

각 사용자 × 각도 데이터로:
  1. neutral 프레임 → CalibrationV2 수집/임계값 도출
  2. forward_head_only / recline 프레임 → JudgmentEngineV2 판정
  3. 정확도 측정
"""

import csv
import sys
from pathlib import Path
from types import SimpleNamespace

import zipfile
import io

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ConfigManager
from src.core.calibration_v2 import CalibrationV2Manager
from src.core.judgment_engine_v2 import JudgmentEngineV2
from src.core.indicator_calculator import PostureIndicators


# ─── 데이터 위치 ────────────────────────────────────────────────────────

U1_DIRS = {
    "103deg": PROJECT_ROOT / "debug_logs/posture_experiment/20260521_173723_103deg",
    "107deg": PROJECT_ROOT / "debug_logs/posture_experiment/20260521_173837_107deg",
    "112deg": PROJECT_ROOT / "debug_logs/posture_experiment/20260521_174034_112deg",
}
U2_ZIPS = {
    "103deg": Path(r"C:\Users\JunHa\Downloads\20260524_232119_103deg.zip"),
    "107deg": Path(r"C:\Users\JunHa\Downloads\20260524_232256_107deg.zip"),
    "112deg": Path(r"C:\Users\JunHa\Downloads\20260524_232422_112deg.zip"),
}
U3_ZIPS = {
    "103deg": Path(r"C:\Users\JunHa\Downloads\20260525_201906_103deg.zip"),
    "107deg": Path(r"C:\Users\JunHa\Downloads\20260525_202229_107deg.zip"),
    "112deg": Path(r"C:\Users\JunHa\Downloads\20260525_202536_112deg.zip"),
}


def load_csv_frames(reader) -> list:
    """CSV reader → PostureIndicators list"""
    frames = []
    for row in reader:
        try:
            ind = PostureIndicators(
                cheek_distance=float(row.get("cheek_distance") or 0),
                eye_distance=float(row.get("eye_distance") or 0),
                face_vertical_length=float(row.get("face_vertical_length") or 0),
                shoulder_width=float(row.get("shoulder_width") or 0),
                shoulder_tilt_deg=float(row.get("shoulder_tilt_deg") or 0),
                neck_offset=0.0,  # CSV에 없으면 0
                eye_line_tilt=float(row.get("eye_line_tilt") or 0),
                chin_occlusion=float(row.get("chin_occlusion") or 0),
                hand_near_face=False,
                hand_face_score=float(row.get("hand_face_score") or 0),
                eye_symmetry_ratio=float(row.get("eye_symmetry_ratio") or 0),
                cheek_symmetry_ratio=float(row.get("cheek_symmetry_ratio") or 0),
                chin_alignment_offset=float(row.get("chin_alignment_offset") or 0),
                timestamp=float(row.get("elapsed_s") or 0),
            )
            # face_center_y 추가 속성으로 설정 (PostureIndicators 에 없는 경우)
            fcy = row.get("face_center_y")
            if fcy is not None:
                setattr(ind, "face_center_y", float(fcy))
            frames.append(ind)
        except (ValueError, TypeError):
            continue
    return frames


def load_frames_from_dir(d: Path, posture: str) -> list:
    p = d / f"frames_{posture}.csv"
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return load_csv_frames(csv.DictReader(f))


def load_frames_from_zip(z_path: Path, posture: str) -> list:
    if not z_path.exists():
        return []
    with zipfile.ZipFile(z_path) as zf:
        try:
            with zf.open(f"frames_{posture}.csv") as f:
                text = io.TextIOWrapper(f, encoding="utf-8")
                return load_csv_frames(csv.DictReader(text))
        except KeyError:
            return []


# ─── 테스트 실행 ────────────────────────────────────────────────────────

def run_test_for_user_angle(user_label: str, source, angle: str) -> dict:
    """단일 사용자/각도에 대해 V2 캘리브 + 판정 정확도 측정"""
    if user_label == "U1":
        d = source[angle]
        neutral_frames = load_frames_from_dir(d, "neutral")
        forward_frames = load_frames_from_dir(d, "forward_head_only")
        recline_frames = load_frames_from_dir(d, "recline")
    else:
        z = source[angle]
        neutral_frames = load_frames_from_zip(z, "neutral")
        forward_frames = load_frames_from_zip(z, "forward_head_only")
        recline_frames = load_frames_from_zip(z, "recline")

    if not neutral_frames:
        return {"error": "no_neutral"}

    # 1. 캘리브레이션 수집
    config = ConfigManager()
    cal_mgr = CalibrationV2Manager(config)
    cal_mgr.minimum_valid_frames = max(10, len(neutral_frames) // 2)  # 테스트용 완화
    cal_mgr.start_collection()
    for f in neutral_frames:
        cal_mgr.add_frame(f)
    success = cal_mgr.finish_collection()
    if not success:
        return {"error": "calibration_failed"}

    cal = cal_mgr.calibration
    thresholds = cal.auto_thresholds

    # 2. 판정 엔진 생성
    engine = JudgmentEngineV2(config, cal_mgr, sensitivity="medium")

    # 어깨 검출률 슬라이딩 윈도우 사전 채우기 (public API)
    engine.preload_shoulder_history(neutral_frames[-20:])

    # 3. 자세별 판정 (검출 실패 프레임은 건너뜀)
    def classify_majority(frames, expected_posture):
        if not frames:
            return None, 0
        counts = {}
        for f in frames:
            # 핵심 지표가 검출 실패면 스킵
            if f.cheek_distance <= 0 or f.eye_distance <= 0:
                continue
            r = engine.judge(f)
            counts[r.detected_posture] = counts.get(r.detected_posture, 0) + 1
        if not counts:
            return None, {}
        top = max(counts.items(), key=lambda x: x[1])
        return top[0], counts

    fwd_pred, fwd_counts = classify_majority(forward_frames, "forward_head_only")
    rec_pred, rec_counts = classify_majority(recline_frames, "recline")

    return {
        "shoulder_rate": cal.shoulder_detection_rate,
        "quality": cal.calibration_quality,
        "thresholds": thresholds,
        "forward_pred": fwd_pred,
        "forward_counts": fwd_counts,
        "recline_pred": rec_pred,
        "recline_counts": rec_counts,
    }


def main():
    sources = {
        "U1": U1_DIRS,
        "U2": U2_ZIPS,
        "U3": U3_ZIPS,
    }
    ANGLES = ["103deg", "107deg", "112deg"]

    print("=" * 95)
    print(" V2 모듈 통합 테스트 — 실제 3 사용자 × 3 각도 데이터")
    print("=" * 95)

    total_cases = 0
    correct = 0
    rows = []

    for user, src in sources.items():
        for angle in ANGLES:
            r = run_test_for_user_angle(user, src, angle)
            if "error" in r:
                rows.append((user, angle, "ERROR", r["error"], "", ""))
                continue

            fwd_ok = r["forward_pred"] == "forward_head_only"
            rec_ok = r["recline_pred"] == "recline"
            total_cases += 2
            correct += int(fwd_ok) + int(rec_ok)

            rows.append((
                user, angle,
                f"shoulder={r['shoulder_rate']:.2f}",
                f"fwd_th={r['thresholds'].get('forward_cheek_delta_pct'):.1f}% "
                f"rec_th={r['thresholds'].get('recline_cheek_delta_pct'):.1f}%",
                f"FWD: {r['forward_pred']} {'O' if fwd_ok else 'X'}",
                f"REC: {r['recline_pred']} {'O' if rec_ok else 'X'}",
            ))

    print(f"\n  {'사용자':<6} {'각도':<8} {'어깨':<14} {'임계값':<32} {'forward 판정':<32} {'recline 판정':<28}")
    print("  " + "-" * 117)
    for r in rows:
        print(f"  {r[0]:<6} {r[1]:<8} {r[2]:<14} {r[3]:<32} {r[4]:<32} {r[5]:<28}")

    print(f"\n  ✦ V2 정확도: {correct}/{total_cases} = {correct/total_cases*100:.1f}% (V1 기존 룰: 8/18=44.4%)")


if __name__ == "__main__":
    main()
