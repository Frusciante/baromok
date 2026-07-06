"""
Phase 7: Shoulder-Cheek Linear Model 자동화 테스트 (개선판)
"""

import logging
import time
import numpy as np
from pathlib import Path

from src.config import ConfigManager
from src.core.indicator_calculator import PostureIndicators
from src.core.baseline_manager import BaselineManager

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def test_1_ransac_cheek_model():
    """Test 1: 어깨 너비(x)에 따른 광대 거리(y) RANSAC 적합 검증 (정상 데이터)"""
    try:
        config = ConfigManager()
        bm = BaselineManager(config, data_dir=Path("data_test"))
        bm.minimum_valid_frame_count = 10
        bm.start_baseline_collection()
        
        # y = slope * x + intercept
        slope = 0.8
        intercept = 0.05
        for i in range(15):
            x = 0.2 + i * 0.02
            y_clean = slope * x + intercept
            # 노이즈 및 이상치 주입
            y = y_clean + (np.random.normal(0, 0.0001) if i % 5 != 0 else 0.5) 
            
            ind = PostureIndicators(
                cheek_distance=y,
                eye_distance=0.05,
                face_vertical_length=0.1,
                head_height=0.1,  # 추가된 필수 필드
                shoulder_width=x,
                shoulder_tilt_deg=0.0,
                neck_offset=0.0,
                eye_line_tilt=0.0,
                chin_occlusion=0.0,
                hand_near_face=False,
                hand_face_score=0.0,
                timestamp=time.time()
            )
            bm.add_frame_to_collection(ind)
            
        success = bm.finish_baseline_collection(fps=30)
        assert success, "Baseline 수집 완료 처리 실패"
        assert bm.shoulder_cheek_model.is_fitted, "RANSAC 모델 학습 실패"
        
        logger.info("✓ Test 1 통과")
        return True
    except Exception as e:
        logger.error(f"✗ Test 1 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_2_ransac_with_none_values():
    """Test 2: 수집 데이터에 None 지표가 포함되어 있을 때 RANSAC 모델 적합 예외 처리 검증"""
    try:
        config = ConfigManager()
        bm = BaselineManager(config, data_dir=Path("data_test"))
        bm.minimum_valid_frame_count = 10
        bm.start_baseline_collection()
        
        # y = slope * x + intercept
        slope = 0.8
        intercept = 0.05
        for i in range(20):
            x = 0.2 + i * 0.02
            y = slope * x + intercept
            
            # 중간에 어깨 너비나 광대 거리가 None인 프레임 주입 (측정 실패 가정)
            if i % 4 == 0:
                ind = PostureIndicators(
                    cheek_distance=None,  # None 주입
                    eye_distance=0.05,
                    face_vertical_length=0.1,
                    head_height=None,     # None 주입
                    shoulder_width=None,  # None 주입
                    shoulder_tilt_deg=0.0,
                    neck_offset=0.0,
                    eye_line_tilt=0.0,
                    chin_occlusion=0.0,
                    hand_near_face=False,
                    hand_face_score=0.0,
                    timestamp=time.time()
                )
            else:
                ind = PostureIndicators(
                    cheek_distance=y,
                    eye_distance=0.05,
                    face_vertical_length=0.1,
                    head_height=0.1,
                    shoulder_width=x,
                    shoulder_tilt_deg=0.0,
                    neck_offset=0.0,
                    eye_line_tilt=0.0,
                    chin_occlusion=0.0,
                    hand_near_face=False,
                    hand_face_score=0.0,
                    timestamp=time.time()
                )
            bm.add_frame_to_collection(ind)
            
        success = bm.finish_baseline_collection(fps=30)
        # None 프레임이 걸러지더라도 최소 유효 프레임 개수(10개) 이상이므로 성공해야 함
        assert success, "None 지표 프레임 스킵 실패로 인한 수집 완료 실패"
        assert bm.shoulder_cheek_model.is_fitted, "RANSAC 모델 학습 실패"
        
        logger.info("✓ Test 2 통과 (None 지표 예외 처리 정상 작동)")
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
        test_2_ransac_with_none_values()
    ]
    
    print("=" * 60)
    passed = sum(1 for r in results if r)
    print(f"Result: {passed}/{len(results)} Tests Passed")
    print("=" * 60)
    if passed < len(results): exit(1)
