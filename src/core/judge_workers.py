"""
자세 판정 워커 및 매니저

각 자세별 독립적인 판정 로직을 멀티스레드로 수행
"""

from PyQt6.QtCore import QObject, pyqtSignal, QThread
from typing import Dict, List, Optional, Any
import numpy as np
import time

from src.core.indicator_calculator import PostureIndicators
from src.core.judgment_engine import PostureType
from src.utils.logger import get_logger
from src.utils.helpers import EMAFilter

logger = get_logger(__name__)


class BaseJudgeWorker(QObject):
    """자세 판정 워커 베이스 클래스"""
    
    # 판정 결과 발신 신호 (posture_type, likelihood, triggered)
    result_ready = pyqtSignal(dict)

    def __init__(self, posture_type: PostureType, config, baseline_manager):
        super().__init__()
        self.posture_type = posture_type
        self.config = config
        self.baseline_manager = baseline_manager
        
        # 상태 관리 (개별 워커가 자신의 히스토리 관리)
        ema_alpha = self.config.get_posture_criteria().get("filters", {}).get("ema", {}).get("alpha", 0.15)
        self.filter = EMAFilter(alpha=ema_alpha)
        
        # 감도 및 설정 로드
        scoring_cfg = self.config.get_frame_scoring_config()
        self.warning_anchor = scoring_cfg.get("warning_anchor", 0.5)
        self.warning_threshold = self.config.get_state_machine_config().get("thresholds", {}).get("warning", 0.45)
        
        # 자세별 감도
        sensitivities = scoring_cfg.get("sensitivities", {})
        self.sensitivity = sensitivities.get(self.posture_type.value, 0.1)

    def handle_indicators(self, indicators: PostureIndicators):
        """지표를 전달받아 판정 수행 (하위 클래스에서 구현)"""
        pass

    def _emit_result(self, likelihood: float):
        """결과 필터링 및 신호 발송"""
        smoothed_likelihood = self.filter.process(likelihood)
        triggered = smoothed_likelihood >= self.warning_threshold
        
        self.result_ready.emit({
            "posture_type": self.posture_type.value,
            "likelihood": float(smoothed_likelihood),
            "triggered": triggered,
            "timestamp": time.time()
        })


class ForwardHeadWorker(BaseJudgeWorker):
    """거북목 판정 워커"""
    
    def __init__(self, config, baseline_manager):
        super().__init__(PostureType.FORWARD_HEAD, config, baseline_manager)
        scoring_cfg = self.config.get_frame_scoring_config()
        self.sensitivity = scoring_cfg.get("sensitivities", {}).get("forward_head", 0.10)

    def handle_indicators(self, indicators: PostureIndicators):
        if indicators.shoulder_width is None or indicators.shoulder_width <= 0:
            self._emit_result(0.0)
            return

        try:
            criteria = self.config.get_posture_type_config(self.posture_type.value)
            primary_th = criteria["primary_conditions"]["deviation"]["threshold"]
            guards = criteria.get("guards", {})

            # 편차 계산 (어깨-광대 모델 사용)
            expected_cheek = max(1e-6, self.baseline_manager.get_expected_cheek(indicators.shoulder_width))
            deviation = (indicators.cheek_distance - expected_cheek) / expected_cheek

            # 1. 기본 방향 확인
            if deviation <= primary_th:
                self._emit_result(0.0)
                return
                
            # 2. 가드 로직 (기울임 등)
            if self._is_guarded(indicators, guards):
                self._emit_result(0.0)
                return

            # 3. 점수 계산
            score = (deviation / self.sensitivity) * self.warning_anchor
            self._emit_result(float(np.clip(score, 0.0, 1.0)))

        except Exception as e:
            logger.error(f"ForwardHeadWorker 판정 실패: {e}")
            self._emit_result(0.0)

    def _is_guarded(self, indicators, guards) -> bool:
        side_tilt = abs(indicators.eye_line_tilt) > guards.get("max_eye_tilt", 12.0)
        sh_tilt = abs(indicators.shoulder_tilt_deg or 0) > guards.get("max_shoulder_tilt", 10.0)
        eye_sym = indicators.eye_symmetry_ratio > guards.get("max_eye_symmetry_ratio", 0.12)
        
        # 기댄 자세 오판 방지
        sw_change = self.baseline_manager.calculate_change_percentage(indicators.shoulder_width, "shoulder_width")
        recline_guard = sw_change < guards.get("max_shoulder_decrease_pct", -15.0)
        
        return side_tilt or sh_tilt or eye_sym or recline_guard


