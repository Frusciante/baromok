"""
V2 판정 엔진 디버그 모듈

╔════════════════════════════════════════════════════════════════════╗
║  ⚠ DEBUG ONLY — REMOVE BEFORE PRODUCTION RELEASE                  ║
║                                                                     ║
║  이 파일은 V2 자세 감지 로직 개발/검증용입니다.                       ║
║  운영 빌드 시 다음을 수행하면 안전하게 제거됩니다:                    ║
║    1. 이 파일(src/core/v2_debug.py) 삭제                              ║
║    2. scripts/v2_live_debug.py 삭제                                   ║
║    3. scripts/v2_replay_debug.py 삭제                                 ║
║    4. debug_logs/v2_runtime/ 폴더 삭제 (출력물)                       ║
║                                                                     ║
║  V2 core 모듈 (calibration_v2.py, judgment_engine_v2.py) 는          ║
║  이 파일을 import 하지 않으므로 삭제 후에도 그대로 동작합니다.        ║
║  외부에서 on_frame 콜백을 None 으로 두면 자동으로 비활성화됩니다.     ║
╚════════════════════════════════════════════════════════════════════╝

기능:
  - 매 프레임 indicators + judgment 결과를 CSV 로 저장
  - 캘리브레이션 baseline 스냅샷 저장
  - 실시간 콘솔 출력 (자세, confidence, Δ%, 후보들)
"""

import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

from src.core.indicator_calculator import PostureIndicators
from src.core.judgment_engine_v2 import JudgmentResultV2, PostureCandidate
from src.utils.logger import get_logger

logger = get_logger(__name__)


# 모든 디버그 출력 루트 — 운영 빌드 시 삭제할 폴더
DEFAULT_DEBUG_ROOT = Path("debug_logs/v2_runtime")


# CSV 필드 (frame_*.csv)
CSV_FIELDS = [
    # 식별
    "frame_idx", "elapsed_s", "timestamp_iso",
    # 판정 결과
    "detected_posture", "display_label", "frame_state",
    "confidence", "deviation_score", "duration_in_state_s",
    # 핵심 지표
    "cheek_distance", "eye_distance", "shoulder_width",
    "eye_line_tilt", "shoulder_tilt_deg",
    "eye_symmetry_ratio", "cheek_symmetry_ratio",
    "chin_alignment_offset", "hand_face_score", "chin_occlusion",
    # Δ% 계산
    "cheek_distance_pct", "eye_distance_pct",
    "eye_line_tilt_delta_deg", "shoulder_width_pct",
    # 후보 자세 (JSON 직렬화)
    "candidates_json",
]


