"""
상태 머신

자세 감지 상태 관리 및 전이
"""
import time
from enum import Enum
from typing import Optional, Callable, List
from dataclasses import dataclass

from src.config import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PostureState(Enum):
    """자세 감지 상태"""
    NORMAL = "normal"  # 바른 자세
    WARNING = "warning"  # 경고 (잠시만 나쁜 자세)
    BAD_POSTURE = "bad_posture"  # 나쁜 자세 (지속)


@dataclass
class StateTransitionEvent:
    """상태 전이 이벤트"""
    from_state: PostureState
    to_state: PostureState
    confirmed_posture: Optional[str]
    timestamp: float
    time_in_previous_state: float


class StateMachine:
    """상태 머신"""
    
    def __init__(self, config: ConfigManager):
        """
        초기화
        
        Args:
            config: 설정 관리자
        """
        self.config = config
        self.current_state = PostureState.NORMAL
        self.state_enter_time = time.time()
        
        # 상태 전이 콜백
        self.state_transition_callbacks: List[Callable[[StateTransitionEvent], None]] = []
        
        # 상태별 타이머
        self.state_timers = {}
        
        logger.info("StateMachine 초기화 완료")
    
    def update_state(
        self, 
        confirmed_posture: Optional[str],
        fps: int = 30
    ) -> PostureState:
        """
        상태 전이 로직
        
        전이 규칙:
        - NORMAL:
          - confirmed_posture가 None → NORMAL 유지
          - confirmed_posture가 있음 → WARNING 전이
        
        - WARNING:
          - confirmed_posture가 None → NORMAL 전이
          - confirmed_posture가 있음 (3초 이상) → BAD_POSTURE 전이
        
        - BAD_POSTURE:
          - confirmed_posture가 None (1초 이상) → WARNING 전이
          - confirmed_posture가 있음 → BAD_POSTURE 유지
        
        Args:
            confirmed_posture: 확정된 자세 (또는 None)
            fps: FPS
            
        Returns:
            현재 상태
        """
        previous_state = self.current_state
        time_in_previous_state = self.get_time_in_current_state()
        
        try:
            state_machine_config = self.config.get_state_machine_config()
            
            if self.current_state == PostureState.NORMAL:
                if confirmed_posture is not None:
                    # 나쁜 자세 감지됨
                    self._transition_to(PostureState.WARNING, confirmed_posture)
                    logger.info(f"상태 전이: NORMAL → WARNING (자세: {confirmed_posture})")
            
            elif self.current_state == PostureState.WARNING:
                if confirmed_posture is None:
                    # 나쁜 자세 해제
                    self._transition_to(PostureState.NORMAL, None)
                    logger.info("상태 전이: WARNING → NORMAL (자세 정상화)")
                else:
                    # 나쁜 자세 지속 (3초 이상이면 BAD_POSTURE로)
                    if time_in_previous_state >= 3.0:
                        self._transition_to(PostureState.BAD_POSTURE, confirmed_posture)
                        logger.warning(
                            f"상태 전이: WARNING → BAD_POSTURE (자세: {confirmed_posture}, "
                            f"지속시간: {time_in_previous_state:.1f}초)"
                        )
            
            elif self.current_state == PostureState.BAD_POSTURE:
                if confirmed_posture is None:
                    # 나쁜 자세 완화 (1초 이상 지속되면)
                    if time_in_previous_state >= 1.0:
                        self._transition_to(PostureState.WARNING, None)
                        logger.info(f"상태 전이: BAD_POSTURE → WARNING (자세 개선, {time_in_previous_state:.1f}초)")
                else:
                    # 나쁜 자세 지속
                    self._transition_to(PostureState.BAD_POSTURE, confirmed_posture)
        
        except Exception as e:
            logger.error(f"상태 전이 실패: {e}")
        
        return self.current_state
    
    def _transition_to(self, new_state: PostureState, confirmed_posture: Optional[str]):
        """
        상태 전이 처리
        
        Args:
            new_state: 새로운 상태
            confirmed_posture: 확정된 자세
        """
        if new_state == self.current_state and confirmed_posture is None:
            # 상태 유지 (이벤트 발생 안 함)
            return
        
        old_state = self.current_state
        time_in_previous = self.get_time_in_current_state()
        
        self.current_state = new_state
        self.state_enter_time = time.time()
        
        # 이벤트 발생
        event = StateTransitionEvent(
            from_state=old_state,
            to_state=new_state,
            confirmed_posture=confirmed_posture,
            timestamp=self.state_enter_time,
            time_in_previous_state=time_in_previous
        )
        
        self._trigger_state_change_event(event)
    
    def register_state_change_callback(self, callback: Callable[[StateTransitionEvent], None]):
        """
        상태 변경 시 실행할 콜백 등록
        
        Args:
            callback: 콜백 함수
        """
        if callback not in self.state_transition_callbacks:
            self.state_transition_callbacks.append(callback)
            logger.debug(f"상태 변경 콜백 등록: {callback.__name__}")
    
    def unregister_state_change_callback(self, callback: Callable[[StateTransitionEvent], None]):
        """
        콜백 등록 해제
        
        Args:
            callback: 콜백 함수
        """
        if callback in self.state_transition_callbacks:
            self.state_transition_callbacks.remove(callback)
            logger.debug(f"상태 변경 콜백 해제: {callback.__name__}")
    
    def _trigger_state_change_event(self, event: StateTransitionEvent):
        """
        상태 변경 이벤트 발생
        
        Args:
            event: StateTransitionEvent
        """
        for callback in self.state_transition_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"콜백 실행 실패: {e}")
    
    def get_current_state(self) -> PostureState:
        """
        현재 상태 조회
        
        Returns:
            현재 PostureState
        """
        return self.current_state
    
    def get_time_in_current_state(self) -> float:
        """
        현재 상태에서 경과한 시간 (초)
        
        Returns:
            경과 시간
        """
        return time.time() - self.state_enter_time
    
    def reset(self):
        """상태를 NORMAL으로 초기화"""
        self.current_state = PostureState.NORMAL
        self.state_enter_time = time.time()
        logger.info("상태 머신 초기화 (NORMAL으로 전환)")
    
    def get_state_name(self) -> str:
        """현재 상태명 반환"""
        state_names = {
            PostureState.NORMAL: "바른 자세",
            PostureState.WARNING: "경고",
            PostureState.BAD_POSTURE: "나쁜 자세"
        }
        return state_names.get(self.current_state, "알 수 없음")


def create_state_machine(config: ConfigManager) -> StateMachine:
    """상태 머신 생성 (팩토리 함수)"""
    return StateMachine(config)
