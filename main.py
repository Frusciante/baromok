#!/usr/bin/env python3
"""
바로록 - 자세 측정 시스템

메인 진입점
"""
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent))

from src.config import ConfigManager
from src.utils.logger import get_logger
from src.ui.app import BarorokApp

logger = get_logger(__name__)


def main():
    """메인 진입점"""
    try:
        logger.info("=== 바로록 애플리케이션 시작 ===")
        
        # 설정 로드 (검증)
        config = ConfigManager()
        
        # 판정 기준
        posture_criteria = config.get_posture_criteria()
        logger.info(f"✓ 판정 기준 버전: {posture_criteria.get('version', 'unknown')}")
        
        # 애플리케이션 설정
        camera_res_w = config.get_app_setting('camera_resolution_width')
        camera_res_h = config.get_app_setting('camera_resolution_height')
        camera_fps = config.get_app_setting('camera_fps')
        logger.info(f"✓ 웹캠 해상도: {camera_res_w}x{camera_res_h}")
        logger.info(f"✓ 웹캠 FPS: {camera_fps}")
        
        # 알림 설정
        sound_alert = config.get_app_setting('enable_sound_alert')
        popup_alert = config.get_app_setting('enable_popup_alert')
        logger.info(f"✓ 알림 설정: 소리={sound_alert}, 팝업={popup_alert}")
        
        logger.info("✓ Phase 1 검증 완료")
        logger.info("✓ Phase 2 검증 완료")
        logger.info("✓ Phase 3 UI 구현 완료 (skeleton)")
        
        # PyQt 애플리케이션 실행
        logger.info("PyQt 애플리케이션 시작...")
        app = BarorokApp()
        return app.run()
        
    except Exception as e:
        logger.error(f"오류 발생: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
