"""QSoundEffect 기반 SoundManager 테스트"""

import sys
from pathlib import Path

# PyQt6 앱 생성 (QSoundEffect 사용 전 필수)
from PyQt6.QtWidgets import QApplication

# 앱 생성
app = QApplication(sys.argv)

# SoundManager 테스트
from src.core.sound_manager import SoundManager

print("=" * 60)
print("QSoundEffect 기반 SoundManager 테스트")
print("=" * 60)

# SoundManager 생성
sound_manager = SoundManager()
print("✓ SoundManager 생성 완료")

# 음량 설정 테스트
sound_manager.set_volume_percent(100)
print("✓ 음량 설정 완료: 100%")

# 알림음 재생 테스트
print("\n>>> play_alert(100) 호출 - 소리가 재생되어야 합니다")
sound_manager.play_alert(100)

print("\n✓ QSoundEffect 기반 SoundManager 모든 테스트 완료")
print("=" * 60)
