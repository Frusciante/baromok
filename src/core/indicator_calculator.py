"""
자세 지표 계산기

랜드마크로부터 자세 관련 지표를 계산 (거리, 비율, 각도 등)
"""
import numpy as np
import math
import time
from dataclasses import dataclass
from typing import Tuple, Dict, Optional, List
from src.utils.helpers import GeometryHelper, NormalizationHelper, EMAFilter
from src.utils.logger import get_logger
from collections import deque

from src.config import ConfigManager

logger = get_logger(__name__)


@dataclass
class PostureIndicators:
    """자세 지표 데이터"""
    cheek_distance: float  # 양쪽 광대 거리
    eye_distance: float  # 양쪽 눈 거리
    face_vertical_length: float # 얼굴 세로 길이
    head_height: float  # 머리 높이 (1.0 - Y중앙값)
    shoulder_width: Optional[float]  # 양쪽 어깨 거리
    shoulder_tilt_deg: Optional[float]  # 어깨 기울기 (도)
    neck_offset: Optional[float]  # 목-어깨 정렬 오차
    eye_line_tilt: float  # 눈 수평선 기울기 (도)
    hand_near_face: bool  # 손이 얼굴 근처인가
    chin_occlusion: float  # 턱 가림 정도 (0~1)
    eye_screen_distance_cm: Optional[float] = None # 홍채 기반 실제 거리
    eye_close_warning: bool = False
    hand_face_score: float = 0.0
    eye_symmetry_ratio: float = 0.0
    cheek_symmetry_ratio: float = 0.0
    face_shoulder_ratio: float = 0.0
    eye_height: float = 0.0
    shoulder_height: float = 0.0
    chin_alignment_offset: float = 0.0
    timestamp: float = 0.0
    step_index: int = 0


