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
        
        # 캐싱될 설정 변수들
        self.sensitivity = 0.1
        self.warning_anchor = 0.5
        self.warning_threshold = 0.45
        self.criteria = {}
        self.guards = {}
        
        # 상태 관리
        ema_alpha = 0.15
        if self.config:
            try: ema_alpha = self.config.get_posture_criteria().get("filters", {}).get("ema", {}).get("alpha", 0.15)
            except Exception: pass
        self.filter = EMAFilter(alpha=ema_alpha)
        
        self.refresh_settings()

    def refresh_settings(self):
        """설정값을 다시 읽어 내부 변수에 캐싱 (루프 오버헤드 방지)"""
        try:
            scoring_cfg = self.config.get_frame_scoring_config()
            self.warning_anchor = scoring_cfg.get("warning_anchor", 0.5)
            self.warning_threshold = self.config.get_state_machine_config().get("thresholds", {}).get("warning", 0.45)
            
            # 공통 감도 로드
            sensitivities = scoring_cfg.get("sensitivities", {})
            self.sensitivity = sensitivities.get(self.posture_type.value, 0.1)
            
            # 판정 기준 및 가드 로드
            self.criteria = self.config.get_posture_type_config(self.posture_type.value)
            self.guards = self.criteria.get("guards", {})
            
            logger.debug(f"{self.posture_type.value} 워커 설정 캐시 갱신 완료")
        except Exception as e:
            logger.error(f"{self.posture_type.value} 워커 설정 갱신 실패: {e}")

    def reset(self):
        """워커 상태 초기화 (EMA 필터 등)"""
        self.filter.reset()
        logger.debug(f"{self.posture_type.value} 워커 초기화됨")

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
    """거북목 판정 워커 (비율 편차[감도] 또는 화면 거리[절대기준] 통합)"""
    
    def __init__(self, config, baseline_manager):
        super().__init__(PostureType.FORWARD_HEAD, config, baseline_manager)
        self.dist_threshold = 45.0

    def refresh_settings(self):
        """설정 캐싱 및 거리 임계값 최신화"""
        super().refresh_settings()
        # dist_threshold가 외부에서 명시적으로 설정되지 않았을 때만 config에서 로드
        if not hasattr(self, "_dist_threshold_override"):
            try:
                cfg = self.config.get_posture_criteria().get("eye_monitoring", {})
                self.dist_threshold = float(cfg.get("distance_threshold_cm", 45.0))
            except Exception:
                self.dist_threshold = 45.0
        else:
            self.dist_threshold = self._dist_threshold_override

    def set_distance_threshold(self, val: float):
        """외부(UI/Settings)에서 거리 임계값 동적 설정"""
        self._dist_threshold_override = float(val)
        self.dist_threshold = float(val)
        logger.debug(f"ForwardHeadWorker: 거리 임계값 변경 -> {val}cm")

    def handle_indicators(self, indicators: PostureIndicators):
        # 1. 즉시 경고 플래그 확인 (2초간 근접 유지 시)
        if indicators.eye_close_warning:
            self._emit_result(0.9)
            return

        score_list = []

        # A. 화면 거리 기준 (절대 기준 - 점진적 상승)
        dist_cm = indicators.eye_screen_distance_cm
        if dist_cm is not None:
            if dist_cm <= self.dist_threshold:
                # 45cm(경고시작) -> 0.4, 20cm(위험) -> 1.0 식의 선형 매핑
                dist_score = 0.4 + (self.dist_threshold - dist_cm) / max(1e-6, self.dist_threshold - 20.0) * 0.6
                score_list.append(float(np.clip(dist_score, 0.0, 1.0)))

        # B. 비율 편차 기준 (상대 기준 - 감도 슬라이더 적용)
        if indicators.shoulder_width is not None and indicators.shoulder_width > 0:
            try:
                primary_th = self.criteria["primary_conditions"]["deviation"]["threshold"]
                expected_cheek = max(1e-6, self.baseline_manager.get_expected_cheek(indicators.shoulder_width))
                deviation = (indicators.cheek_distance - expected_cheek) / expected_cheek

                if deviation > primary_th and not self._is_guarded(indicators):
                    ratio_score = (deviation / max(0.01, self.sensitivity)) * self.warning_anchor
                    score_list.append(float(np.clip(ratio_score, 0.0, 1.0)))
            except Exception: pass

        final_score = max(score_list) if score_list else 0.0
        self._emit_result(final_score)

    def _is_guarded(self, indicators) -> bool:
        side_tilt = abs(indicators.eye_line_tilt) > self.guards.get("max_eye_tilt", 12.0)
        sh_tilt = abs(indicators.shoulder_tilt_deg or 0) > self.guards.get("max_shoulder_tilt", 10.0)
        eye_sym = indicators.eye_symmetry_ratio > self.guards.get("max_eye_symmetry_ratio", 0.12)
        
        sw_change = self.baseline_manager.calculate_change_percentage(indicators.shoulder_width, "shoulder_width")
        recline_guard = sw_change < self.guards.get("max_shoulder_decrease_pct", -15.0)
        
        return side_tilt or sh_tilt or eye_sym or recline_guard


