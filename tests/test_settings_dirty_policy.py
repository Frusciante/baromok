import os
import json
import tempfile
from src.config import SettingsConfig, ConfigManager


def test_settings_dirty_and_persist():
    # 준비: 임시 config 파일 사용
    cfg = ConfigManager()
    # 기본 설정값 불러오기
    settings = SettingsConfig()

    # 임시 파일에 저장
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    try:
        settings.save_to_json(path)
        # 로드
        loaded = SettingsConfig.load_from_json(path, cfg)
        assert abs(loaded.forward_head_sensitivity - settings.forward_head_sensitivity) < 1e-9

        # 변경 적용 시 dirty 플래그 시뮬레이션 (앱에서 관리)
        loaded.forward_head_sensitivity = settings.forward_head_sensitivity + 0.01
        # 저장
        loaded.save_to_json(path)
        reloaded = SettingsConfig.load_from_json(path, cfg)
        assert abs(reloaded.forward_head_sensitivity - loaded.forward_head_sensitivity) < 1e-9
    finally:
        os.remove(path)


if __name__ == '__main__':
    test_settings_dirty_and_persist()
    print('ok')
