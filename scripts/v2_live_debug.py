#!/usr/bin/env python3
"""
V2 자세 감지 실시간 디버그 스크립트

╔════════════════════════════════════════════════════════════════════╗
║  ⚠ DEBUG ONLY — REMOVE BEFORE PRODUCTION RELEASE                  ║
║  운영 빌드 시 이 파일 삭제. V2 core 모듈은 영향받지 않음.            ║
╚════════════════════════════════════════════════════════════════════╝

사용법:
  py -3 scripts/v2_live_debug.py                        # 캘리브 → 라이브 판정
  py -3 scripts/v2_live_debug.py --skip-calibration     # 저장된 baseline_v2.json 사용
  py -3 scripts/v2_live_debug.py --sensitivity high     # 민감도 변경
  py -3 scripts/v2_live_debug.py --print-every 1        # 매 프레임 콘솔 출력
  py -3 scripts/v2_live_debug.py --duration 30          # 30초만 라이브 판정

출력:
  debug_logs/v2_runtime/<timestamp>_<label>/
    ├── frames.csv             # 매 프레임 indicators + 판정
    └── baseline_snapshot.json # 사용된 캘리브레이션 스냅샷
"""

import argparse
import sys
import time
from pathlib import Path

import cv2

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
from src.core.indicator_calculator import IndicatorCalculator
from src.core.judgment_engine_v2 import JudgmentEngineV2
from src.core.landmark_extractor import create_landmark_extractor
from src.core.v2_debug import V2DebugRecorder
from src.utils.logger import get_logger

logger = get_logger(__name__, "INFO")


def _capture_indicators(cap, extractor, calculator: IndicatorCalculator):
    """카메라 한 프레임 → PostureIndicators (실패 시 None).

    V1 시스템과 동일한 LandmarkExtractor / IndicatorCalculator 사용 패턴.
    """
    ok, frame = cap.read()
    if not ok or frame is None:
        return None
    h, w = frame.shape[:2]
    extracted = extractor.extract_landmarks(frame)
    lm = extractor.get_relevant_landmarks(extracted, w, h)
    lm_norm = extractor.normalize_landmarks(
        lm, w, h, timestamp_ms=int(time.time() * 1000)
    )
    indicators = calculator.calculate_all_indicators(lm_norm, timestamp=time.time())
    return frame, indicators


def run_calibration(
    cap: cv2.VideoCapture,
    extractor,
    calculator: IndicatorCalculator,
    cal_mgr: CalibrationV2Manager,
) -> bool:
    """neutral 자세 캘리브레이션 (V2)"""
    print("\n" + "=" * 60)
    print("  [V2 캘리브레이션]  바른 자세로 앉아 대기하세요")
    print("=" * 60)

    # 카운트다운
    for s in range(int(cal_mgr.wait_seconds), 0, -1):
        print(f"  {s}초 후 측정 시작...", end="\r", flush=True)
        time.sleep(1)
    print("  측정 중...                  ")

    cal_mgr.start_collection()
    t_start = time.time()
    while time.time() - t_start < cal_mgr.collect_seconds:
        captured = _capture_indicators(cap, extractor, calculator)
        if captured is None:
            continue
        _, ind = captured
        if ind is not None:
            cal_mgr.add_frame(ind)

        elapsed = time.time() - t_start
        # 진행 표시 — private 멤버 접근 대신 public property 사용
        print(
            f"  진행 {elapsed:.1f}/{cal_mgr.collect_seconds:.1f}s "
            f"(프레임 {cal_mgr.collected_frame_count})",
            end="\r",
            flush=True,
        )

    success = cal_mgr.finish_collection()
    print()
    if success:
        cal = cal_mgr.calibration
        print(f"  ✓ 캘리브레이션 완료 — 품질: {cal.calibration_quality}")
        print(f"    어깨 검출률: {cal.shoulder_detection_rate*100:.1f}%")
        print(f"    자동 임계값:")
        for k, v in cal.auto_thresholds.items():
            print(f"      {k}: {v}")
        for msg in cal.quality_messages:
            print(f"    ⚠ {msg}")
        cal_mgr.save()
    else:
        print("  ✗ 캘리브레이션 실패")
    return success