class ReclineWorker(BaseJudgeWorker):
    """기댄 자세 판정 워커"""
    
    def __init__(self, config, baseline_manager):
        super().__init__(PostureType.RECLINE, config, baseline_manager)

    def handle_indicators(self, indicators: PostureIndicators):
        # [추가] 고개 숙임 감지 시 기댄 자세 판정 억제
        try:
            baseline_metrics = self.baseline_manager.get_baseline_metrics()
            if baseline_metrics and "face_pitch_deg" in baseline_metrics.metrics:
                base_pitch = baseline_metrics.metrics["face_pitch_deg"]
                pitch_diff = indicators.face_pitch_deg - base_pitch
                # 고개를 일정 수준(예: 10도) 이상 숙였다면 기댄 자세 판정을 억제
                if pitch_diff > 10.0:
                    self._emit_result(0.0)
                    return
        except Exception: pass

        has_sh = indicators.shoulder_width is not None and indicators.shoulder_width > 0
        proxy_val = indicators.shoulder_width if has_sh else indicators.eye_distance
        
        if not proxy_val or proxy_val <= 0:
            self._emit_result(0.0)
            return

        try:
            primary_th = self.criteria["primary_conditions"]["deviation"]["threshold"]
            expected_height = max(1e-6, self.baseline_manager.get_expected_height(proxy_val, is_shoulder=has_sh))
            deviation = (indicators.head_height - expected_height) / expected_height

            # [수정] Y축 높이 기반 알고리즘은 고개 돌림/기울임에 독립적이므로 가드 체크 제거
            if deviation >= primary_th:
                self._emit_result(0.0)
                return

            score = (abs(deviation) / max(0.01, self.sensitivity)) * self.warning_anchor
            self._emit_result(float(np.clip(score, 0.0, 1.0)))
        except Exception as e:
            logger.error(f"ReclineWorker 판정 실패: {e}")
            self._emit_result(0.0)

    def _is_guarded(self, indicators) -> bool:
        side_tilt = abs(indicators.eye_line_tilt) > self.guards.get("max_eye_tilt", 12.0)
        eye_sym = indicators.eye_symmetry_ratio > self.guards.get("max_eye_symmetry_ratio", 0.12)
        cheek_sym = indicators.cheek_symmetry_ratio > self.guards.get("max_cheek_symmetry_ratio", 0.12)
        chin_off = indicators.chin_alignment_offset > self.guards.get("max_chin_alignment_offset", 0.15)
        
        sh_tilt = False
        if indicators.shoulder_tilt_deg is not None:
            sh_tilt = abs(indicators.shoulder_tilt_deg) > self.guards.get("max_shoulder_tilt", 10.0)
        
        return side_tilt or eye_sym or cheek_sym or chin_off or sh_tilt