class IndicatorCalculator:
    """자세 지표 계산기"""
    
    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config
        self.geometry_helper = GeometryHelper()
        self.normalization_helper = NormalizationHelper()
        self._shoulder_tilt_history = deque(maxlen=5)
        
        # 설정 캐시 변수들
        self._ema_alpha = 0.15
        self._iris_diameter_mm = 11.5
        self._camera_hfov_deg = 60.0
        self._eye_distance_threshold_cm = 45.0
        self._eye_sustain_seconds = 2.0
        self._camera_frame_width = 1280
        
        self.ema_filters = {}
        self.refresh_settings()
        
        self._eye_close_start_time: Optional[float] = None
        logger.info(f"IndicatorCalculator 초기화 완료 (캐싱 활성)")

    def refresh_settings(self):
        """설정 파일에서 값을 읽어 내부 변수에 캐싱 (루프 오버헤드 방지)"""
        if not self.config:
            return

        try:
            criteria = self.config.get_posture_criteria()
            # EMA Alpha
            self._ema_alpha = criteria.get("filters", {}).get("indicator_ema", {}).get("alpha", 0.15)
            
            # 홍채 모니터링 설정
            eye_cfg = criteria.get("eye_monitoring", {})
            self._iris_diameter_mm = float(eye_cfg.get("iris_diameter_mm", 11.5))
            self._camera_hfov_deg = float(eye_cfg.get("camera_horizontal_fov_deg", 60.0))
            
            # dist_threshold가 외부에서 명시적으로 설정되지 않았을 때만 config에서 로드
            if not hasattr(self, "_eye_distance_threshold_override"):
                self._eye_distance_threshold_cm = float(eye_cfg.get("distance_threshold_cm", 45.0))
            else:
                self._eye_distance_threshold_cm = self._eye_distance_threshold_override

            self._eye_sustain_seconds = float(eye_cfg.get("sustain_seconds", 2.0))
            
            # 카메라 설정 (CameraWorker와 동일한 설정 키 사용 보장)
            self._camera_frame_width = int(self.config.get_app_setting('camera_resolution_width', 1280))
            
            # 필터 갱신 (이미 존재하면 alpha만 업데이트, 없으면 생성)
            filter_keys = [
                'cheek_distance', 'eye_distance', 'face_vertical_length', 'head_height',
                'shoulder_width', 'shoulder_tilt_deg', 'neck_offset', 'eye_line_tilt',
                'chin_occlusion', 'hand_face_score', 'shoulder_height', 'eye_height'
            ]
            for key in filter_keys:
                if key in self.ema_filters:
                    self.ema_filters[key].alpha = self._ema_alpha
                else:
                    self.ema_filters[key] = EMAFilter(alpha=self._ema_alpha)
                    
            logger.debug("IndicatorCalculator 설정 캐시 갱신 완료")
        except Exception as e:
            logger.error(f"IndicatorCalculator 설정 갱신 실패: {e}")

    def set_eye_distance_threshold(self, val: float):
        """외부에서 거리 임계값 동적 설정"""
        self._eye_distance_threshold_override = float(val)
        self._eye_distance_threshold_cm = float(val)
        logger.debug(f"IndicatorCalculator: 거리 임계값 변경 -> {val}cm")

    def calculate_cheek_distance(self, left_cheek, right_cheek) -> float:
        if left_cheek is None or right_cheek is None: return 0.0
        return float(np.clip(self.geometry_helper.calculate_distance(np.array(left_cheek), np.array(right_cheek)), 0.0, 1.0))
    
    def calculate_eye_distance(self, left_eye, right_eye) -> float:
        if left_eye is None or right_eye is None: return 0.0
        return float(np.clip(self.geometry_helper.calculate_distance(np.array(left_eye), np.array(right_eye)), 0.0, 1.0))

    def calculate_head_height(self, left_eye, right_eye, left_cheek, right_cheek) -> float:
        """머리 높이 계산 (1.0 - Y좌표 중앙값)"""
        pts = [p for p in [left_eye, right_eye, left_cheek, right_cheek] if p is not None]
        if not pts: return 0.0
        avg_y = sum(p[1] for p in pts) / len(pts)
        return float(np.clip(1.0 - avg_y, 0.0, 1.0))

    def calculate_eye_height(self, left_eye, right_eye) -> float:
        """눈 높이 계산 (1.0 - Y좌표 평균)"""
        if left_eye is None or right_eye is None: return 0.0
        avg_y = (left_eye[1] + right_eye[1]) / 2.0
        return float(np.clip(1.0 - avg_y, 0.0, 1.0))

    def calculate_face_vertical_length(self, left_eye, right_eye, chin) -> float:
        if left_eye is None or right_eye is None or chin is None: return 0.0
        eye_mid = np.array([(left_eye[0] + right_eye[0]) / 2.0, (left_eye[1] + right_eye[1]) / 2.0])
        return float(np.clip(self.geometry_helper.calculate_distance(eye_mid, np.array(chin)), 0.0, 1.0))
    
    def calculate_shoulder_width(self, left_shoulder, right_shoulder) -> float:
        if left_shoulder is None or right_shoulder is None: return 0.0
        return float(np.clip(self.geometry_helper.calculate_distance(np.array(left_shoulder), np.array(right_shoulder)), 0.0, 1.0))
    
    def calculate_shoulder_height(self, left_shoulder, right_shoulder) -> float:
        """어깨 높이 계산 (1.0 - Y좌표 평균)"""
        if left_shoulder is None or right_shoulder is None: return 0.0
        avg_y = (left_shoulder[1] + right_shoulder[1]) / 2.0
        return float(np.clip(1.0 - avg_y, 0.0, 1.0))

    def calculate_shoulder_tilt_degree(self, left_shoulder, right_shoulder) -> float:
        if left_shoulder is None or right_shoulder is None: return 0.0
        h_diff = right_shoulder[1] - left_shoulder[1]
        w_diff = right_shoulder[0] - left_shoulder[0]
        if abs(w_diff) < 1e-3: return 0.0
        return float(np.clip(np.degrees(np.arctan2(-h_diff, w_diff)), -90.0, 90.0))
    
    def calculate_neck_offset(self, face_center, left_shoulder, right_shoulder) -> float:
        if face_center is None or left_shoulder is None or right_shoulder is None: return 0.0
        sh_center = np.array([(left_shoulder[0] + right_shoulder[0]) / 2.0, (left_shoulder[1] + right_shoulder[1]) / 2.0])
        return float(np.clip(self.geometry_helper.calculate_distance(np.array(face_center), sh_center), 0.0, 1.0))
    
    def calculate_eye_line_tilt(self, left_eye, right_eye) -> float:
        if left_eye is None or right_eye is None: return 0.0
        return float(np.clip(self.geometry_helper.calculate_angle_with_horizontal(np.array(left_eye), np.array(right_eye)), -90.0, 90.0))
    
    def calculate_chin_occlusion(self, chin_points, landmarks_dict) -> float:
        if not chin_points or not landmarks_dict: return 0.0
        threshold = 0.1
        if self.config:
            try: threshold = self.config.get_posture_criteria().get("chin_rest_estimated", {}).get("primary_conditions", {}).get("chin_occlusion", {}).get("threshold", 0.1)
            except Exception: pass
        score = 0.0
        for side in ['right_hand_tips', 'left_hand_tips']:
            for hand_pt in (landmarks_dict.get(side) or []):
                if hand_pt is None: continue
                hand = np.array(hand_pt[:2])
                for chin_pt in chin_points:
                    if chin_pt is None: continue
                    dist = self.geometry_helper.calculate_distance(np.array(chin_pt), hand)
                    if dist < threshold: score += (1.0 - dist / threshold) * 0.1
        return float(np.clip(score, 0.0, 1.0))
    
    def calculate_hand_near_face(self, landmarks_dict, face_center, threshold=None) -> bool:
        if face_center is None: return False
        if threshold is None:
            threshold = 0.15
            if self.config:
                try: threshold = self.config.get_posture_criteria().get("chin_rest_estimated", {}).get("primary_conditions", {}).get("hand_near_face", {}).get("threshold", 0.15)
                except Exception: pass
        face = np.array(face_center)
        for side in ['right_hand_tips', 'left_hand_tips']:
            for hand_pt in (landmarks_dict.get(side) or []):
                if hand_pt is None: continue
                if self.geometry_helper.calculate_distance(np.array(hand_pt[:2]), face) < threshold: return True
        return False
    
    def calculate_hand_near_score(self, landmarks_dict, face_center) -> float:
        if face_center is None: return 0.0
        min_dist = 1.0
        face = np.array(face_center)
        found = False
        for side in ['right_hand_tips', 'left_hand_tips']:
            for hand_pt in (landmarks_dict.get(side) or []):
                if hand_pt is None: continue
                min_dist = min(min_dist, self.geometry_helper.calculate_distance(np.array(hand_pt[:2]), face))
                found = True
        if not found: return 0.0
        score = 1.0 - (min_dist - 0.1) / (0.3 - 0.1)
        return float(np.clip(score, 0.0, 1.0))

    def calculate_all_indicators(
        self,
        landmarks: Dict[str, any],
        timestamp: float = 0.0,
        low_latency: bool = False,
        baseline_mode: bool = False
    ) -> Optional[PostureIndicators]:
        """모든 자세 지표 계산 (캐싱된 설정 사용)"""
        if (landmarks.get('left_cheek') is None or landmarks.get('right_cheek') is None):
            return None

        try:
            # 저지연 모드 시에만 alpha 임시 조정
            if low_latency:
                for f in self.ema_filters.values(): f.alpha = 0.5
            else:
                for f in self.ema_filters.values(): f.alpha = self._ema_alpha

            # 1. 얼굴 지표
            cheek_dist_raw = self.calculate_cheek_distance(landmarks['left_cheek'], landmarks['right_cheek'])
            eye_dist_raw = self.calculate_eye_distance(landmarks.get('left_eye'), landmarks.get('right_eye'))
            head_height_raw = self.calculate_head_height(
                landmarks.get('left_eye'), landmarks.get('right_eye'),
                landmarks.get('left_cheek'), landmarks.get('right_cheek')
            )
            eye_h_raw = self.calculate_eye_height(landmarks.get('left_eye'), landmarks.get('right_eye'))
            
            chin_pt = landmarks.get('chin_points')[0] if landmarks.get('chin_points') else None
            face_v_len_raw = self.calculate_face_vertical_length(landmarks.get('left_eye'), landmarks.get('right_eye'), chin_pt)
            eye_tilt_raw = self.calculate_eye_line_tilt(landmarks.get('left_eye'), landmarks.get('right_eye'))
            
            # 대칭성
            eye_sym = 0.0; cheek_sym = 0.0; chin_offset = 0.0
            face_center = landmarks.get('face_center')
            if face_center:
                if landmarks.get('left_eye') and landmarks.get('right_eye'):
                    l_d = abs(face_center[0] - landmarks['left_eye'][0])
                    r_d = abs(face_center[0] - landmarks['right_eye'][0])
                    if (l_d + r_d) > 0: eye_sym = abs(l_d - r_d) / (l_d + r_d)
                if landmarks.get('left_cheek') and landmarks.get('right_cheek'):
                    l_c = abs(face_center[0] - landmarks['left_cheek'][0])
                    r_c = abs(face_center[0] - landmarks['right_cheek'][0])
                    if (l_c + r_c) > 0: cheek_sym = abs(l_c - r_c) / (l_c + r_c)
                if landmarks.get('chin_points'): chin_offset = abs(face_center[0] - landmarks['chin_points'][0][0])

            # 2. 어깨 지표
            has_sh = (landmarks.get('left_shoulder') is not None and landmarks.get('right_shoulder') is not None)
            sh_w_raw = self.calculate_shoulder_width(landmarks['left_shoulder'], landmarks['right_shoulder']) if has_sh else None
            sh_h_raw = self.calculate_shoulder_height(landmarks['left_shoulder'], landmarks['right_shoulder']) if has_sh else 0.0
            sh_tilt_raw = self.calculate_shoulder_tilt_degree(landmarks['left_shoulder'], landmarks['right_shoulder']) if has_sh else None
            neck_off_raw = self.calculate_neck_offset(face_center, landmarks['left_shoulder'], landmarks['right_shoulder']) if has_sh and face_center else None

            # 필터링
            if baseline_mode:
                cheek_dist = cheek_dist_raw; eye_dist = eye_dist_raw; face_v_len = face_v_len_raw; eye_tilt = eye_tilt_raw
                head_height = head_height_raw; eye_h = eye_h_raw; sh_h = sh_h_raw
                sh_w = sh_w_raw; sh_tilt = sh_tilt_raw; neck_off = neck_off_raw
            else:
                cheek_dist = self.ema_filters['cheek_distance'].process(cheek_dist_raw)
                eye_dist = self.ema_filters['eye_distance'].process(eye_dist_raw)
                head_height = self.ema_filters['head_height'].process(head_height_raw)
                eye_h = self.ema_filters['eye_height'].process(eye_h_raw)
                face_v_len = self.ema_filters['face_vertical_length'].process(face_v_len_raw)
                eye_tilt = self.ema_filters['eye_line_tilt'].process(eye_tilt_raw)
                if has_sh:
                    sh_w = self.ema_filters['shoulder_width'].process(sh_w_raw)
                    sh_h = self.ema_filters['shoulder_height'].process(sh_h_raw)
                    sh_tilt = self.ema_filters['shoulder_tilt_deg'].process(sh_tilt_raw)
                    neck_off = self.ema_filters['neck_offset'].process(neck_off_raw)
                    try:
                        self._shoulder_tilt_history.append(sh_tilt)
                        if len(self._shoulder_tilt_history) > 0: sh_tilt = float(np.median(list(self._shoulder_tilt_history)))
                    except Exception: pass
                else:
                    sh_w = None; sh_h = 0.0; sh_tilt = None; neck_off = None

            # 홍채 거리 (비교적 정확한 물리 거리 산출)
            eye_screen_cm = None; eye_warning = False
            try:
                l_px = landmarks.get('left_iris_diameter_px_raw') or landmarks.get('left_iris_diameter_px')
                r_px = landmarks.get('right_iris_diameter_px_raw') or landmarks.get('right_iris_diameter_px')
                if l_px or r_px:
                    hfov_rad = math.radians(self._camera_hfov_deg)
                    f_px = float(self._camera_frame_width) / (2.0 * math.tan(hfov_rad / 2.0))
                    px_vals = [px for px in (l_px, r_px) if px and px > 0]
                    if px_vals:
                        z_cm_vals = [((self._iris_diameter_mm * f_px) / float(px)) / 10.0 for px in px_vals]
                        # [복구] 사용자 요청에 따라 20cm 오프셋 재적용
                        eye_screen_cm = max(0.0, float(min(z_cm_vals)) - 20.0)
                        now = timestamp if timestamp > 0 else time.time()
                        if eye_screen_cm <= self._eye_distance_threshold_cm:
                            if self._eye_close_start_time is None: self._eye_close_start_time = now
                            if now - self._eye_close_start_time >= self._eye_sustain_seconds: eye_warning = True
                        else: self._eye_close_start_time = None
            except Exception: pass

            # 손 상호작용
            chin_occ_raw = self.calculate_chin_occlusion(landmarks.get('chin_points', []), landmarks)
            near_score = self.calculate_hand_near_score(landmarks, face_center)
            
            # 가중치 또는 기본값 사용
            h_f_score_raw = 0.5 * near_score + 0.5 * chin_occ_raw
            
            if baseline_mode: h_f_score = h_f_score_raw; chin_occ = chin_occ_raw
            else:
                h_f_score = self.ema_filters['hand_face_score'].process(h_f_score_raw)
                chin_occ = self.ema_filters['chin_occlusion'].process(chin_occ_raw)

            # face_shoulder_ratio 계산 (cheek_distance / shoulder_width)
            fs_ratio = 0.0
            if cheek_dist and sh_w and sh_w > 0:
                fs_ratio = float(cheek_dist / sh_w)

            return PostureIndicators(
                cheek_distance=cheek_dist, eye_distance=eye_dist, face_vertical_length=face_v_len,
                head_height=head_height,
                shoulder_width=sh_w, shoulder_tilt_deg=sh_tilt, neck_offset=neck_off,
                eye_line_tilt=eye_tilt, hand_near_face=self.calculate_hand_near_face(landmarks, face_center),
                chin_occlusion=chin_occ, eye_screen_distance_cm=eye_screen_cm, eye_close_warning=eye_warning,
                hand_face_score=h_f_score, eye_symmetry_ratio=eye_sym, cheek_symmetry_ratio=cheek_sym,
                face_shoulder_ratio=fs_ratio,
                eye_height=eye_h,
                shoulder_height=sh_h,
                chin_alignment_offset=chin_offset, timestamp=timestamp
            )
        except Exception as e:
            logger.error(f"지표 계산 최종 단계 실패: {e}", exc_info=True)
            return None


def create_indicator_calculator(config: Optional[ConfigManager] = None) -> IndicatorCalculator:
    return IndicatorCalculator(config)
