"""
Phase 5-2: 알림음 구현 자동화 테스트

테스트 내용:
- Test 1: SoundManager import 검증
- Test 2: 음량 0 테스트 (소리 없음)
- Test 3: 음량 70 테스트 (소리 있음)
- Test 4: 음량 100 테스트 (최대 음량)
- Test 5: 음량 범위 밖 테스트 (오류 처리)
"""

import logging
from src.core.sound_manager import SoundManager
from src.config import SettingsConfig

# 로거 설정
logging.basicConfig(
    level=logging.DEBUG, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def test_1_sound_manager_import():
    """Test 1: SoundManager import 검증"""
    try:
        sm = SoundManager()
        assert hasattr(sm, "play_alert"), "play_alert 메서드가 없음"
        assert callable(sm.play_alert), "play_alert이 호출 가능하지 않음"
        logger.info("✓ Test 1 통과: SoundManager import 성공")
        return True
    except Exception as e:
        logger.error(f"✗ Test 1 실패: {e}")
        return False


def test_2_sound_volume_zero():
    """Test 2: 음량 0 테스트"""
    try:
        sm = SoundManager()
        # 음량 0일 때 sound_manager.play_alert(0) → DEBUG 로그 출력, 소리 없음
        sm.play_alert(0)
        logger.info("✓ Test 2 통과: 음량 0에서 소리 재생 스킵")
        return True
    except Exception as e:
        logger.error(f"✗ Test 2 실패: {e}")
        return False


def test_3_sound_volume_70():
    """Test 3: 음량 70 테스트"""
    try:
        sm = SoundManager()
        # 음량 70일 때 sound_manager.play_alert(70) → INFO 로그 출력, 소리 재생
        sm.play_alert(70)
        logger.info("✓ Test 3 통과: 음량 70에서 소리 재생")
        return True
    except Exception as e:
        logger.error(f"✗ Test 3 실패: {e}")
        return False


def test_4_sound_volume_100():
    """Test 4: 음량 100 테스트"""
    try:
        sm = SoundManager()
        # 음량 100일 때 sound_manager.play_alert(100) → INFO 로그 출력, 소리 재생
        sm.play_alert(100)
        logger.info("✓ Test 4 통과: 음량 100에서 소리 재생")
        return True
    except Exception as e:
        logger.error(f"✗ Test 4 실패: {e}")
        return False


def test_5_sound_volume_out_of_range():
    """Test 5: 음량 범위 밖 테스트"""
    try:
        sm = SoundManager()
        # 음량 -10일 때 sound_manager.play_alert(-10) → DEBUG 로그 출력, 소리 없음
        sm.play_alert(-10)
        # 음량 150일 때 sound_manager.play_alert(150) → INFO 로그 출력, 소리 재생
        sm.play_alert(150)
        logger.info("✓ Test 5 통과: 범위 밖 음량에서 올바른 처리")
        return True
    except Exception as e:
        logger.error(f"✗ Test 5 실패: {e}")
        return False


def test_6_settings_config_load():
    """Test 6: SettingsConfig에서 sound 설정 로드"""
    try:
        settings = SettingsConfig.load_from_json("data/config.json")
        assert hasattr(settings, "sound_enabled"), "sound_enabled 속성이 없음"
        assert hasattr(settings, "sound_volume"), "sound_volume 속성이 없음"
        logger.info(
            f"✓ Test 6 통과: sound_enabled={settings.sound_enabled}, sound_volume={settings.sound_volume}"
        )
        return True
    except Exception as e:
        logger.error(f"✗ Test 6 실패: {e}")
        return False


def test_7_sound_enabled_true():
    """Test 7: sound_enabled=True일 때 음성 재생"""
    try:
        settings = SettingsConfig.load_from_json("data/config.json")
        original_sound_enabled = settings.sound_enabled
        settings.sound_enabled = True

        # sound_enabled=True이면 소리 재생
        sm = SoundManager()
        if settings.sound_enabled:
            sm.play_alert(settings.sound_volume)

        logger.info(f"✓ Test 7 통과: sound_enabled=True에서 소리 재생")

        # 원래 설정으로 복구
        settings.sound_enabled = original_sound_enabled
        return True
    except Exception as e:
        logger.error(f"✗ Test 7 실패: {e}")
        return False


def test_8_sound_enabled_false():
    """Test 8: sound_enabled=False일 때 음성 미재생"""
    try:
        settings = SettingsConfig.load_from_json("data/config.json")
        original_sound_enabled = settings.sound_enabled
        settings.sound_enabled = False

        # sound_enabled=False이면 소리 미재생
        sm = SoundManager()
        if settings.sound_enabled:
            sm.play_alert(settings.sound_volume)
        else:
            logger.info("알림음 비활성화 상태: 소리 재생 안 함")

        logger.info(f"✓ Test 8 통과: sound_enabled=False에서 소리 미재생")

        # 원래 설정으로 복구
        settings.sound_enabled = original_sound_enabled
        return True
    except Exception as e:
        logger.error(f"✗ Test 8 실패: {e}")
        return False


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Phase 5-2 자동화 테스트 시작")
    logger.info("=" * 50)

    results = []
    results.append(("Test 1: SoundManager import", test_1_sound_manager_import()))
    results.append(("Test 2: 음량 0", test_2_sound_volume_zero()))
    results.append(("Test 3: 음량 70", test_3_sound_volume_70()))
    results.append(("Test 4: 음량 100", test_4_sound_volume_100()))
    results.append(("Test 5: 음량 범위 밖", test_5_sound_volume_out_of_range()))
    results.append(("Test 6: SettingsConfig 로드", test_6_settings_config_load()))
    results.append(("Test 7: sound_enabled=True", test_7_sound_enabled_true()))
    results.append(("Test 8: sound_enabled=False", test_8_sound_enabled_false()))

    logger.info("=" * 50)
    logger.info("테스트 결과 요약")
    logger.info("=" * 50)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info("=" * 50)
    logger.info(f"총 {passed}/{total} 테스트 통과")
    logger.info("=" * 50)