class ChinRestWorker(BaseJudgeWorker):
    """턱 괸 자세 판정 워커"""
    
    def __init__(self, config, baseline_manager):
        super().__init__(PostureType.CHIN_REST, config, baseline_manager)

    def handle_indicators(self, indicators: PostureIndicators):
        try:
            eye_th = self.criteria["primary_conditions"]["eye_line_tilt_deg"]["threshold"]
            hand_triggered = (indicators.hand_near_face or indicators.chin_occlusion > 0.25)
            if not hand_triggered:
                self._emit_result(0.0)
                return

            sens_factor = 0.1 / max(0.01, self.sensitivity)
            eye_score = self._normalize(abs(indicators.eye_line_tilt) / eye_th, 0, 2.0) * sens_factor
            
            w = self.config.get_frame_scoring_config().get("likelihood_weights", {}).get("chin_rest", {})
            w_eye = w.get("eye", 0.35)
            w_hand = w.get("hand", 0.3)
            w_sh = w.get("shoulder", 0.2) if indicators.shoulder_width is not None else 0.0
            
            total_w = w_eye + w_hand + w_sh
            likelihood = (w_eye * eye_score + w_hand * indicators.hand_face_score * sens_factor) / total_w if total_w > 0 else 0.0
            
            self._emit_result(likelihood)
        except Exception as e:
            logger.error(f"ChinRestWorker 판정 실패: {e}")
            self._emit_result(0.0)

    def _normalize(self, val, min_v, max_v):
        return float(np.clip((val - min_v) / (max_v - min_v), 0.0, 1.0)) if max_v > min_v else 0.0


class TurnedHeadWorker(BaseJudgeWorker):
    """고개 돌린 자세 판정 워커"""
    def __init__(self, config, baseline_manager):
        super().__init__(PostureType.TURNED_HEAD, config, baseline_manager)

    def handle_indicators(self, indicators: PostureIndicators):
        try:
            th_config = self.criteria.get("thresholds", {})
            eye_th = th_config.get("eye_symmetry", 0.4)
            cheek_th = th_config.get("cheek_symmetry", 0.4)
            
            sens_factor = 0.1 / max(0.01, self.sensitivity)
            eye_score = float(np.clip((indicators.eye_symmetry_ratio / eye_th) * sens_factor, 0, 1.0))
            cheek_score = float(np.clip((indicators.cheek_symmetry_ratio / cheek_th) * sens_factor, 0, 1.0))
            
            self._emit_result(0.5 * eye_score + 0.5 * cheek_score)
        except Exception:
            self._emit_result(0.0)


class SideTiltWorker(BaseJudgeWorker):
    """고개 기울인 자세 판정 워커"""
    def __init__(self, config, baseline_manager):
        super().__init__(PostureType.SIDE_TILT, config, baseline_manager)

    def handle_indicators(self, indicators: PostureIndicators):
        try:
            primary_th = self.criteria.get("primary_conditions", {}).get("eye_line_tilt_deg", {}).get("threshold", 10.0)
            tilt = abs(indicators.eye_line_tilt)
            if tilt < 3.0:
                self._emit_result(0.0)
                return
            
            sens_factor = 0.1 / max(0.01, self.sensitivity)
            self._emit_result(float(np.clip((tilt / primary_th) * sens_factor, 0, 1.0)))
        except Exception:
            self._emit_result(0.0)


class HeadDownWorker(BaseJudgeWorker):
    """고개 숙임 판정 워커 (Pitch)"""

    def __init__(self, config, baseline_manager):
        super().__init__(PostureType.HEAD_DOWN, config, baseline_manager)

    def handle_indicators(self, indicators: PostureIndicators):
        try:
            baseline_metrics = self.baseline_manager.get_baseline_metrics()
            if not baseline_metrics:
                self._emit_result(0.0)
                return
            
            baseline_pitch = baseline_metrics.metrics.get("face_pitch_deg", 0.0)
            current_pitch = indicators.face_pitch_deg

            # 고개를 숙이면 pitch가 증가하는 방향으로 계산됨 (dz/dy)
            # delta_pitch = current - baseline
            diff = current_pitch - baseline_pitch

            # 설정값 로드
            threshold = self.criteria.get("threshold", 15.0)
            
            # likelihood 계산: 임계값 근처에서 시작하여 선형 증가
            # 예: threshold=15일 때, 10도부터 시작하여 20도에서 1.0 도달 (sensitivities 반영 가능)
            sens_factor = 0.1 / max(0.01, self.sensitivity)
            
            margin = 5.0
            likelihood = float(np.clip(((diff - (threshold - margin)) / (2 * margin)) * sens_factor, 0.0, 1.0))
            
            # triggered는 필터링된 likelihood가 warning_threshold를 넘었을 때 _emit_result에서 결정됨
            # 하지만 원시 likelihood 계산 시 threshold를 넘으면 높은 값을 주도록 유도
            if diff >= threshold:
                likelihood = max(likelihood, self.warning_anchor + 0.1)

            self._emit_result(likelihood)
        except Exception as e:
            logger.error(f"HeadDownWorker 판정 실패: {e}")
            self._emit_result(0.0)


