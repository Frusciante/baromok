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
        # 1. 확정된 나쁜 자세 목록 추출 (triggered=True)
        active_list = [res for res in results if res["triggered"]]

        # [강화] 상호 배제: 거북목과 기댄 자세는 공존할 수 없음.
        # 프레임 단위 결과에서도 거북목이 있으면 기댄 자세는 무조건 제거한다.
        is_fwd = any(res["posture_type"] == PostureType.FORWARD_HEAD.value for res in active_list)
        if is_fwd:
            active_list = [res for res in active_list if res["posture_type"] != PostureType.RECLINE.value]

        dominant_p = None
        max_likelihood = -1.0

        # 필터링된 목록을 기반으로 우세 자세 결정
        for res in active_list:
            if res["likelihood"] > max_likelihood:
                max_likelihood = res["likelihood"]
                dominant_p = res["posture_type"]

        # 모든 워커 결과에 대해 지속 시간 업데이트 수행 (결과 발산 방지를 위해 원본 results 사용 가능하나, 
        # 일관성을 위해 active_list에 남은 것들만 시간 누적되도록 유도)
        # 하지만 _update_posture_duration 내부에서 triggered 여부를 보므로, 
        # recline의 경우 여기서 triggered를 강제로 False로 만들거나 처리 로직을 수정해야 함.
        
        for res in results:
            p_type = res["posture_type"]
            # 거북목이 있는 경우 recline의 triggered를 강제로 False로 간주하여 시간 누적 방지
            if is_fwd and p_type == PostureType.RECLINE.value:
                res_to_process = res.copy()
                res_to_process["triggered"] = False
                self._update_posture_duration(res_to_process, current_timestamp)
            else:
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
        """지속시간 조건을 만족한 모든 자세 목록 반환 (v1.2: 상호 배제 로직 강화)"""
        confirmed = []
        for pt in PostureType:
            p_key = pt.value
            criteria = self.config.get_posture_type_config(p_key)
            sustain_seconds = criteria.get("sustain_seconds", 2)
            
            if self.posture_active_durations.get(p_key, 0) >= sustain_seconds:
                confirmed.append(p_key)
        
        # [강화] 상호 배제: 거북목과 기댄 자세는 공존할 수 없음.
        # 동시에 감지될 경우 '거북목'만 남기고 기댄 자세는 완전히 제거한다.
        if "forward_head" in confirmed and "recline" in confirmed:
            confirmed = [p for p in confirmed if p != "recline"]
            logger.info("상호 배제 적용: 거북목과 기댄 자세 동시 감지됨 -> 거북목만 유지")

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