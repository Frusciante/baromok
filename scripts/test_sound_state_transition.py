#!/usr/bin/env python3
"""
실제 앱 상태 전이를 시뮬레이션하여 알림음 문제 진단
"""

import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logger import get_logger
from src.config import ConfigManager, SettingsConfig
from src.core.state_machine import StateMachine, PostureState, StateTransitionEvent

logger = get_logger(__name__, "DEBUG")


def test_state_transition_and_sound():
    """실제 상태 전이 시뮬레이션"""
    logger.info("=" * 70)
    logger.info("상태 전이 시뮬레이션 테스트")
    logger.info("=" * 70)

    try:
        # 설정 로드
        config = ConfigManager()
        settings = SettingsConfig.load_from_json("data/config.json", config)
        logger.info(f"sound_enabled: {settings.sound_enabled}")
        logger.info(f"sound_volume: {settings.sound_volume}")

        # 상태 머신 생성
        state_machine = StateMachine(config)
        logger.info(f"초기 상태: {state_machine.current_state.value}")

        # 콜백 설정
        call_count = [0]
        events_received = []

        def handle_state_transition(event: StateTransitionEvent):
            call_count[0] += 1
            events_received.append(
                {
                    "from": event.from_state.value,
                    "to": event.to_state.value,
                    "timestamp": time.time(),
                }
            )
            logger.info(
                f"상태 전이 콜백: {event.from_state.value} -> {event.to_state.value}"
            )

            # 실제 앱의 로직을 따라
            alert_type = "warning" if event.to_state.value == "warning" else "danger"
            logger.info(f"  alert_type = {alert_type}")

            if event.to_state.value == "bad_posture":
                logger.info(
                    f"  [조건 충족] sound_enabled={settings.sound_enabled} and to_state=='bad_posture'"
                )
                if settings.sound_enabled:
                    logger.info(
                        f"  → _show_alert_popup에서 _play_alert_sound_async() 호출 예정"
                    )
                    # 실제 재생
                    from src.core.sound_manager import SoundManager

                    sm = SoundManager()
                    sm.play_alert(settings.sound_volume)
                    logger.info(f"  → 알림음 재생됨!")

            if event.to_state.value == "bad_posture":
                logger.info(f"  [조건 충족] event.to_state.value == 'bad_posture'")
                logger.info(f"  → _play_bad_posture_sound_once() 호출 예정")

        state_machine.register_state_change_callback(handle_state_transition)
        logger.info("콜백 등록 완료\n")

        # Test 1: NORMAL -> WARNING
        logger.info("-" * 70)
        logger.info("Test 1: NORMAL -> WARNING 전이")
        logger.info("-" * 70)
        state_machine.update_state(PostureState.WARNING)
        time.sleep(1)

        # Test 2: WARNING -> BAD_POSTURE
        logger.info("\n" + "-" * 70)
        logger.info("Test 2: WARNING -> BAD_POSTURE 전이")
        logger.info("-" * 70)
        state_machine.update_state(PostureState.BAD_POSTURE)
        time.sleep(1)

        # Test 3: BAD_POSTURE -> NORMAL (알림음 없어야 함)
        logger.info("\n" + "-" * 70)
        logger.info("Test 3: BAD_POSTURE -> NORMAL 전이")
        logger.info("-" * 70)
        state_machine.update_state(PostureState.NORMAL)
        time.sleep(1)

        # Test 4: 빠른 연속 전이
        logger.info("\n" + "-" * 70)
        logger.info("Test 4: 빠른 연속 전이 (WARNING -> BAD_POSTURE -> BAD_POSTURE)")
        logger.info("-" * 70)
        state_machine.update_state(PostureState.WARNING)
        time.sleep(0.5)
        state_machine.update_state(PostureState.BAD_POSTURE)
        time.sleep(0.5)
        state_machine.update_state(PostureState.BAD_POSTURE)  # 같은 상태로 유지
        time.sleep(1)

        logger.info("\n" + "=" * 70)
        logger.info(f"콜백 호출 총 {call_count[0]}회")
        logger.info("전이 이벤트:")
        for i, event in enumerate(events_received, 1):
            logger.info(f"  {i}. {event['from']} -> {event['to']}")

        return True

    except Exception as e:
        logger.error(f"테스트 실패: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    logger.info("알림음 상태 전이 진단 시작\n")
    success = test_state_transition_and_sound()

    logger.info("\n" + "=" * 70)
    if success:
        logger.info("✓ 테스트 완료")
    else:
        logger.info("✗ 테스트 실패")
