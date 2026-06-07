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
            FileNotFoundError: JSON 파일을 찾을 수 없습니다
            json.JSONDecodeError: JSON 파싱 실패
            ValueError: 스키마 검증 실패
        """
        # src/config.py -> src/ -> baromok/ -> .github/
        criteria_path = (
            Path(__file__).parent.parent
            / ".github"
            / "rules"
            / "operation"
            / "posture_definition_criteria.json"
        )

        if not criteria_path.exists():
            raise FileNotFoundError(
                f"판정 기준 파일을 찾을 수 없습니다: {criteria_path}"
            )

        try:
            with open(criteria_path, "r", encoding="utf-8") as f:
                criteria = json.load(f)
            logger.info(f"판정 기준 파일 로드 완료: {criteria_path}")
            return criteria
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"JSON 파싱 실패: {e.msg} (line {e.lineno})", e.doc, e.pos
            )
        except Exception as e:
            raise ValueError(f"판정 기준 파일 로드 중 오류: {e}")


class ApplicationSettings(BaseSettings):
    """애플리케이션 설정 (사용자 커스터마이징 가능)"""

    # 앱 기본 정보
    app_name: str = "바로목"
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

    _instance: Optional["ConfigManager"] = None

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

    def get_mediapipe_config(self) -> Dict[str, Any]:
        """MediaPipe 설정 조회"""
        return self.posture_criteria.get("mediapipe", {})

    def get_filters_config(self) -> Dict[str, Any]:
        """필터 설정 조회

        posture_definition_criteria.json 내의 `filters` 항목을 반환합니다.
        """
        return self.posture_criteria.get("filters", {})

    def get_baseline_config(self) -> Dict[str, Any]:
        """Baseline 설정 조회"""
        return self.posture_criteria.get("baseline", {})

    def get_posture_type_config(self, posture_type: str) -> Dict[str, Any]:
        """특정 자세 유형의 설정 조회"""
        posture_types = self.posture_criteria.get("posture_types", {})
        if posture_type not in posture_types:
            raise ValueError(f"미알려진 자세 유형: {posture_type}")
        return posture_types[posture_type]

    def get_event_judgment_config(self) -> Dict[str, Any]:
        """이벤트 판정 설정 조회"""
        return self.posture_criteria.get("event_judgment", {})

    def get_state_machine_config(self) -> Dict[str, Any]:
        """상태 머신 설정 조회"""
        global_rules = self.posture_criteria.get("global_rules", {})
        return global_rules.get("state_machine", {})

    def get_frame_scoring_config(self) -> Dict[str, Any]:
        """프레임 점수 설정 조회"""
        return self.posture_criteria.get("frame_scoring", {})

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
            with open(env_file, "w", encoding="utf-8") as f:
                for key, value in self.app_settings.dict().items():
                    f.write(f"{key.upper()}={value}\n")
            logger.info(f"애플리케이션 설정 저장 완료: {env_file}")
        except Exception as e:
            logger.error(f"애플리케이션 설정 저장 실패: {e}")
            raise


# 글로벌 설정 관리자 인스턴스 (지연 초기화)
_config_manager: Optional["ConfigManager"] = None


def get_config() -> "ConfigManager":
    """설정 관리자 조회 (유틸 함수) — 첫 호출 시 초기화"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


# 하위 호환성을 위한 별칭 (기존 코드에서 config_manager를 직접 참조하는 경우)
config_manager = get_config()


# ============================================================================
# 사용자 UI 설정 (SettingsScreen용)
# ============================================================================


from dataclasses import dataclass, asdict, fields


@dataclass
class SettingsConfig:
    """사용자 커스터마이징 가능한 UI 설정"""

    # 알림 설정
    notification_enabled: bool = True
    notification_interval: int = 30  # 초

    # 소리 설정
    sound_enabled: bool = True
    sound_volume: int = 70  # 0-100

    # 팝업 설정
    popup_position: str = "center"  # "center" | "top"
    popup_auto_close: bool = True
    popup_auto_close_time: int = 5  # 초

    # 자동 시작
    auto_start_detection: bool = False

    # 감도 설정 (기본값은 None이며 로드 시 JSON에서 가져옴)
    forward_head_sensitivity: Optional[float] = None
    recline_sensitivity: Optional[float] = None

    # 자세 맞춤 기반 권장(최신 오차 기반) 감도 저장 (초기화 시 사용)
    recommended_forward_head: Optional[float] = None
    recommended_recline: Optional[float] = None

    @classmethod
    def load_from_json(cls, file_path: str, config_manager: Optional[ConfigManager] = None) -> "SettingsConfig":
        """JSON 파일에서 설정 로드"""
        def _apply_sensitivity_defaults(instance: "SettingsConfig") -> "SettingsConfig":
            if config_manager:
                scoring_config = config_manager.get_frame_scoring_config()
                sensitivities = scoring_config.get("sensitivities", {})

                if instance.forward_head_sensitivity is None:
                    instance.forward_head_sensitivity = sensitivities.get("forward_head", 0.075)
                if instance.recline_sensitivity is None:
                    instance.recline_sensitivity = sensitivities.get("recline", 0.01)
                if instance.recommended_forward_head is None:
                    instance.recommended_forward_head = sensitivities.get("forward_head", 0.075)
                if instance.recommended_recline is None:
                    instance.recommended_recline = sensitivities.get("recline", 0.01)
            else:
                if instance.forward_head_sensitivity is None:
                    instance.forward_head_sensitivity = 0.075
                if instance.recline_sensitivity is None:
                    instance.recline_sensitivity = 0.01
                if instance.recommended_forward_head is None:
                    instance.recommended_forward_head = instance.forward_head_sensitivity
                if instance.recommended_recline is None:
                    instance.recommended_recline = instance.recline_sensitivity
            return instance

        try:
            instance = cls()
            
            # JSON 파일 로드
            data = {}
            if Path(file_path).exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
            # 필드 채우기
            field_names = {f.name for f in fields(cls)}
            for k, v in data.items():
                if k in field_names:
                    setattr(instance, k, v)
            
            return _apply_sensitivity_defaults(instance)
            
        except Exception as e:
            logger.warning("설정 파일 로드 실패, 기본값 사용: %s", e)
            return _apply_sensitivity_defaults(cls())

    def save_to_json(self, file_path: str) -> None:
        """JSON 파일에 설정 저장"""
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
            logger.info("설정 저장 완료: %s", file_path)
        except Exception as e:
            logger.error("설정 저장 실패: %s", e)

    def reset_to_defaults(self):
        """기본값으로 초기화 (최신 자세 맞춤 권장값 사용)"""
        if self.recommended_forward_head is not None:
            self.forward_head_sensitivity = self.recommended_forward_head
        if self.recommended_recline is not None:
            self.recline_sensitivity = self.recommended_recline
            
        logger.info(f"민감도 설정이 권장값으로 초기화되었습니다: Fwd={self.forward_head_sensitivity:.3f}, Rec={self.recline_sensitivity:.3f}")