class ReclineWorker(BaseJudgeWorker):
    """기댄 자세 판정 워커"""
    
    def __init__(self, config, baseline_manager):
        super().__init__(PostureType.RECLINE, config, baseline_manager)
        scoring_cfg = self.config.get_frame_scoring_config()
        self.sensitivity = scoring_cfg.get("sensitivities", {}).get("recline", 0.04)

    def handle_indicators(self, indicators: PostureIndicators):
        has_sh = indicators.shoulder_width is not None and indicators.shoulder_width > 0
        proxy_val = indicators.shoulder_width if has_sh else indicators.eye_distance
        
        if not proxy_val or proxy_val <= 0:
            self._emit_result(0.0)
            return

        try:
            criteria = self.config.get_posture_type_config(self.posture_type.value)
            primary_th = criteria["primary_conditions"]["deviation"]["threshold"]
            guards = criteria.get("guards", {})

            # 편차 계산 (높이 모델 사용)
            expected_height = max(1e-6, self.baseline_manager.get_expected_height(proxy_val, is_shoulder=has_sh))
            deviation = (indicators.head_height - expected_height) / expected_height

            # 1. 기본 방향 확인 (높이가 낮아지면 음수)
            if deviation >= primary_th:
                self._emit_result(0.0)
                return
                
            # 2. 가드 로직
            if self._is_guarded(indicators, guards):
                self._emit_result(0.0)
                return

            # 3. 점수 계산
            score = (abs(deviation) / self.sensitivity) * self.warning_anchor
            self._emit_result(float(np.clip(score, 0.0, 1.0)))

        except Exception as e:
            logger.error(f"ReclineWorker 판정 실패: {e}")
            self._emit_result(0.0)

    def _is_guarded(self, indicators, guards) -> bool:
        side_tilt = abs(indicators.eye_line_tilt) > guards.get("max_eye_tilt", 12.0)
        
        # 눈/광대 대칭 및 턱 정렬 확인 (v1.1 완화된 기준 적용)
        eye_sym = indicators.eye_symmetry_ratio > guards.get("max_eye_symmetry_ratio", 0.12)
        cheek_sym = indicators.cheek_symmetry_ratio > guards.get("max_cheek_symmetry_ratio", 0.12)
        chin_off = indicators.chin_alignment_offset > guards.get("max_chin_alignment_offset", 0.15)
        
        # 어깨가 있을 때만 어깨 기울기 체크
        sh_tilt = False
        if indicators.shoulder_tilt_deg is not None:
            sh_tilt = abs(indicators.shoulder_tilt_deg) > guards.get("max_shoulder_tilt", 10.0)
        
        return side_tilt or eye_sym or cheek_sym or chin_off or sh_tilt


