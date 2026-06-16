"""
세션 관리자 (SQLite 기반)
"""

import json
import uuid
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict, field, fields
from typing import List, Optional, Dict, Any
import logging

from src.config import ConfigManager
from src.utils.paths import DATA_DIR

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id       TEXT PRIMARY KEY,
    start_time       TEXT NOT NULL,
    end_time         TEXT,
    duration_seconds INTEGER DEFAULT 0,
    total_frames     INTEGER DEFAULT 0,
    statistics       TEXT DEFAULT '{}',
    notes            TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS frame_records (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    timestamp         TEXT NOT NULL,
    posture_type      TEXT NOT NULL DEFAULT 'normal',
    probability       REAL DEFAULT 0.0,
    state             TEXT NOT NULL DEFAULT 'NORMAL',
    cheek_distance    REAL DEFAULT 0.0,
    eye_distance      REAL DEFAULT 0.0,
    shoulder_width    REAL DEFAULT 0.0,
    shoulder_tilt_deg REAL DEFAULT 0.0,
    neck_offset       REAL DEFAULT 0.0,
    eye_line_tilt     REAL DEFAULT 0.0,
    chin_occlusion    REAL DEFAULT 0.0,
    hand_near_face    REAL DEFAULT 0.0,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fr_session ON frame_records(session_id);
CREATE INDEX IF NOT EXISTS idx_sess_start ON sessions(start_time DESC);
"""


@dataclass
class FrameRecord:
    timestamp: str
    posture_type: str
    probability: float
    state: str
    cheek_distance: float
    eye_distance: float
    shoulder_width: float
    shoulder_tilt_deg: float
    neck_offset: float
    eye_line_tilt: float
    chin_occlusion: float
    hand_near_face: float
    face_shoulder_ratio: float


@dataclass
class SessionData:
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: int = 0
    total_frames: int = 0
    frame_records: List[FrameRecord] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "total_frames": self.total_frames,
            "frame_records": [asdict(r) for r in self.frame_records],
            "statistics": self.statistics,
            "notes": self.notes,
        }

    @staticmethod
    def from_dict(data: dict) -> "SessionData":
        fr_fields = {f.name for f in fields(FrameRecord)}
        frame_records = []
        for r in data.get("frame_records", []):
            if isinstance(r, dict):
                filtered = {k: v for k, v in r.items() if k in fr_fields}
                frame_records.append(FrameRecord(**filtered))
        return SessionData(
            session_id=data["session_id"],
            start_time=data["start_time"],
            end_time=data.get("end_time"),
            duration_seconds=data.get("duration_seconds", 0),
            total_frames=data.get("total_frames", 0),
            frame_records=frame_records,
            statistics=data.get("statistics", {}),
            notes=data.get("notes", ""),
        )


class SessionManager:
    """세션 데이터 관리자 (SQLite 기반)"""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.current_session: Optional[SessionData] = None
        self.sessions_history: List[SessionData] = []
        self._lock = threading.Lock()

        data_dir = DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(data_dir / "sessions.db")
        self.sessions_dir = data_dir / "sessions"  # 레거시 JSON 경로

        # 영구 연결 (매 프레임마다 연결 생성 비용 제거)
        self._conn: Optional[sqlite3.Connection] = None

        self._init_db()
        self._migrate_json_sessions()
        logger.info(f"SessionManager 초기화 완료 (DB: {self.db_path})")

    # ------------------------------------------------------------------
    # DB 연결
    # ------------------------------------------------------------------
    def _get_conn(self) -> sqlite3.Connection:
        """영구 연결 반환 (없으면 생성). 스레드 안전은 _lock으로 보장."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        """DB 연결 명시적 종료 (앱 종료 시 호출)"""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(_SCHEMA_SQL)
        logger.info("SQLite DB 스키마 초기화 완료")

    # ------------------------------------------------------------------
    # JSON → DB 마이그레이션
    # ------------------------------------------------------------------
    def _migrate_json_sessions(self):
        if not self.sessions_dir.exists():
            return
        json_files = list(self.sessions_dir.glob("session_*.json"))
        if not json_files:
            return

        migrated = skipped = deleted = 0
        for filepath in json_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session_id = data.get("session_id")
                if not session_id:
                    filepath.unlink()
                    continue
                with self._get_conn() as conn:
                    already_exists = conn.execute("SELECT 1 FROM sessions WHERE session_id=?", (session_id,)).fetchone()
                if already_exists:
                    skipped += 1
                else:
                    session = SessionData.from_dict(data)
                    if not session.statistics and session.frame_records:
                        session.statistics = self.calculate_session_stats(session)
                    self._save_session_to_db(session)
                    migrated += 1
                filepath.unlink()
                deleted += 1
            except Exception as e:
                logger.warning(f"JSON 마이그레이션 실패 ({filepath.name}): {e}")

        if migrated or skipped:
            logger.info(f"JSON 마이그레이션: {migrated}개 임포트, {skipped}개 이미 존재, {deleted}개 JSON 삭제")

    # ------------------------------------------------------------------
    # 세션 생명주기
    # ------------------------------------------------------------------
    def start_session(self):
        session_id = str(uuid.uuid4())
        start_time = datetime.now().isoformat()
        self.current_session = SessionData(session_id=session_id, start_time=start_time)
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO sessions (session_id, start_time) VALUES (?, ?)",
                    (session_id, start_time),
                )
        logger.info(f"세션 시작: {session_id}")

    def add_frame_data(self, frame_data: dict):
        if self.current_session is None:
            logger.warning("진행 중인 세션이 없습니다.")
            return
        try:
            indicators = frame_data.get("indicators")
            ind = {}
            if indicators:
                ind = {
                    "cheek_distance":    float(indicators.cheek_distance or 0.0),
                    "eye_distance":      float(indicators.eye_distance or 0.0),
                    "shoulder_width":    float(indicators.shoulder_width or 0.0),
                    "shoulder_tilt_deg": float(indicators.shoulder_tilt_deg or 0.0),
                    "neck_offset":       float(indicators.neck_offset or 0.0),
                    "eye_line_tilt":     float(indicators.eye_line_tilt or 0.0),
                    "chin_occlusion":    float(indicators.chin_occlusion or 0.0),
                    "hand_near_face":    float(indicators.hand_near_face or 0.0),
                    "neck_offset": float(indicators.neck_offset or 0.0),
                    "eye_line_tilt": float(indicators.eye_line_tilt or 0.0),
                    "chin_occlusion": float(indicators.chin_occlusion or 0.0),
                    "hand_near_face": float(indicators.hand_near_face or 0.0),
                    "face_shoulder_ratio": float(indicators.face_shoulder_ratio or 0.0),
                }
            ts = frame_data.get("timestamp", datetime.now())
            if isinstance(ts, datetime):
                ts = ts.isoformat()
            with self._lock:
                with self._get_conn() as conn:
                    conn.execute(
                        """INSERT INTO frame_records
                           (session_id, timestamp, posture_type, probability, state,
                            cheek_distance, eye_distance, shoulder_width,
                            shoulder_tilt_deg, neck_offset, eye_line_tilt,
                            chin_occlusion, hand_near_face)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            self.current_session.session_id, ts,
                            frame_data.get("posture_type", "normal"),
                            float(frame_data.get("probability", 0.0)),
                            frame_data.get("state", "NORMAL"),
                            ind.get("cheek_distance", 0.0),
                            ind.get("eye_distance", 0.0),
                            ind.get("shoulder_width", 0.0),
                            ind.get("shoulder_tilt_deg", 0.0),
                            ind.get("neck_offset", 0.0),
                            ind.get("eye_line_tilt", 0.0),
                            ind.get("chin_occlusion", 0.0),
                            ind.get("hand_near_face", 0.0),
                        ),
                    )
                    conn.execute(
                        "UPDATE sessions SET total_frames = total_frames + 1 WHERE session_id=?",
                        (self.current_session.session_id,),
                    )
                    self.current_session.total_frames += 1

            # 프레임 레코드 생성
            timestamp = frame_data.get("timestamp", datetime.now())
            if isinstance(timestamp, datetime):
                timestamp_str = timestamp.isoformat()
            else:
                timestamp_str = timestamp

            record = FrameRecord(
                timestamp=timestamp_str,
                posture_type=frame_data.get("posture_type", "normal"),
                probability=float(frame_data.get("probability", 0.0)),
                state=frame_data.get("state", "NORMAL"),
                cheek_distance=indicator_dict.get("cheek_distance", 0.0),
                eye_distance=indicator_dict.get("eye_distance", 0.0),
                shoulder_width=indicator_dict.get("shoulder_width", 0.0),
                shoulder_tilt_deg=indicator_dict.get("shoulder_tilt_deg", 0.0),
                neck_offset=indicator_dict.get("neck_offset", 0.0),
                eye_line_tilt=indicator_dict.get("eye_line_tilt", 0.0),
                chin_occlusion=indicator_dict.get("chin_occlusion", 0.0),
                hand_near_face=indicator_dict.get("hand_near_face", 0.0),
                face_shoulder_ratio=indicator_dict.get("face_shoulder_ratio", 0.0),
            )

            self.current_session.frame_records.append(record)
            self.current_session.total_frames += 1

        except Exception as e:
            logger.error(f"프레임 데이터 추가 실패: {e}", exc_info=True)

    def end_session(self, active_duration: Optional[int] = None) -> Optional[SessionData]:
        if self.current_session is None:
            logger.warning("진행 중인 세션이 없습니다.")
            return None
        try:
            end_time = datetime.now().isoformat()
            
            # 1. 활성 탐지 시간 결정 (외부 전달값 우선, 없으면 전체 시간)
            if active_duration is not None:
                duration = active_duration
                logger.info(f"세션 종료: 활성 탐지 시간 {duration}초 (외부 입력)")
            else:
                duration = int((datetime.fromisoformat(end_time) - datetime.fromisoformat(self.current_session.start_time)).total_seconds())
                logger.info(f"세션 종료: 전체 시간 {duration}초 (계산값)")
                
            # 2. 통계 계산 (가중 평균 포함)
            stats = self._calculate_stats_from_db(self.current_session.session_id, duration)
            
            with self._lock:
                with self._get_conn() as conn:
                    conn.execute(
                        "UPDATE sessions SET end_time=?, duration_seconds=?, statistics=? WHERE session_id=?",
                        (end_time, duration, json.dumps(stats, ensure_ascii=False), self.current_session.session_id),
                    )
            
            self.current_session.end_time = end_time
            self.current_session.duration_seconds = duration
            self.current_session.statistics = stats
            self.sessions_history.append(self.current_session)
            
            session = self.current_session
            self.current_session = None
            return session
        except Exception as e:
            logger.error(f"세션 종료 중 오류: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # 통계 계산
    # ------------------------------------------------------------------
    def _calculate_stats_from_db(self, session_id: str, duration_seconds: int = 0) -> dict:
        try:
            with self._lock, self._get_conn() as conn:
                # 1. 기본 카운트 및 배분 정보 (프레임 기반)
                row = conn.execute(
                    """SELECT
                           COUNT(*) AS total,
                           SUM(CASE WHEN posture_type='forward_head'        THEN 1 ELSE 0 END) AS fh,
                           SUM(CASE WHEN posture_type='recline'             THEN 1 ELSE 0 END) AS rc,
                           SUM(CASE WHEN posture_type='chin_rest_estimated' THEN 1 ELSE 0 END) AS cr,
                           SUM(CASE WHEN posture_type='normal'              THEN 1 ELSE 0 END) AS nm,
                           SUM(CASE WHEN posture_type='side_tilt'           THEN 1 ELSE 0 END) AS stl,
                           SUM(CASE WHEN posture_type='turned_head'         THEN 1 ELSE 0 END) AS th
                       FROM frame_records WHERE session_id=?""",
                    (session_id,),
                ).fetchone()

                total = row["total"] or 0
                if total == 0:
                    return {}

                # 2. 시간 가중 평균 및 실제 지속 시간 계산
                records = conn.execute(
                    "SELECT timestamp, probability, state, posture_type FROM frame_records WHERE session_id=? ORDER BY id",
                    (session_id,),
                ).fetchall()

                total_weighted_prob = 0.0
                total_time_delta = 0.0
                
                state_durations = {"NORMAL": 0.0, "WARNING": 0.0, "BAD_POSTURE": 0.0}
                posture_changes = 0
                max_bad_streak = 0.0
                curr_bad_streak = 0.0
                prev_time = None
                prev_posture = None

                for r in records:
                    curr_time = datetime.fromisoformat(r["timestamp"]).timestamp()
                    prob = float(r["probability"] or 0.0)
                    state = r["state"].upper()
                    posture = r["posture_type"]

                    if prev_time is not None:
                        dt = max(0.0, curr_time - prev_time)
                        # 너무 큰 간격(예: 프로그램 중단 후 재개)은 가중치에서 제한 (최대 1초)
                        weight = min(dt, 1.0) 
                        
                        total_weighted_prob += prob * weight
                        total_time_delta += weight
                        
                        # 상태별 시간 누적
                        if state in state_durations:
                            state_durations[state] += weight
                        
                        # 나쁜 자세 최대 지속 시간 (Streak)
                        if state == "BAD_POSTURE":
                            curr_bad_streak += weight
                        else:
                            max_bad_streak = max(max_bad_streak, curr_bad_streak)
                            curr_bad_streak = 0.0
                        
                        # 자세 변경 횟수
                        if prev_posture and prev_posture != posture:
                            posture_changes += 1

                    prev_time = curr_time
                    prev_posture = posture
                
                max_bad_streak = max(max_bad_streak, curr_bad_streak)
                
                # 가중 평균 계산
                avg_prob = total_weighted_prob / total_time_delta if total_time_delta > 0 else 0.0
                
                # 전체 시간 (실제 기록된 시간의 합)
                dur = duration_seconds if duration_seconds > 0 else int(total_time_delta)

            return {
                "duration_seconds":           dur,
                "total_frames":               total,
                "fps":                        round(total / dur, 1) if dur > 0 else 0,
                "posture_distribution": {
                    "forward_head":        row["fh"] or 0,
                    "recline":             row["rc"] or 0,
                    "chin_rest_estimated": row["cr"] or 0,
                    "normal":              row["nm"] or 0,
                    "side_tilt":           row["stl"] or 0,
                    "turned_head":         row["th"] or 0,
                },
                "state_counts": state_durations, # 프레임 수 대신 시간(초) 저장
                "good_posture_seconds":       round(state_durations["NORMAL"], 2),
                "warning_posture_seconds":    round(state_durations["WARNING"], 2),
                "bad_posture_seconds":        round(state_durations["BAD_POSTURE"], 2),
                "good_posture_percentage":    round(state_durations["NORMAL"] / max(0.1, total_time_delta) * 100, 1),
                "warning_posture_percentage": round(state_durations["WARNING"] / max(0.1, total_time_delta) * 100, 1),
                "bad_posture_percentage":     round(state_durations["BAD_POSTURE"] / max(0.1, total_time_delta) * 100, 1),
                "posture_changes":            posture_changes,
                "max_bad_duration_seconds":   round(max_bad_streak, 2),
                "average_probability":        round(avg_prob, 3),
            }
        except Exception as e:
            logger.error(f"DB 통계 계산 실패: {e}", exc_info=True)
            return {}

    def calculate_session_stats(self, session: SessionData) -> dict:
        """frame_records 기반 통계 계산 (JSON 마이그레이션 호환용)"""
        if not session.frame_records:
            return {}
        try:
            posture_counts = {"forward_head": 0, "recline": 0, "chin_rest_estimated": 0, "normal": 0, "side_tilt": 0, "turned_head": 0}
            state_counts   = {"NORMAL": 0, "WARNING": 0, "BAD_POSTURE": 0}
            probs = []
            prev = None
            posture_changes = max_bad = bad_dur = 0

            for r in session.frame_records:
                pt = r.posture_type
                st = str(r.state).upper()
                if pt in posture_counts:
                    posture_counts[pt] += 1
                if st in state_counts:
                    state_counts[st] += 1
                probs.append(r.probability)
                if prev and prev != pt:
                    posture_changes += 1
                prev = pt
                if st == "BAD_POSTURE":
                    bad_dur += 1
                else:
                    max_bad = max(max_bad, bad_dur)
                    bad_dur = 0
            max_bad = max(max_bad, bad_dur)

            total = len(session.frame_records)
            good  = state_counts["NORMAL"]
            warn  = state_counts["WARNING"]
            bad   = state_counts["BAD_POSTURE"]
            dur   = session.duration_seconds or total

            return {
                "duration_seconds":           session.duration_seconds,
                "total_frames":               total,
                "fps":                        round(total / session.duration_seconds, 1) if session.duration_seconds > 0 else 0,
                "posture_distribution":       posture_counts,
                "state_counts":               state_counts,
                "good_posture_seconds":       round(dur * good / total, 2),
                "warning_posture_seconds":    round(dur * warn / total, 2),
                "bad_posture_seconds":        round(dur * bad  / total, 2),
                "good_posture_percentage":    round(good / total * 100, 1),
                "warning_posture_percentage": round(warn / total * 100, 1),
                "bad_posture_percentage":     round(bad  / total * 100, 1),
                "posture_changes":            posture_changes,
                "max_bad_duration_seconds":   max_bad,
                "average_probability":        round(sum(probs) / total, 3),
            }
        except Exception as e:
            logger.error(f"통계 계산 실패: {e}", exc_info=True)
            return {}

    # ------------------------------------------------------------------
    # 세션 로드 / 저장 / 삭제
    # ------------------------------------------------------------------
    def load_recent_sessions(self, count: int = 30) -> List[SessionData]:
        """최근 N개 세션 로드 (통계만, frame_records 미포함)"""
        try:
            with self._lock, self._get_conn() as conn:
                rows = conn.execute(
                    """SELECT session_id, start_time, end_time,
                              duration_seconds, total_frames, statistics, notes
                       FROM sessions
                       WHERE end_time IS NOT NULL
                       ORDER BY start_time DESC
                       LIMIT ?""",
                    (count,),
                ).fetchall()

            sessions = []
            for row in rows:
                try:
                    stats = json.loads(row["statistics"] or "{}")
                    sessions.append(SessionData(
                        session_id=row["session_id"],
                        start_time=row["start_time"],
                        end_time=row["end_time"],
                        duration_seconds=row["duration_seconds"] or 0,
                        total_frames=row["total_frames"] or 0,
                        statistics=stats,
                        notes=row["notes"] or "",
                    ))
                except Exception as e:
                    logger.warning(f"세션 행 파싱 실패: {e}")

            logger.info(f"최근 {len(sessions)}개 세션 로드됨")
            return sessions
        except Exception as e:
            logger.error(f"세션 로드 실패: {e}", exc_info=True)
            return []

    def _save_session_to_db(self, session: SessionData):
        """SessionData UPSERT (JSON 마이그레이션용)"""
        try:
            stats_json = json.dumps(session.statistics or {}, ensure_ascii=False)
            with self._lock:
                with self._get_conn() as conn:
                    conn.execute(
                        """INSERT OR REPLACE INTO sessions
                           (session_id, start_time, end_time,
                            duration_seconds, total_frames, statistics, notes)
                           VALUES (?,?,?,?,?,?,?)""",
                        (session.session_id, session.start_time, session.end_time,
                         session.duration_seconds, session.total_frames, stats_json, session.notes),
                    )
                    if session.frame_records:
                        conn.executemany(
                            """INSERT OR IGNORE INTO frame_records
                               (session_id, timestamp, posture_type, probability, state,
                                cheek_distance, eye_distance, shoulder_width,
                                shoulder_tilt_deg, neck_offset, eye_line_tilt,
                                chin_occlusion, hand_near_face)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            [(session.session_id, r.timestamp, r.posture_type, r.probability,
                              r.state, r.cheek_distance, r.eye_distance, r.shoulder_width,
                              r.shoulder_tilt_deg, r.neck_offset, r.eye_line_tilt,
                              r.chin_occlusion, r.hand_near_face)
                             for r in session.frame_records],
                        )
        except Exception as e:
            logger.error(f"세션 DB 저장 실패: {e}", exc_info=True)

    def load_sessions_by_date_range(self, start_date: str, end_date: str) -> List[SessionData]:
        """날짜 범위로 세션 로드 (start_date 이상 end_date 미만, ISO 형식)"""
        try:
            with self._lock, self._get_conn() as conn:
                rows = conn.execute(
                    """SELECT session_id, start_time, end_time,
                              duration_seconds, total_frames, statistics, notes
                       FROM sessions
                       WHERE end_time IS NOT NULL
                         AND start_time >= ? AND start_time < ?
                       ORDER BY start_time ASC""",
                    (start_date, end_date),
                ).fetchall()

            sessions = []
            for row in rows:
                try:
                    stats = json.loads(row["statistics"] or "{}")
                    sessions.append(SessionData(
                        session_id=row["session_id"],
                        start_time=row["start_time"],
                        end_time=row["end_time"],
                        duration_seconds=row["duration_seconds"] or 0,
                        total_frames=row["total_frames"] or 0,
                        statistics=stats,
                        notes=row["notes"] or "",
                    ))
                except Exception as e:
                    logger.warning(f"세션 행 파싱 실패: {e}")

            logger.info(f"{start_date} ~ {end_date} 세션 {len(sessions)}개 로드됨")
            return sessions
        except Exception as e:
            logger.error(f"날짜 범위 세션 로드 실패: {e}", exc_info=True)
            return []

    # 하위 호환
    def save_session_to_file(self, session: SessionData):
        self._save_session_to_db(session)

    def load_session_from_file(self, filepath: str) -> Optional[SessionData]:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            session = SessionData.from_dict(data)
            if session.frame_records and not session.statistics:
                session.statistics = self.calculate_session_stats(session)
            return session
        except Exception as e:
            logger.error(f"세션 파일 로드 실패 ({filepath}): {e}", exc_info=True)
            return None

    def delete_session(self, session_id: str) -> bool:
        try:
            with self._lock:
                with self._get_conn() as conn:
                    conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
            logger.info(f"세션 삭제: {session_id}")
            return True
        except Exception as e:
            logger.error(f"세션 삭제 실패: {e}", exc_info=True)
            return False


def create_session_manager(config: ConfigManager) -> SessionManager:
    return SessionManager(config)
