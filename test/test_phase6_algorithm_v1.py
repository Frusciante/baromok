"""
Phase 6: Algorithm v1.0 Integration 자동화 테스트
"""

import logging
import time
import numpy as np

from src.config import ConfigManager
from src.utils.helpers import OneEuroFilter, EMAFilter
from src.core.indicator_calculator import IndicatorCalculator, PostureIndicators
from src.core.baseline_manager import BaselineManager
from src.core.judgment_engine import JudgmentEngine
from src.core.state_machine import StateMachine, PostureState

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def test_1_filters():
    """Test 1: One Euro & EMA 필터 동작 검증"""
    try:
        ema = EMAFilter(alpha=1.0) # 테스트를 위해 즉시 반영
        val1 = ema.process(10.0)
        val2 = ema.process(20.0)
        assert val2 == 20.0, "EMA 필터 동작 실패"
        
        oe = OneEuroFilter()
        pts1 = oe.process(time.time(), [0.5, 0.5])
        time.sleep(0.01)
        pts2 = oe.process(time.time(), [0.6, 0.6])
        assert len(pts2) == 2, "One Euro 필터 출력 차원 오류"
        logger.info("✓ Test 1 통과: 필터 클래스 정상 동작")
        return True
    except Exception as e:
        logger.error(f"✗ Test 1 실패: {e}")
        return False

def test_2_ransac_baseline():
    """Test 2: BaselineManager의 RANSAC 캘리브레이션 검증"""
    try:
        config = ConfigManager()
        bm = BaselineManager(config, data_dir="data_test")
        bm.minimum_valid_frame_count = 10
        bm.start_baseline_collection()
        
        for i in range(10):
            ind = PostureIndicators(
                cheek_distance=0.1 + i*0.01,
                eye_distance=0.05,
                face_vertical_length=0.15,
                head_height=0.7,
                shoulder_width=0.2 + i*0.02,
                shoulder_tilt_deg=0.0,
                neck_offset=0.0,
                eye_line_tilt=0.0,
                chin_occlusion=0.0,
                hand_near_face=False,
                hand_face_score=0.0,
                timestamp=time.time()
            )
            bm.add_frame_to_collection(ind)
            
        bm.finish_baseline_collection(fps=30)
        
        assert bm.ransac_model.is_fitted, "RANSAC 모델 학습 실패"
        
        # get_expected_ratio 대신 get_expected_cheek 사용 권장되나 기존 테스트 유지 위해 호출
        expected_cheek = bm.get_expected_cheek(0.3)
        assert expected_cheek > 0, "예상 광대 거리 산출 실패"
        
        logger.info("✓ Test 2 통과: RANSAC 캘리브레이션 성공")
        return True
    except Exception as e:
        logger.error(f"✗ Test 2 실패: {e}")
        return False

def test_3_new_indicators():
    """Test 3: hand_face_score 신규 지표 연산 검증"""
    try:
        calc = IndicatorCalculator()
        score = calc.calculate_hand_near_score(
            landmarks_dict={'right_hand_tips': [(0.51, 0.51)], 'left_hand_tips': []},
            face_center=(0.5, 0.5)
        )
        assert score > 0.8, f"손-얼굴 근접 점수 산출 오류: {score}"
        logger.info("✓ Test 3 통과: 신규 지표(hand_face_score) 산출 성공")
        return True
    except Exception as e:
        logger.error(f"✗ Test 3 실패: {e}")
        return False

def test_4_judgment_engine_new_formula():
    """Test 4: JudgmentEngine의 새로운 RANSAC 오차 점수 기반 판정 확인"""
    try:
        config = ConfigManager()
        bm = BaselineManager(config, data_dir="data_test")
        bm.baseline_metrics = type('obj', (object,), {
            'metrics': {'cheek_distance': 0.1, 'shoulder_width': 0.2, 'head_height': 0.7}
        })()
        bm.ransac_model.fit([0.2, 0.3], [0.1, 0.15]) # y = 0.5x
        
        je = JudgmentEngine(config, bm)
        for f in je.likes_filters.values(): f.alpha = 1.0 # 즉시 반영
        
        # 거북목 유도: shoulder_width=0.2 면 expected_cheek=0.1. 현재 cheek_distance=0.15 면 deviation=0.5
        bad_ind = PostureIndicators(
            cheek_distance=0.15, eye_distance=0.05,
            face_vertical_length=0.15, head_height=0.7,
            shoulder_width=0.2, shoulder_tilt_deg=0.0,
            neck_offset=0.0, eye_line_tilt=0.0, chin_occlusion=0.0,
            hand_near_face=False, hand_face_score=0.0, timestamp=time.time()
        )
        
        result = je.judge_single_frame(bad_ind)
        assert result.forward_head_likelihood > 0.45, f"거북목 점수 미달: {result.forward_head_likelihood}"
        
        logger.info(f"✓ Test 4 통과: 신규 점수 공식 동작 성공")
        return True
    except Exception as e:
        logger.error(f"✗ Test 4 실패: {e}")
        return False

def test_5_state_machine_hysteresis():
    """Test 5: 상태 머신 Hysteresis (깜빡임 방어) 검증"""
    try:
        config = ConfigManager()
        sm = StateMachine(config)
        assert sm.current_state == PostureState.NORMAL
        sm.update_state("forward_head")
        assert sm.current_state == PostureState.WARNING
        sm.update_state(None)
        assert sm.current_state == PostureState.WARNING
        logger.info("✓ Test 5 통과: Hysteresis 방어 로직 성공")
        return True
    except Exception as e:
        logger.error(f"✗ Test 5 실패: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Phase 6 자동화 테스트 시작")
    print("=" * 50)
    results = [test_1_filters(), test_2_ransac_baseline(), test_3_new_indicators(), test_4_judgment_engine_new_formula(), test_5_state_machine_hysteresis()]
    print("=" * 50)
    passed = sum(1 for r in results if r)
    print(f"총 {passed}/{len(results)} 테스트 통과")
    print("=" * 50)
