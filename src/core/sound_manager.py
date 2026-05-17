"""
알림음 관리 모듈

PyQt6 QSoundEffect를 사용해 알림음을 재생하고, 슬라이더 값에 따라 실제 볼륨을 제어합니다.
"""

import math
import struct
import wave
from pathlib import Path

from PyQt6.QtCore import QEventLoop, QTimer, QUrl
from PyQt6.QtMultimedia import QSoundEffect

from src.utils.logger import get_logger

logger = get_logger(__name__)


class SoundManager:
    """알림음 관리 클래스"""

    def __init__(self):
        """SoundManager 초기화"""
        self.is_playing = False
        self._volume_percent = 70
        self._effect = QSoundEffect()

        self._assets_dir = Path("assets")
        self._assets_dir.mkdir(parents=True, exist_ok=True)
        self._alert_wav = self._assets_dir / "alert_beep.wav"
        if not self._alert_wav.exists():
            self._generate_beep_wav(self._alert_wav, frequency=880, duration_ms=500)

        self._effect.setSource(QUrl.fromLocalFile(str(self._alert_wav.resolve())))
        self._effect.setLoopCount(1)
        self.set_volume_percent(self._volume_percent)
        self._wait_until_ready(timeout_ms=3000)

        logger.info("SoundManager 초기화 완료 (QSoundEffect)")

    @property
    def supports_volume_control(self) -> bool:
        return True

    def set_volume_percent(self, volume_percent: int):
        """볼륨 설정 (0-100). QSoundEffect volume(0.0~1.0)로 매핑한다."""
        if not isinstance(volume_percent, (int, float)):
            logger.warning(f"음량 타입 오류: {type(volume_percent)}, 기본값(70) 사용")
            volume_percent = 70

        self._volume_percent = max(0, min(100, int(volume_percent)))
        self._effect.setVolume(self._volume_percent / 100.0)

    def play_alert(self, volume_percent: int = 70):
        """알림음 재생"""
        self.set_volume_percent(volume_percent)

        if self._volume_percent <= 0:
            logger.debug("음량이 0%이므로 알림음 재생 스킵")
            return

        if self._effect.status().name != "Ready":
            self._wait_until_ready(timeout_ms=1000)

        try:
            self._effect.play()
            logger.info(f"알림음 재생 완료: 음량={self._volume_percent}%")
        except Exception as e:
            logger.error(f"알림음 재생 실패: {type(e).__name__}: {e}")

    def play_beep(self, frequency: int, duration_ms: int):
        """테스트용 비프 WAV를 재생한다. 실제 음량은 현재 볼륨 설정을 따른다."""
        try:
            if not self._alert_wav.exists():
                self._generate_beep_wav(self._alert_wav, frequency=frequency, duration_ms=duration_ms)
            self._effect.setSource(QUrl.fromLocalFile(str(self._alert_wav.resolve())))
            self._effect.play()
        except Exception as e:
            logger.error(f"비프음 재생 실패: {e}")

    def _generate_beep_wav(self, path: Path, frequency: int = 880, duration_ms: int = 500):
        """간단한 사인파 WAV 파일을 생성한다."""
        try:
            sample_rate = 44100
            amplitude = 12000
            total_samples = int(sample_rate * (duration_ms / 1000.0))

            with wave.open(str(path), "w") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)

                for index in range(total_samples):
                    sample_value = int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
                    wav_file.writeframes(struct.pack("<h", sample_value))

            logger.info("사인파 WAV 생성: %s", path)
        except Exception as e:
            logger.error(f"WAV 생성 실패: {e}")

    def _wait_until_ready(self, timeout_ms: int = 3000):
        """QSoundEffect가 Ready 상태가 될 때까지 짧게 이벤트 루프를 돌린다."""
        if self._effect.status().name == "Ready":
            return

        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)

        def _maybe_quit(_status=None):
            if self._effect.status().name == "Ready":
                loop.quit()

        self._effect.statusChanged.connect(_maybe_quit)
        timer.start(timeout_ms)
        loop.exec()
        try:
            self._effect.statusChanged.disconnect(_maybe_quit)
        except Exception:
            pass
