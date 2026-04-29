"""
세션 관리자

세션 데이터 수집, 계산, 저장
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any
import logging

from src.config import ConfigManager
from src.core.judgment_engine import PostureType
from src.core.state_machine import PostureState

logger = logging.getLogger(__name__)


@dataclass
class FrameRecord:
    """프레임별 기록"""
    timestamp: str                 # ISO 형식
    posture_type: str              # "normal", "forward_head", "recline", etc.
    probability: float             # 0-1
    state: str                     # "NORMAL", "WARNING", "BAD_POSTURE"
    cheek_distance: float          # 지표값
    eye_distance: float
    face_shoulder_ratio: float
    shoulder_width: float
    shoulder_tilt_deg: float
    neck_offset: float
    eye_line_tilt: float
    chin_occlusion: float
    hand_near_face: float


@dataclass
class SessionData:
    """세션 데이터"""
    session_id: str                # UUID
    start_time: str                # ISO 형식
    end_time: Optional[str] = None
    duration_seconds: int = 0
    total_frames: int = 0
    frame_records: List[FrameRecord] = field(default_factory=list)
    
    # 통계
    statistics: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    
    def to_dict(self) -> dict:
        """딕셔너리로 변환 (JSON 저장용)"""
        return {
            'session_id': self.session_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_seconds': self.duration_seconds,
            'total_frames': self.total_frames,
            'frame_records': [asdict(r) for r in self.frame_records],
            'statistics': self.statistics,
            'notes': self.notes
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'SessionData':
        """딕셔너리에서 생성"""
        frame_records = [FrameRecord(**r) for r in data.get('frame_records', [])]
        return SessionData(
            session_id=data['session_id'],
            start_time=data['start_time'],
            end_time=data.get('end_time'),
            duration_seconds=data.get('duration_seconds', 0),
            total_frames=data.get('total_frames', 0),
            frame_records=frame_records,
            statistics=data.get('statistics', {}),
            notes=data.get('notes', '')
        )


class SessionManager:
    """세션 데이터 관리자"""
    
    def __init__(self, config: ConfigManager):
        """
        초기화
        
        Args:
            config: ConfigManager 싱글톤
        """
        self.config = config
        self.current_session: Optional[SessionData] = None
        self.sessions_history: List[SessionData] = []
        
        # 세션 저장 디렉토리
        self.sessions_dir = Path(__file__).parent.parent.parent / "data" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"SessionManager 초기화 (저장 경로: {self.sessions_dir})")
    
    def start_session(self):
        """새 세션 시작"""
        session_id = str(uuid.uuid4())
        start_time = datetime.now().isoformat()
        
        self.current_session = SessionData(
            session_id=session_id,
            start_time=start_time
        )
        
        logger.info(f"세션 시작: {session_id}")
    
    def add_frame_data(self, frame_data: dict):
        """
        프레임 데이터 추가
        
        Args:
            frame_data: {
                'posture_type': str,
                'probability': float,
                'state': str ("NORMAL", "WARNING", "BAD_POSTURE"),
                'indicators': PostureIndicators,
                'timestamp': datetime
            }
        """
        if self.current_session is None:
            logger.warning("진행 중인 세션이 없습니다. start_session()을 호출하세요.")
            return
        
        try:
            # 지표 추출
            indicators = frame_data.get('indicators')
            indicator_dict = {}
            if indicators:
                indicator_dict = {
                    'cheek_distance': float(indicators.cheek_distance or 0.0),
                    'eye_distance': float(indicators.eye_distance or 0.0),
                    'face_shoulder_ratio': float(indicators.face_shoulder_ratio or 0.0),
                    'shoulder_width': float(indicators.shoulder_width or 0.0),
                    'shoulder_tilt_deg': float(indicators.shoulder_tilt_deg or 0.0),
                    'neck_offset': float(indicators.neck_offset or 0.0),
                    'eye_line_tilt': float(indicators.eye_line_tilt or 0.0),
                    'chin_occlusion': float(indicators.chin_occlusion or 0.0),
                    'hand_near_face': float(indicators.hand_near_face or 0.0),
                }
            
            # 프레임 레코드 생성
            timestamp = frame_data.get('timestamp', datetime.now())
            if isinstance(timestamp, datetime):
                timestamp_str = timestamp.isoformat()
            else:
                timestamp_str = timestamp
            
            record = FrameRecord(
                timestamp=timestamp_str,
                posture_type=frame_data.get('posture_type', 'normal'),
                probability=float(frame_data.get('probability', 0.0)),
                state=frame_data.get('state', 'NORMAL'),
                cheek_distance=indicator_dict.get('cheek_distance', 0.0),
                eye_distance=indicator_dict.get('eye_distance', 0.0),
                face_shoulder_ratio=indicator_dict.get('face_shoulder_ratio', 0.0),
                shoulder_width=indicator_dict.get('shoulder_width', 0.0),
                shoulder_tilt_deg=indicator_dict.get('shoulder_tilt_deg', 0.0),
                neck_offset=indicator_dict.get('neck_offset', 0.0),
                eye_line_tilt=indicator_dict.get('eye_line_tilt', 0.0),
                chin_occlusion=indicator_dict.get('chin_occlusion', 0.0),
                hand_near_face=indicator_dict.get('hand_near_face', 0.0),
            )
            
            self.current_session.frame_records.append(record)
            self.current_session.total_frames += 1
            
        except Exception as e:
            logger.error(f"프레임 데이터 추가 실패: {e}", exc_info=True)
    
    def end_session(self) -> Optional[SessionData]:
        """
        세션 종료 및 저장
        
        Returns:
            SessionData (통계 포함) 또는 None
        """
        if self.current_session is None:
            logger.warning("진행 중인 세션이 없습니다.")
            return None
        
        try:
            # 종료 시간 설정
            self.current_session.end_time = datetime.now().isoformat()
            
            # 지속 시간 계산
            start = datetime.fromisoformat(self.current_session.start_time)
            end = datetime.fromisoformat(self.current_session.end_time)
            self.current_session.duration_seconds = int((end - start).total_seconds())
            
            # 통계 계산
            self.current_session.statistics = self.calculate_session_stats(
                self.current_session
            )
            
            # 저장
            self.save_session_to_file(self.current_session)
            
            # 히스토리에 추가
            self.sessions_history.append(self.current_session)
            
            logger.info(
                f"세션 종료 및 저장: {self.current_session.session_id} "
                f"({self.current_session.duration_seconds}초)"
            )
            
            session = self.current_session
            self.current_session = None
            return session
            
        except Exception as e:
            logger.error(f"세션 종료 중 오류: {e}", exc_info=True)
            return None
    
    def calculate_session_stats(self, session: SessionData) -> dict:
        """
        세션 통계 계산
        
        Args:
            session: SessionData
        
        Returns:
            {
                'duration_seconds': int,
                'total_frames': int,
                'posture_distribution': {...},
                'good_posture_percentage': float,
                'bad_posture_percentage': float,
                'warning_posture_percentage': float,
                'posture_changes': int,
                'max_bad_duration_seconds': int,
                'average_probability': float
            }
        """
        if not session.frame_records:
            return {}
        
        try:
            # 자세 분포
            posture_distribution = {
                'normal': 0,
                'forward_head': 0,
                'recline': 0,
                'crossed_leg_estimated': 0,
                'chin_rest_estimated': 0
            }
            
            state_counts = {
                'NORMAL': 0,
                'WARNING': 0,
                'BAD_POSTURE': 0
            }
            
            probabilities = []
            prev_posture = None
            posture_changes = 0
            max_bad_duration = 0
            bad_duration = 0
            
            for record in session.frame_records:
                # 자세 분포
                posture = record.posture_type
                if posture in posture_distribution:
                    posture_distribution[posture] += 1
                
                # 상태 카운트
                state = record.state
                if state in state_counts:
                    state_counts[state] += 1
                
                # 확률 평균
                probabilities.append(record.probability)
                
                # 자세 변화 횟수
                if prev_posture and prev_posture != posture:
                    posture_changes += 1
                prev_posture = posture
                
                # 최악 지속 시간
                if state == 'BAD_POSTURE':
                    bad_duration += 1
                else:
                    max_bad_duration = max(max_bad_duration, bad_duration)
                    bad_duration = 0
            
            max_bad_duration = max(max_bad_duration, bad_duration)
            
            # 백분율 계산
            total = len(session.frame_records)
            good_count = state_counts['NORMAL']
            warning_count = state_counts['WARNING']
            bad_count = state_counts['BAD_POSTURE']
            
            good_percentage = (good_count / total * 100) if total > 0 else 0
            warning_percentage = (warning_count / total * 100) if total > 0 else 0
            bad_percentage = (bad_count / total * 100) if total > 0 else 0
            
            # 평균 확률
            avg_probability = (sum(probabilities) / len(probabilities)) if probabilities else 0
            
            return {
                'duration_seconds': session.duration_seconds,
                'total_frames': total,
                'fps': round(total / session.duration_seconds, 1) if session.duration_seconds > 0 else 0,
                'posture_distribution': posture_distribution,
                'state_counts': state_counts,
                'good_posture_percentage': round(good_percentage, 1),
                'warning_posture_percentage': round(warning_percentage, 1),
                'bad_posture_percentage': round(bad_percentage, 1),
                'posture_changes': posture_changes,
                'max_bad_duration_seconds': max_bad_duration,
                'average_probability': round(avg_probability, 3)
            }
            
        except Exception as e:
            logger.error(f"통계 계산 실패: {e}", exc_info=True)
            return {}
    
    def load_recent_sessions(self, count: int = 10) -> List[SessionData]:
        """
        최근 N개 세션 로드
        
        Args:
            count: 로드할 세션 수
        
        Returns:
            SessionData 리스트 (최신순)
        """
        try:
            session_files = sorted(
                self.sessions_dir.glob("session_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )[:count]
            
            sessions = []
            for filepath in session_files:
                try:
                    session = self.load_session_from_file(str(filepath))
                    if session:
                        sessions.append(session)
                except Exception as e:
                    logger.warning(f"세션 파일 로드 실패 ({filepath}): {e}")
            
            logger.info(f"최근 {len(sessions)}개 세션 로드됨")
            return sessions
            
        except Exception as e:
            logger.error(f"최근 세션 로드 실패: {e}", exc_info=True)
            return []
    
    def save_session_to_file(self, session: SessionData):
        """
        세션을 JSON으로 저장
        
        Args:
            session: SessionData
        """
        try:
            filename = f"session_{session.session_id}.json"
            filepath = self.sessions_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"세션 저장: {filepath}")
            
        except Exception as e:
            logger.error(f"세션 저장 실패: {e}", exc_info=True)
    
    def load_session_from_file(self, filepath: str) -> Optional[SessionData]:
        """
        JSON에서 세션 로드
        
        Args:
            filepath: 파일 경로
        
        Returns:
            SessionData 또는 None
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            session = SessionData.from_dict(data)
            logger.info(f"세션 로드: {filepath}")
            return session
            
        except Exception as e:
            logger.error(f"세션 로드 실패 ({filepath}): {e}", exc_info=True)
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """
        세션 삭제
        
        Args:
            session_id: 세션 ID
        
        Returns:
            성공 여부
        """
        try:
            filename = f"session_{session_id}.json"
            filepath = self.sessions_dir / filename
            
            if filepath.exists():
                filepath.unlink()
                logger.info(f"세션 삭제: {session_id}")
                return True
            else:
                logger.warning(f"세션 파일 없음: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"세션 삭제 실패: {e}", exc_info=True)
            return False


def create_session_manager(config: ConfigManager) -> SessionManager:
    """세션 관리자 생성"""
    return SessionManager(config)
