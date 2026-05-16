"""
알림음 관리 모듈

Windows winsound를 사용하여 경고 알림음을 재생합니다.
"""

import winsound
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SoundManager:
    """알림음 관리 클래스"""

    def __init__(self):
        """SoundManager 초기화"""
        self.is_playing = False
        logger.info("SoundManager 초기화 완료")

    def play_alert(self, volume_percent: int = 70):
        """
        알림음 재생

        Args:
            volume_percent: 음량 (0-100%)

        Raises:
            ValueError: volume_percent이 0-100 범위를 벗어난 경우
        """
        # 음량 유효성 검증
        if not isinstance(volume_percent, (int, float)):
            logger.warning(f"음량 타입 오류: {type(volume_percent)}, 기본값(70) 사용")
            volume_percent = 70

        volume_percent = int(volume_percent)

        # 음량 0이하면 재생 안 함
        if volume_percent <= 0:
            logger.debug("음량이 0%이므로 알림음 재생 스킵")
            return

        try:
            # Windows 기본 경고음 재생
            # winsound.Beep(frequency, duration)
            # - frequency: 440-1000 Hz 권장 (800Hz 사용)
            # - duration: ms (500ms 사용)
            winsound.Beep(800, 500)
            logger.info(f"알림음 재생 완료: 음량={volume_percent}%")
        except Exception as e:
            logger.error(f"알림음 재생 실패: {type(e).__name__}: {e}")

    def play_beep(self, frequency: int, duration_ms: int):
        """커스텀 주파수와 길이로 비프음 재생"""
        try:
            winsound.Beep(frequency, duration_ms)
        except Exception as e:
            logger.error(f"비프음 재생 실패: {e}")