class ChinRestWorker(BaseJudgeWorker):
    """턱 괸 자세 판정 워커"""
    
    def __init__(self, config, baseline_manager):
        super().__init__(PostureType.CHIN_REST, config, baseline_manager)
        # 턱 괸 자세는 감도 조절이 특별하므로 별도 저장 가능 (기본값 0.1)
        self.sensitivity = 0.1

    def handle_indicators(self, indicators: PostureIndicators):
        try:
            criteria = self.config.get_posture_type_config(self.posture_type.value)
            eye_th = criteria["primary_conditions"]["eye_line_tilt_deg"]["threshold"]
            
            # 손 트리거
            hand_triggered = (indicators.hand_near_face or indicators.chin_occlusion > 0.25)
            if not hand_triggered:
                self._emit_result(0.0)
                return

            # 상세 점수 산출 로직
            # 감도(sensitivity)가 낮을수록(민감) 점수가 더 잘 오르도록 설계
            # (기본 0.1 기준, sensitivity=0.05면 2배 민감)
            sens_factor = 0.1 / max(0.01, self.sensitivity)
            
            eye_score = self._normalize(abs(indicators.eye_line_tilt) / eye_th, 0, 2.0) * sens_factor
            
            w = self.config.get_frame_scoring_config().get("likelihood_weights", {}).get("chin_rest", {})
            has_sh = indicators.shoulder_width is not None
            
            w_eye = w.get("eye", 0.35)
            w_hand = w.get("hand", 0.3)
            w_sh = w.get("shoulder", 0.2) if has_sh else 0.0
            
            total_w = w_eye + w_hand + w_sh
            likelihood = (w_eye * eye_score + w_hand * indicators.hand_face_score * sens_factor) / total_w if total_w > 0 else 0.0
            
            self._emit_result(likelihood)
        except Exception as e:
            logger.error(f"ChinRestWorker 판정 실패: {e}")
            self._emit_result(0.0)

    def _normalize(self, val, min_v, max_v):
        return float(np.clip((val - min_v) / (max_v - min_v), 0.0, 1.0)) if max_v > min_v else 0.0


class EyeCloseWorker(BaseJudgeWorker):
    """눈-화면 거리 판정 워커"""
    def __init__(self, config, baseline_manager):
        super().__init__(PostureType.EYE_CLOSE, config, baseline_manager)
        self.sensitivity = 0.1 # 기본값

    def handle_indicators(self, indicators: PostureIndicators):
        if indicators.eye_close_warning:
            self._emit_result(1.0)
            return

        dist_cm = indicators.eye_screen_distance_cm
        if dist_cm is None:
            self._emit_result(0.0)
            return

        cfg = self.config.get_posture_criteria().get("eye_monitoring", {})
        threshold = float(cfg.get("distance_threshold_cm", 45.0))
        
        # 감도 반영: sensitivity가 작을수록(0.05) 더 먼 거리에서도 위험으로 판정
        # 가중치 앵커: 0.1 대비 비율
        sens_offset = (0.1 - self.sensitivity) * 100.0 # 0.1 -> 0, 0.05 -> +5cm
        effective_threshold = threshold + sens_offset
        
        severity = max(0.0, (effective_threshold - float(dist_cm)) / max(1e-6, effective_threshold))
        self._emit_result(float(np.clip(severity, 0.0, 1.0)))


class TurnedHeadWorker(BaseJudgeWorker):
    """고개 돌린 자세 판정 워커 (Yaw)"""
    def __init__(self, config, baseline_manager):
        super().__init__(PostureType.TURNED_HEAD, config, baseline_manager)
        self.sensitivity = 0.1

    def handle_indicators(self, indicators: PostureIndicators):
        try:
            criteria = self.config.get_posture_type_config(self.posture_type.value)
            th_config = criteria.get("thresholds", {})
            eye_th = th_config.get("eye_symmetry", 0.4)
            cheek_th = th_config.get("cheek_symmetry", 0.4)
            
            sens_factor = 0.1 / max(0.01, self.sensitivity)
            
            eye_score = float(np.clip((indicators.eye_symmetry_ratio / eye_th) * sens_factor, 0, 1.0))
            cheek_score = float(np.clip((indicators.cheek_symmetry_ratio / cheek_th) * sens_factor, 0, 1.0))
            
            self._emit_result(0.5 * eye_score + 0.5 * cheek_score)
        except Exception:
            self._emit_result(0.0)


