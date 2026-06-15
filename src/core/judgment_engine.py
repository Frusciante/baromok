"""
판정 엔진 (Coordinator)

멀티스레드 워커들로부터 수집된 결과를 통합하여 상태 결정
"""

import numpy as np
from typing import Any, Dict, Optional, List
from dataclasses import dataclass
from enum import Enum

from src.config import ConfigManager
from src.core.indicator_calculator import PostureIndicators
from src.core.baseline_manager import BaselineManager
from src.utils.logger import get_logger
from src.utils.helpers import NormalizationHelper

logger = get_logger(__name__)


class PostureType(Enum):
    """자세 유형"""
    FORWARD_HEAD = "forward_head"  # 거북목
    RECLINE = "recline"  # 기댄 자세
    CHIN_REST = "chin_rest_estimated"  # 턱 괸 자세
    EYE_CLOSE = "eye_close"  # 화면과 눈 거리 가까움
    TURNED_HEAD = "turned_head"  # 고개 돌린 자세 (Yaw)
    SIDE_TILT = "side_tilt"  # 고개 기울인 자세 (Roll)


@dataclass
class PostureJudgmentResult:
    """단일 프레임 판정 결과 (v1.2: 다중 탐지 지원)"""
    active_postures: List[Dict[str, Any]]  # 감지된 모든 나쁜 자세 목록
    dominant_posture: Optional[str]  # 가장 심각한 자세 (하위 호환용)
    timestamp: float


class JudgmentEngine:
    """자세 판정 엔진 (조정자 역할)"""

    def __init__(self, config: ConfigManager, baseline_manager: BaselineManager):
        """
        초기화
        """
        self.config = config
        self.baseline_manager = baseline_manager
        self.normalization_helper = NormalizationHelper()

        # 자세별 지속 시간 추적
        self.posture_start_times: Dict[str, Optional[float]] = {
            pt.value: None for pt in PostureType
        }
        self.posture_active_durations: Dict[str, float] = {
            pt.value: 0.0 for pt in PostureType
        }

        self.last_confirmed_postures: List[str] = []
        
        # 하위 호환성을 위한 감도 필드
        self.forward_head_sensitivity = 0.10
        self.recline_sensitivity = 0.04
        
        logger.info("JudgmentEngine (Coordinator) 초기화 완료")

    def update_sensitivities(self, forward_head: float, recline: float):
        """사용자 정의 감도 업데이트 (워커들에게 전달될 기준값 저장)"""
        self.forward_head_sensitivity = forward_head
        self.recline_sensitivity = recline
        logger.info(f"조정자 감도 설정 업데이트: 거북목={forward_head:.3f}, 기댄자세={recline:.3f}")

    def process_worker_results(self, results: List[dict], current_timestamp: float) -> PostureJudgmentResult:
        """
        워커들로부터 수집된 다중 결과를 처리하여 통합된 결과 생성
        """
        # 1. 충돌 방지 우선순위 확인
        is_forward_head_triggered = False # (구 eye_close 포함)
        is_turned_head_triggered = False
        
        for res in results:
            if res["triggered"]:
                if res["posture_type"] == PostureType.FORWARD_HEAD.value:
                    is_forward_head_triggered = True
                elif res["posture_type"] == PostureType.TURNED_HEAD.value:
                    is_turned_head_triggered = True

        active_list = []
        dominant_p = None
        max_likelihood = -1.0

        for res in results:
            p_type = res["posture_type"]
            
            # [수정] 모든 억제 로직 제거 -> 다중 자세 동시 탐지 허용

            if res["triggered"]:
                active_list.append(res)
                if res["likelihood"] > max_likelihood:
                    max_likelihood = res["likelihood"]
                    dominant_p = p_type
            
            # 지속 시간 업데이트를 위해 개별 자세 누적 로직 수행
            self._update_posture_duration(res, current_timestamp)

        return PostureJudgmentResult(
            active_postures=active_list,
            dominant_posture=dominant_p,
            timestamp=current_timestamp
        )

    def _update_posture_duration(self, result: dict, current_timestamp: float):
        """개별 자세의 지속 시간을 독립적으로 업데이트"""
        p_type = result["posture_type"]
        if result["triggered"]:
            if self.posture_start_times[p_type] is None:
                self.posture_start_times[p_type] = current_timestamp
            self.posture_active_durations[p_type] = current_timestamp - self.posture_start_times[p_type]
        else:
            self.posture_start_times[p_type] = None
            self.posture_active_durations[p_type] = 0.0

    def get_all_confirmed_postures(self, current_timestamp: float) -> List[str]:
        """지속시간 조건을 만족한 모든 자세 목록 반환"""
        confirmed = []
        for pt in PostureType:
            p_key = pt.value
            criteria = self.config.get_posture_type_config(p_key)
            sustain_seconds = criteria.get("sustain_seconds", 2)
            
            if self.posture_active_durations.get(p_key, 0) >= sustain_seconds:
                confirmed.append(p_key)
        
        self.last_confirmed_postures = confirmed
        return confirmed

    def reset_history(self):
        """모든 상태 초기화"""
        for pt in PostureType:
            p_key = pt.value
            self.posture_start_times[p_key] = None
            self.posture_active_durations[p_key] = 0.0
        self.last_confirmed_postures = []
        logger.debug("JudgmentEngine 히스토리 초기화 완료")


def create_judgment_engine(config: ConfigManager, baseline_manager: BaselineManager) -> JudgmentEngine:
    """판정 엔진 생성"""
    return JudgmentEngine(config, baseline_manager)
