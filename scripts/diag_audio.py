import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtMultimedia import QSoundEffect, QMediaDevices
from PyQt6.QtCore import QTimer, QUrl

try:
    from src.core.sound_manager import SoundManager
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)

app = QApplication(sys.argv)
sm = SoundManager()

# Use _effect which is the internal attribute in SoundManager
effect = sm._effect


def get_status_name(status):
    try:
        # Check integer values for PyQt6 QSoundEffect.Status
        # 0: Null, 1: Loading, 2: Ready, 3: Error
        mapping = {0: "Null", 1: "Loading", 2: "Ready", 3: "Error"}
        val = int(status)
        return mapping.get(val, f"Unknown({val})")
    except:
        return str(status)


current_status = effect.status()
print(f"1) QSoundEffect status: {get_status_name(current_status)}")

wav_path = sm._alert_wav
print(f"2) Alert wav file exists: {wav_path.exists()}")
print(f"3) Resolved wav path: {wav_path.absolute()}")
print(f"4) Current volume: {effect.volume() * 100}%")

default_device = QMediaDevices.defaultAudioOutput()
print(
    f"5) Default audio output: {default_device.description() if not default_device.isNull() else 'None'}"
)

if current_status == QSoundEffect.Status.Error:
    print("6) QSoundEffect is in Error status.")
else:
    print("6) Status is not Error.")

print("Calling play_alert(59)...")
sm.play_alert(59)


def finalize():
    print(f"Post-play status: {get_status_name(effect.status())}")
    app.quit()


QTimer.singleShot(1500, finalize)
app.exec()
