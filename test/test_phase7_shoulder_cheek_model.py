"""
Phase 7: Shoulder-Cheek Quadratic Model 자동화 테스트 (개선판)
"""

import logging
import time
import numpy as np
from pathlib import Path

from src.config import ConfigManager
from src.core.indicator_calculator import IndicatorCalculator, PostureIndicators
from src.core.baseline_manager import BaselineManager
from src.core.judgment_engine import JudgmentEngine

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def test_1_ransac_cheek_model():
    """Test 1: 어깨 너비(x)에 따른 광대 거리(y) RANSAC 적합 검증"""
    try:
        config = ConfigManager()
        bm = BaselineManager(config, data_dir="data_test")
        bm.minimum_valid_frame_count = 10
        bm.start_baseline_collection()
        
        # 2차 함수 데이터 생성: y = 0.5x^2 + 0.2x + 0.05
        for i in range(15):
            x = 0.2 + i * 0.02
            y_clean = 0.5 * (x**2) + 0.2 * x + 0.05
            # 노이즈 및 이상치 주입
            y = y_clean + (np.random.normal(0, 0.0001) if i % 5 != 0 else 0.5) 
            
            ind = PostureIndicators(
                cheek_distance=y, eye_distance=0.05,
                face_vertical_length=0.1, # 기본값
                shoulder_width=x, shoulder_tilt_deg=0.0,
                neck_offset=0.0, eye_line_tilt=0.0, chin_occlusion=0.0,
                hand_near_face=False, hand_face_score=0.0, timestamp=time.time()
            )
            bm.add_frame_to_collection(ind)
            
        bm.finish_baseline_collection(fps=30)
        
        assert bm.ransac_model.is_fitted, "RANSAC 모델 학습 실패"
        
        test_x = 0.35
        expected_y = bm.get_expected_cheek(test_x)
        clean_y = 0.5 * (test_x**2) + 0.2 * test_x + 0.05
        
        logger.info(f"Test 1: x={test_x:.2f} -> expected_y={expected_y:.4f} (정답 근사치: {clean_y:.4f})")
        assert abs(expected_y - clean_y) < 0.02, f"예측값 오차 과다: {expected_y} vs {clean_y}"
        
        logger.info("✓ Test 1 통과")
        return True
    except Exception as e:
        logger.error(f"✗ Test 1 실패: {e}")
        return False

def test_2_judgment_logic():
    """Test 2: Deviation (%) 기반 판정 로직 및 EMA 안정화 검증"""
    try:
        config = ConfigManager()
        bm = BaselineManager(config, data_dir="data_test")
        # Mock baseline
        bm.baseline_metrics = type('obj', (object,), {
            'metrics': {
                'cheek_distance': 0.1, 
                'shoulder_width': 0.3,
                'face_vertical_length': 0.15,
                'eye_distance': 0.05
            }
        })()
        bm.get_expected_cheek = lambda x: 0.1
        # calculate_change_percentage mock
        def mock_calc_change(val, name):
            base = bm.baseline_metrics.metrics[name]
            return (val - base) / base * 100.0
        bm.calculate_change_percentage = mock_calc_change
        
        je = JudgmentEngine(config, bm)
        # EMA 필터 영향 배제를 위해 alpha=1.0 강제 적용 (테스트용)
        for f in je.likes_filters.values():
            f.alpha = 1.0
            
        logger.info(f"Sensitivities: Fwd={je.forward_head_sensitivity}, Rec={je.recline_sensitivity}")

        # 1. 정상 자세
        normal_ind = PostureIndicators(
            cheek_distance=0.1, shoulder_width=0.3,
            eye_distance=0.05, face_vertical_length=0.15,
            shoulder_tilt_deg=0.0,
            neck_offset=0.0, eye_line_tilt=0.0, chin_occlusion=0.0,
            hand_near_face=False, hand_face_score=0.0, timestamp=time.time()
        )
        res_norm = je.judge_single_frame(normal_ind)
        logger.info(f"Normal: Fwd Like={res_norm.forward_head_likelihood:.4f}, Rec Like={res_norm.recline_likelihood:.4f}")
        assert res_norm.forward_head_likelihood < 0.1
        
        # 2. 거북목 유도 (편차 +15% -> 10% 기준 초과)
        # score = (0.15 / 0.10) * 0.5 = 0.75
        forward_ind = PostureIndicators(
            cheek_distance=0.115, shoulder_width=0.3,
            eye_distance=0.05, face_vertical_length=0.15,
            shoulder_tilt_deg=0.0,
            neck_offset=0.0, eye_line_tilt=0.0, chin_occlusion=0.0,
            hand_near_face=False, hand_face_score=0.0, timestamp=time.time()
        )
        res_fwd = je.judge_single_frame(forward_ind)
        logger.info(f"Forward (+15%): Like={res_fwd.forward_head_likelihood:.4f}")
        assert res_fwd.forward_head_likelihood >= 0.74, f"거북목 감지 실패: {res_fwd.forward_head_likelihood}"
        
        # 3. 기댄 자세 유도 (편차 -10% -> 4% 기준 초과, 얼굴 세로 길이도 감소 -10%)
        # abs_dev = 0.10. score = (0.10 / 0.04) * 0.5 = 1.25 -> clip 1.0
        recline_ind = PostureIndicators(
            cheek_distance=0.09, shoulder_width=0.3,
            eye_distance=0.05, face_vertical_length=0.135, # -10% 감소
            shoulder_tilt_deg=0.0,
            neck_offset=0.0, eye_line_tilt=0.0, chin_occlusion=0.0,
            hand_near_face=False, hand_face_score=0.0, timestamp=time.time()
        )
        res_rec = je.judge_single_frame(recline_ind)
        logger.info(f"Recline (-10%): Like={res_rec.recline_likelihood:.4f}")
        assert res_rec.recline_likelihood > 0.5, f"기댄 자세 감지 실패: {res_rec.recline_likelihood}"

        # 4. 기댄 자세 가드 테스트 (얼굴 크기는 작아졌으나 세로 길이는 유지됨)
        # face_v_len_change = 0% >= -4.0% (Stable) -> Recline 거부되어야 함
        recline_guard_ind = PostureIndicators(
            cheek_distance=0.09, shoulder_width=0.3,
            eye_distance=0.05, face_vertical_length=0.15, # 유지
            shoulder_tilt_deg=0.0,
            neck_offset=0.0, eye_line_tilt=0.0, chin_occlusion=0.0,
            hand_near_face=False, hand_face_score=0.0, timestamp=time.time()
        )
        res_rec_guard = je.judge_single_frame(recline_guard_ind)
        logger.info(f"Recline Guard (Stable V-Len): Like={res_rec_guard.recline_likelihood:.4f}")
        assert res_rec_guard.recline_likelihood == 0.0, f"기댄 자세 가드 작동 실패: {res_rec_guard.recline_likelihood}"
        
        logger.info("✓ Test 2 통과")
        return True
    except Exception as e:
        logger.error(f"✗ Test 2 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Phase 7: Shoulder-Cheek Model Verification (Debug)")
    print("=" * 60)
    Path("data_test").mkdir(exist_ok=True)
    
    results = [
        test_1_ransac_cheek_model(),
        test_2_judgment_logic()
    ]
    
    print("=" * 60)
    passed = sum(1 for r in results if r)
    print(f"Result: {passed}/{len(results)} Tests Passed")
    print("=" * 60)
    if passed < len(results): exit(1)
