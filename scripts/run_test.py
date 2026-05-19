import sys
import os
import json

# Ensure the path is correct
sys.path.insert(0, r'c:\Users\이우성\OneDrive\Desktop\baromok_ws')

try:
    from src.core.sound_manager import SoundManager
    from src.config import SettingsConfig
    
    # Load current config
    config_path = 'data/config.json'
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        print(f"Current config - sound_enabled: {config_data.get('sound_enabled')}, sound_volume: {config_data.get('sound_volume')}")
    else:
        print(f"Config file not found: {config_path}")

    # Create SoundManager
    sm = SoundManager()
    print("SoundManager created")

    # Test 1: Direct play with volume 90
    print("\nTest 1: play_alert(90)")
    sm.play_alert(90)

    # Test 3: play_beep (QSoundEffect does not provide frequency API; keep for compatibility)
    print("\nTest 3: play_beep(1000, 300) - If available")
    try:
        sm.play_beep(1000, 300)
    except Exception:
        print("play_beep not supported in QSoundEffect mode")

    print("\nAll tests completed")
except Exception as e:
    print(f"Error occurred: {e}")
    import traceback
    traceback.print_exc()