class PostureJudgeManager(QObject):
    """모든 판정 워커를 관리하고 스레드를 할당하는 매니저"""
    
    indicators_updated = pyqtSignal(object)
    all_results_ready = pyqtSignal(list)

    def __init__(self, config, baseline_manager):
        super().__init__()
        self.config = config
        self.baseline_manager = baseline_manager
        self.workers: Dict[str, BaseJudgeWorker] = {}
        self.threads: List[QThread] = []
        self.current_frame_results = {}
        self.expected_count = 0
        self._initialize_workers()

    def _initialize_workers(self):
        worker_classes = [
            ForwardHeadWorker, ReclineWorker, ChinRestWorker, 
            TurnedHeadWorker, SideTiltWorker, HeadDownWorker
        ]
        for cls in worker_classes:
            worker = cls(self.config, self.baseline_manager)
            thread = QThread()
            worker.moveToThread(thread)
            self.indicators_updated.connect(worker.handle_indicators)
            worker.result_ready.connect(self._collect_result)
            thread.finished.connect(worker.deleteLater)
            self.workers[worker.posture_type.value] = worker
            self.threads.append(thread)
            thread.start()
        self.expected_count = len(self.workers)
        logger.info(f"PostureJudgeManager: {self.expected_count}개의 판정 워커 기동 완료")

    def broadcast_indicators(self, indicators: PostureIndicators):
        self.current_frame_results = {}
        self.indicators_updated.emit(indicators)

    def update_sensitivities(self, settings_dict: Dict[str, float]):
        """감도 및 각종 임계값 통합 갱신"""
        for key, val in settings_dict.items():
            # 1. 거리 임계값 처리 (거북목 전용)
            if key == "forward_head_distance_threshold":
                worker = self.workers.get(PostureType.FORWARD_HEAD.value)
                if worker and hasattr(worker, "set_distance_threshold"):
                    worker.set_distance_threshold(val)
                continue
            
            # 2. 고개 숙임 임계값 처리
            if key == "head_down_threshold":
                worker = self.workers.get(PostureType.HEAD_DOWN.value)
                if worker:
                    # criteria 내부의 threshold 값을 직접 업데이트
                    worker.criteria["threshold"] = val
                continue
            
            # 3. 일반 감도 처리
            p_type = key.replace("_sensitivity", "") # xxx_sensitivity -> xxx
            if p_type in self.workers:
                self.workers[p_type].sensitivity = val
                self.workers[p_type].refresh_settings()
        logger.info("판정 워커 설정 캐시 갱신 완료")

    def reset_all_workers(self):
        """모든 워커의 내부 필터 및 상태 초기화"""
        for worker in self.workers.values():
            if hasattr(worker, "reset"):
                worker.reset()
        self.current_frame_results = {}
        logger.info("모든 판정 워커 상태 초기화 완료")

    def _collect_result(self, result: dict):
        p_type = result["posture_type"]
        self.current_frame_results[p_type] = result
        if len(self.current_frame_results) >= self.expected_count:
            results_list = list(self.current_frame_results.values())
            self.all_results_ready.emit(results_list)

    def stop_all(self):
        for thread in self.threads:
            thread.quit()
            thread.wait(500)
        logger.info("모든 판정 스레드 종료 완료")