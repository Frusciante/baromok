"""
알림음 관리 모듈

PyQt6 QSoundEffect를 사용하여 경고 알림음을 재생합니다.
"""

from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtWidgets import QApplication

from src.utils.logger import get_logger
from src.utils.paths import SOUNDS_DIR

logger = get_logger(__name__)


class SoundManager:
    """알림음 관리 클래스 - QSoundEffect 기반"""

    def __init__(self):
        """SoundManager 초기화"""
        self._volume_percent = 70
        self._effect = None
        self._alert_wav = SOUNDS_DIR / "alert.wav"

        # QApplication이 존재하고 alert.wav 파일이 있으면 QSoundEffect 초기화
        if QApplication.instance() is not None and self._alert_wav.exists():
            try:
                self._effect = QSoundEffect()
                self._effect.setSource(QUrl.fromLocalFile(str(self._alert_wav)))
                self._effect.setLoopCount(1)
                self._effect.setVolume(self._volume_percent / 100.0)
                logger.info(f"QSoundEffect 초기화 완료: {self._alert_wav}")
            except Exception as e:
                logger.error(f"QSoundEffect 초기화 실패: {e}")
                self._effect = None
        else:
            logger.warning(
                f"QSoundEffect 초기화 불가: "
                f"QApplication={QApplication.instance() is not None}, "
                f"alert.wav={self._alert_wav.exists()}"
            )

    def set_volume_percent(self, volume_percent: int):
        """
        볼륨 설정 (0-100)

        Args:
            volume_percent: 음량 비율 (0-100%)
        """
        if not isinstance(volume_percent, (int, float)):
            logger.warning(f"음량 타입 오류: {type(volume_percent)}, 기본값(70) 사용")
            volume_percent = 70

        self._volume_percent = max(0, min(100, int(volume_percent)))

        # QSoundEffect에 반영
        if self._effect is not None:
            self._effect.setVolume(self._volume_percent / 100.0)
            logger.debug(f"볼륨 설정: {self._volume_percent}%")

    def play_alert(self, volume_percent: int = 70):
        """
        경고 알림음 재생

        Args:
            volume_percent: 음량 (0-100%)
        """
        self.set_volume_percent(volume_percent)

        if self._volume_percent <= 0:
            logger.debug("음량이 0%이므로 알림음 재생 스킵")
            return

        if self._effect is not None and self._alert_wav.exists():
            try:
                self._effect.stop()
                self._effect.play()
                logger.info(
                    f"QSoundEffect 알림음 재생: {self._alert_wav} (음량: {self._volume_percent}%)"
                )
            except Exception as e:
                logger.error(f"QSoundEffect 재생 실패: {e}")
        else:
            logger.error(
                f"알림음 재생 불가: effect={self._effect is not None}, file={self._alert_wav.exists()}"
            )
