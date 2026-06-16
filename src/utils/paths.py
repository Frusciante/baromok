"""
경로 관리 유틸리티
"""
import os
import sys
from pathlib import Path

def get_app_root() -> Path:
    """
    애플리케이션의 루트 경로를 반환합니다.
    빌드된 실행 파일(.exe) 환경에서는 실행 파일이 있는 디렉토리를 반환하며,
    개발 환경에서는 프로젝트 루트 디렉토리를 반환합니다.
    """
    # 1. Nuitka/PyInstaller 빌드 환경 체크
    # Nuitka의 pyqt6 플러그인은 sys.frozen을 True로 설정합니다.
    if getattr(sys, 'frozen', False):
        # 사용자가 다운로드 받은 디렉토리에 있는 baromok.exe의 부모 폴더
        return Path(sys.executable).parent.absolute()
    
    # 2. 개발 환경 (src/utils/paths.py -> src/utils/ -> src/ -> baromok/)
    return Path(__file__).parent.parent.parent.absolute()

# 모든 리소스와 데이터의 기준이 되는 루트 경로
APP_ROOT = get_app_root()

# --- 리소스 경로 (APP_ROOT 하위에서 고정된 위치) ---
ASSETS_DIR = APP_ROOT / "assets"
MODELS_DIR = ASSETS_DIR / "models"
UI_ASSETS_DIR = ASSETS_DIR / "ui"
SOUNDS_DIR = ASSETS_DIR / "sounds"

# --- 데이터 및 설정 경로 (APP_ROOT 하위에서 고정된 위치) ---
DATA_DIR = APP_ROOT / "data"

# 주요 설정 파일들
CRITERIA_JSON_PATH = DATA_DIR / "posture_definition_criteria.json"
CONFIG_JSON_PATH = DATA_DIR / "config.json"
BASELINE_JSON_PATH = DATA_DIR / "baseline.json"
SESSIONS_DB_PATH = DATA_DIR / "sessions.db"

def get_resource_path(relative_path: str) -> Path:
    """하위 호환성을 위한 함수: APP_ROOT 기준 상대 경로 반환"""
    return APP_ROOT / relative_path

def get_data_path(relative_path: str) -> Path:
    """하위 호환성을 위한 함수: APP_ROOT 기준 상대 경로 반환"""
    return APP_ROOT / relative_path