def run_live(
    cap: cv2.VideoCapture,
    extractor,
    calculator: IndicatorCalculator,
    engine: JudgmentEngineV2,
    duration_s: float,
) -> None:
    """라이브 판정 — 매 프레임 V2 판정 + 디버그 출력"""
    print("\n" + "=" * 60)
    print(f"  [V2 라이브 판정]  {duration_s:.0f}초 동안 측정")
    print(f"  ESC 또는 q 키로 조기 종료 가능 (cv2 창 포커스 필요)")
    print("=" * 60)

    t_start = time.time()
    window_name = "V2 Debug (q to quit)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 640, 480)

    confirmed_label = ""  # update_sustain 이 확정한 자세 (있을 때만 표시)
    while time.time() - t_start < duration_s:
        captured = _capture_indicators(cap, extractor, calculator)
        if captured is None:
            continue
        frame, ind = captured
        if ind is None:
            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break
            continue

        # 판정 — on_frame 콜백이 디버그 기록기로 연결돼 있음
        judgment = engine.judge(ind)

        # 자세 확정 검사 (sustain_seconds 동안 유지된 자세)
        confirmed = engine.update_sustain(judgment)
        if confirmed:
            confirmed_label = f"CONFIRMED: {confirmed}"

        # 화면에 라벨 오버레이 — cv2.putText 는 한국어 미지원이므로 ASCII 만 사용
        text = (
            f"{judgment.detected_posture} "
            f"({judgment.frame_state}, conf={judgment.confidence:.2f})"
        )
        color = {
            "NORMAL": (80, 220, 80),
            "WARNING": (50, 200, 230),
            "BAD_POSTURE": (60, 80, 230),
        }.get(judgment.frame_state, (200, 200, 200))
        cv2.putText(frame, text, (16, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        if confirmed_label:
            cv2.putText(frame, confirmed_label, (16, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow(window_name, frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord("q")):
            break

    cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="V2 자세 감지 라이브 디버그")
    parser.add_argument("--skip-calibration", action="store_true",
                        help="저장된 baseline_v2.json 사용 (재캘리 안 함)")
    parser.add_argument("--sensitivity", choices=["high", "medium", "low"],
                        default="medium", help="판정 민감도")
    parser.add_argument("--duration", type=float, default=60.0,
                        help="라이브 판정 지속 시간(초)")
    parser.add_argument("--print-every", type=int, default=5,
                        help="N 프레임마다 콘솔 출력 (1=매 프레임)")
    parser.add_argument("--label", default="live", help="세션 라벨 (폴더명에 포함)")
    parser.add_argument("--camera-index", type=int, default=0)
    args = parser.parse_args()

    print(f"※ 화면 각도는 평소 자세에 맞게 고정해주세요. (예: 105~110도)")
    print()

    # 초기화
    config = ConfigManager()
    cal_mgr = CalibrationV2Manager(config)
    extractor = create_landmark_extractor(config)
    calculator = IndicatorCalculator(config)

    # 카메라 열기
    cap = cv2.VideoCapture(args.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[오류] 카메라({args.camera_index}) 열 수 없음")
        return 1

    try:
        # 1. 캘리브레이션
        if args.skip_calibration:
            if not cal_mgr.load():
                print("[오류] baseline_v2.json 없음 — --skip-calibration 사용 불가")
                return 1
            print(f"※ 저장된 V2 baseline 사용 (품질: {cal_mgr.calibration.calibration_quality})")
        else:
            if not run_calibration(cap, extractor, calculator, cal_mgr):
                return 1

        # 2. 라이브 판정 (디버그 기록 활성화)
        with V2DebugRecorder(live_console=True, console_every_n=args.print_every) as rec:
            session_dir = rec.start_session(label=args.label)
            rec.record_calibration(cal_mgr.calibration)

            engine = JudgmentEngineV2(
                config, cal_mgr,
                sensitivity=args.sensitivity,
                on_frame=rec.on_frame,
            )
            # 캘리브에서 수집한 프레임으로 어깨 검출 이력 사전 채움
            # (없으면 첫 5초간 어깨 보조 지표 비활성화)
            engine.preload_shoulder_history(cal_mgr.get_collected_frames())

            run_live(cap, extractor, calculator, engine, args.duration)

            print(f"\n[완료] 결과 파일:")
            print(f"  {session_dir / 'frames.csv'}")
            print(f"  {session_dir / 'baseline_snapshot.json'}")

    finally:
        cap.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
