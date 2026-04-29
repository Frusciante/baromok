"""
설정 관리 시스템

판정 기준 JSON 로더 및 애플리케이션 설정 관리
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import logging

logger = logging.getLogger(__name__)


class PostureSettings(BaseSettings):
    """자세 판정 기준 설정 (JSON 기반)"""
    
    @staticmethod
    def load_posture_criteria_json() -> Dict[str, Any]:
        """
        posture_definition_criteria.json 로더
        
        Returns:
            판정 기준 딕셔너리
            
        Raises:
            FileNotFoundError: JSON 파일을 찾을 수 없음
            json.JSONDecodeError: JSON 파싱 실패
            ValueError: 스키마 검증 실패
        """
        # src/config.py -> src/ -> baromok/ -> .github/
        criteria_path = Path(__file__).parent.parent / ".github" / "rules" / "operation" / "posture_definition_criteria.json"
        
        if not criteria_path.exists():
            raise FileNotFoundError(f"판정 기준 파일을 찾을 수 없습니다: {criteria_path}")
        
        try:
            with open(criteria_path, 'r', encoding='utf-8') as f:
                criteria = json.load(f)
            logger.info(f"판정 기준 파일 로드 완료: {criteria_path}")
            return criteria
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"JSON 파싱 실패: {e.msg} (line {e.lineno})", e.doc, e.pos)
        except Exception as e:
            raise ValueError(f"판정 기준 파일 로드 중 오류: {e}")


class ApplicationSettings(BaseSettings):
    """애플리케이션 설정 (사용자 커스터마이징 가능)"""
    
    # 앱 기본 정보
    app_name: str = "바로록"
    app_version: str = "0.1.0"
    
    # UI 설정
    window_width: int = 1280
    window_height: int = 800
    window_min_width: int = 800
    window_min_height: int = 600
    
    # 웹캠 설정
    camera_index: int = 0  # 기본 카메라
    camera_fps: int = 30
    camera_resolution_width: int = 1280
    camera_resolution_height: int = 720
    
    # 알림 설정
    enable_sound_alert: bool = True
    enable_popup_alert: bool = True
    popup_position: str = "top"  # "top" or "center"
    alert_sound_volume: int = 70  # 0~100
    alert_cooldown_seconds: float = 3.0  # 중복 알림 억제 시간
    
    # 자동 시작 설정
    auto_start_detection: bool = False
    
    # 로그 설정
    log_level: str = "INFO"
    log_file: Optional[str] = None  # None이면 콘솔만 출력
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class ConfigManager:
    """설정 관리자 (싱글톤 패턴)"""
    
    _instance: Optional['ConfigManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """초기화"""
        self.posture_criteria: Dict[str, Any] = {}
        self.app_settings: ApplicationSettings = ApplicationSettings()
        self._load_all()
    
    def _load_all(self):
        """모든 설정 로드"""
        try:
            # 판정 기준 로드
            self.posture_criteria = PostureSettings.load_posture_criteria_json()
            logger.info("모든 설정 로드 완료")
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
            raise
    
    def get_posture_criteria(self) -> Dict[str, Any]:
        """판정 기준 조회"""
        return self.posture_criteria
    
    def get_baseline_config(self) -> Dict[str, Any]:
        """Baseline 설정 조회"""
        try:
            return self.posture_criteria.get("baseline", {})
        except KeyError as e:
            raise ValueError(f"'baseline' 키를 찾을 수 없습니다: {e}")
    
    def get_posture_type_config(self, posture_type: str) -> Dict[str, Any]:
        """특정 자세 유형의 설정 조회"""
        try:
            posture_types = self.posture_criteria.get("posture_types", {})
            if posture_type not in posture_types:
                raise KeyError(f"미알려진 자세 유형: {posture_type}")
            return posture_types[posture_type]
        except KeyError as e:
            raise ValueError(f"자세 유형 설정 조회 실패: {e}")
    
    def get_event_judgment_config(self) -> Dict[str, Any]:
        """이벤트 판정 설정 조회"""
        try:
            return self.posture_criteria.get("event_judgment", {})
        except KeyError as e:
            raise ValueError(f"'event_judgment' 키를 찾을 수 없습니다: {e}")
    
    def get_state_machine_config(self) -> Dict[str, Any]:
        """상태 머신 설정 조회"""
        try:
            global_rules = self.posture_criteria.get("global_rules", {})
            return global_rules.get("state_machine", {})
        except KeyError as e:
            raise ValueError(f"'state_machine' 키를 찾을 수 없습니다: {e}")
    
    def get_frame_scoring_config(self) -> Dict[str, Any]:
        """프레임 점수 설정 조회"""
        try:
            return self.posture_criteria.get("frame_scoring", {})
        except KeyError as e:
            raise ValueError(f"'frame_scoring' 키를 찾을 수 없습니다: {e}")
    
    def get_app_setting(self, key: str, default: Any = None) -> Any:
        """애플리케이션 설정 조회"""
        return getattr(self.app_settings, key, default)
    
    def update_app_setting(self, key: str, value: Any):
        """애플리케이션 설정 업데이트"""
        if hasattr(self.app_settings, key):
            setattr(self.app_settings, key, value)
            logger.info(f"설정 업데이트: {key} = {value}")
        else:
            raise AttributeError(f"미알려진 설정 키: {key}")
    
    def save_app_settings_to_env(self, env_file: str = ".env"):
        """애플리케이션 설정을 .env 파일로 저장 (선택)"""
        try:
            with open(env_file, 'w', encoding='utf-8') as f:
                for key, value in self.app_settings.dict().items():
                    f.write(f"{key.upper()}={value}\n")
            logger.info(f"애플리케이션 설정 저장 완료: {env_file}")
        except Exception as e:
            logger.error(f"애플리케이션 설정 저장 실패: {e}")
            raise


# 글로벌 설정 관리자 인스턴스
config_manager = ConfigManager()


def get_config() -> ConfigManager:
    """설정 관리자 조회 (유틸 함수)"""
    return config_manager