class SideTiltWorker(BaseJudgeWorker):
    """고개 기울인 자세 판정 워커 (Roll)"""
    def __init__(self, config, baseline_manager):
        super().__init__(PostureType.SIDE_TILT, config, baseline_manager)
        self.sensitivity = 0.1

    def handle_indicators(self, indicators: PostureIndicators):
        try:
            criteria = self.config.get_posture_type_config(self.posture_type.value)
            primary_th = criteria.get("primary_conditions", {}).get("eye_line_tilt_deg", {}).get("threshold", 10.0)
            
            tilt = abs(indicators.eye_line_tilt)
            if tilt < 3.0:
                self._emit_result(0.0)
                return
            
            sens_factor = 0.1 / max(0.01, self.sensitivity)
            self._emit_result(float(np.clip((tilt / primary_th) * sens_factor, 0, 1.0)))
        except Exception:
            self._emit_result(0.0)


class PostureJudgeManager(QObject):
    """모든 판정 워커를 관리하고 스레드를 할당하는 매니저"""
    
    # 지표 전달 신호
    indicators_updated = pyqtSignal(object)
    # 통합된 판정 결과들을 모아서 발신
    all_results_ready = pyqtSignal(list)

    def __init__(self, config, baseline_manager):
        super().__init__()
        self.config = config
        self.baseline_manager = baseline_manager
        
        self.workers: Dict[str, BaseJudgeWorker] = {}
        self.threads: List[QThread] = []
        
        # 현재 프레임의 결과들을 임시 저장할 딕셔너리
        self.current_frame_results = {}
        self.expected_count = 0
        
        self._initialize_workers()

    def _initialize_workers(self):
        """각 자세별 워커 생성 및 스레드 배치"""
        worker_classes = [
            ForwardHeadWorker,
            ReclineWorker,
            ChinRestWorker,
            EyeCloseWorker,
            TurnedHeadWorker,
            SideTiltWorker
        ]
        
        for cls in worker_classes:
            worker = cls(self.config, self.baseline_manager)
            thread = QThread()
            worker.moveToThread(thread)
            
            # 지표 수신 연결
            self.indicators_updated.connect(worker.handle_indicators)
            # 결과 수집 연결
            worker.result_ready.connect(self._collect_result)
            
            # 종료 처리
            thread.finished.connect(worker.deleteLater)
            
            self.workers[worker.posture_type.value] = worker
            self.threads.append(thread)
            thread.start()
            
        self.expected_count = len(self.workers)
        logger.info(f"PostureJudgeManager: {self.expected_count}개의 판정 워커 기동 완료")

    def broadcast_indicators(self, indicators: PostureIndicators):
        """새로운 지표를 모든 워커에게 전달 (신호 발신)"""
        self.current_frame_results = {}
        self.indicators_updated.emit(indicators)

    def update_sensitivities(self, sensitivity_dict: Dict[str, float]):
        """개별 워커의 감도 설정을 실시간 갱신"""
        for p_type, val in sensitivity_dict.items():
            if p_type in self.workers:
                self.workers[p_type].sensitivity = val
        logger.info(f"판정 워커 감도 갱신 완료: {len(sensitivity_dict)}종")

    def _collect_result(self, result: dict):
        """워커로부터 결과를 수집하여 모두 모이면 통합 발송"""
        p_type = result["posture_type"]
        self.current_frame_results[p_type] = result
        
        if len(self.current_frame_results) >= self.expected_count:
            # 모든 워커의 결과가 모임 (순서 보장을 위해 리스트로 변환)
            results_list = list(self.current_frame_results.values())
            self.all_results_ready.emit(results_list)

    def stop_all(self):
        """모든 스레드 중지"""
        for thread in self.threads:
            thread.quit()
            thread.wait(500)
        logger.info("모든 판정 스레드 종료 완료")