class V2DebugRecorder:
    """V2 판정 결과 디버그 기록기.

    JudgmentEngineV2 의 on_frame 콜백으로 등록하면 매 프레임이 기록된다.

    ⚠ Thread-safety: 단일 쓰레드(=판정 엔진을 호출하는 쓰레드) 사용 가정.
       여러 쓰레드에서 동시에 on_frame 을 부르면 파일 핸들이 깨질 수 있음.

    Example:
        recorder = V2DebugRecorder()
        recorder.start_session(label="my_debug_run")
        recorder.record_calibration(cal_mgr.calibration)

        engine = JudgmentEngineV2(config, cal_mgr, on_frame=recorder.on_frame)
        # ... judge() 호출들 ...

        recorder.finish_session()
    """

    # 매 N 프레임마다 CSV flush (crash 시 데이터 보존)
    FLUSH_EVERY_N_FRAMES = 30

    def __init__(
        self,
        output_root: Optional[Path] = None,
        live_console: bool = True,
        console_every_n: int = 5,
    ):
        """
        Args:
            output_root: 결과 저장 폴더 (None = debug_logs/v2_runtime)
            live_console: True 면 실시간 콘솔 출력 활성화
            console_every_n: N 프레임마다 콘솔 출력 (1 = 매 프레임)
        """
        self.output_root = Path(output_root) if output_root else DEFAULT_DEBUG_ROOT
        self.live_console = live_console
        self.console_every_n = max(1, int(console_every_n))

        self._session_dir: Optional[Path] = None
        self._csv_file: Optional[TextIO] = None
        self._csv_writer: Optional[csv.DictWriter] = None
        self._frame_count: int = 0
        self._session_start_ts: Optional[float] = None
        self._session_label: str = ""

    # ─── 세션 관리 ─────────────────────────────────────────────────────

    def start_session(self, label: str = "") -> Path:
        """디버그 세션 시작. 세션별 폴더를 생성."""
        if self._csv_file is not None:
            self.finish_session()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label = "".join(c for c in label if c.isalnum() or c in "_-")
        dirname = f"{ts}_{safe_label}" if safe_label else ts
        self._session_dir = self.output_root / dirname
        self._session_dir.mkdir(parents=True, exist_ok=True)

        csv_path = self._session_dir / "frames.csv"
        self._csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        self._csv_writer = csv.DictWriter(self._csv_file, fieldnames=CSV_FIELDS)
        self._csv_writer.writeheader()
        self._frame_count = 0
        self._session_start_ts = None
        self._session_label = label

        if self.live_console:
            print(f"\n[V2 DEBUG] 세션 시작: {self._session_dir}", flush=True)
        return self._session_dir

    def finish_session(self) -> None:
        """세션 종료 — 파일 flush/close"""
        if self._csv_file is not None:
            self._csv_file.flush()
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None
        if self.live_console and self._session_dir:
            print(
                f"[V2 DEBUG] 세션 종료: {self._frame_count} 프레임 → {self._session_dir}",
                flush=True,
            )

    def record_calibration(self, calibration: Any) -> None:
        """캘리브레이션 baseline 스냅샷 저장. calibration=None 이면 무시."""
        if self._session_dir is None or calibration is None:
            return
        try:
            from src.core.calibration_v2 import CalibrationV2Manager
            payload = CalibrationV2Manager._serialize(calibration)
        except Exception:
            # CalibrationV2 객체 → dict 추출 (fallback)
            payload = {
                "version": getattr(calibration, "version", "?"),
                "frame_count": getattr(calibration, "frame_count", 0),
                "auto_thresholds": getattr(calibration, "auto_thresholds", {}),
            }
        out = self._session_dir / "baseline_snapshot.json"
        try:
            with open(out, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"baseline_snapshot 저장 실패 (무시): {e}")

    # ─── 프레임 콜백 ───────────────────────────────────────────────────

    def on_frame(self, indicators: PostureIndicators, result: JudgmentResultV2) -> None:
        """JudgmentEngineV2.judge() 가 호출하는 콜백"""
        if self._csv_writer is None:
            return

        if self._session_start_ts is None:
            self._session_start_ts = result.timestamp
        elapsed = result.timestamp - self._session_start_ts

        row: Dict[str, Any] = {
            "frame_idx": self._frame_count,
            "elapsed_s": round(elapsed, 3),
            "timestamp_iso": datetime.now().isoformat(),
            "detected_posture": result.detected_posture,
            "display_label": result.display_label,
            "frame_state": result.frame_state,
            "confidence": round(result.confidence, 4),
            "deviation_score": round(result.deviation_score, 4),
            "duration_in_state_s": round(result.duration_in_state_s, 3),
            "cheek_distance": indicators.cheek_distance,
            "eye_distance": indicators.eye_distance,
            "shoulder_width": indicators.shoulder_width,
            "eye_line_tilt": indicators.eye_line_tilt,
            "shoulder_tilt_deg": indicators.shoulder_tilt_deg,
            "eye_symmetry_ratio": indicators.eye_symmetry_ratio,
            "cheek_symmetry_ratio": indicators.cheek_symmetry_ratio,
            "chin_alignment_offset": indicators.chin_alignment_offset,
            "hand_face_score": indicators.hand_face_score,
            "chin_occlusion": indicators.chin_occlusion,
            "cheek_distance_pct": result.deltas.get("cheek_distance_pct"),
            "eye_distance_pct": result.deltas.get("eye_distance_pct"),
            "eye_line_tilt_delta_deg": result.deltas.get("eye_line_tilt_delta_deg"),
            "shoulder_width_pct": result.deltas.get("shoulder_width_pct"),
            "candidates_json": json.dumps(
                [
                    {
                        "p": c.posture,
                        "dev": round(c.deviation_score, 3),
                        "ratio": round(c.threshold_ratio, 3),
                    }
                    for c in result.candidates
                ],
                ensure_ascii=False,
            ),
        }
        self._csv_writer.writerow(row)
        self._frame_count += 1

        # 주기적 flush — crash 시에도 데이터 보존
        if self._csv_file is not None and self._frame_count % self.FLUSH_EVERY_N_FRAMES == 0:
            try:
                self._csv_file.flush()
            except Exception:
                pass

        if self.live_console and self._frame_count % self.console_every_n == 0:
            self._print_frame(indicators, result, elapsed)

    # ─── 콘솔 출력 ─────────────────────────────────────────────────────

    @staticmethod
    def _print_frame(
        indicators: PostureIndicators, result: JudgmentResultV2, elapsed_s: float
    ) -> None:
        """현재 프레임 상태 콘솔에 한 줄 출력"""
        state_color = {
            "NORMAL": "",
            "WARNING": "!",
            "BAD_POSTURE": "!!",
        }.get(result.frame_state, "")

        cands = " | ".join(
            f"{c.posture}={c.deviation_score:.1f}" for c in result.candidates
        ) or "-"

        deltas = result.deltas
        cd_pct = deltas.get("cheek_distance_pct", 0)
        sw_pct = deltas.get("shoulder_width_pct")
        eye_tilt = deltas.get("eye_line_tilt_delta_deg", 0)

        sw_str = f"sw={sw_pct:+.1f}%" if sw_pct is not None else "sw=N/A"

        line = (
            f"[{elapsed_s:6.1f}s] {state_color:<2} "
            f"{result.display_label:<14} conf={result.confidence:.2f} "
            f"cd={cd_pct:+.1f}% {sw_str} et={eye_tilt:+.1f}° "
            f"hand={indicators.hand_face_score:.2f} | cands: {cands}"
        )
        print(line, flush=True)

    # ─── 컨텍스트 매니저 지원 ─────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.finish_session()
