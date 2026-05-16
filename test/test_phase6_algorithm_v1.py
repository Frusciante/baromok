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
        ema = EMAFilter(alpha=0.15)
        val1 = ema.process(10.0)
        val2 = ema.process(20.0)
        assert val2 > 10.0 and val2 < 20.0, "EMA 필터 평활화 실패"
        
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
        bm.minimum_valid_frame_count = 10  # 테스트를 위해 최소 필요 프레임 제한 축소
        bm.start_baseline_collection()
        
        # 가상의 거리 이동 데이터 주입 (어깨가 커질수록 얼굴-어깨 비율 변화)
        for i in range(10):
            ind = PostureIndicators(
                cheek_distance=0.1 + i*0.01,
                eye_distance=0.05,
                face_shoulder_ratio=0.5 - i*0.01,
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
        
        # RANSAC 적합 확인
        assert bm.ransac_model.is_fitted, "RANSAC 모델 학습 실패 (is_fitted=False)"
        
        expected_ratio = bm.get_expected_ratio(0.3)
        assert expected_ratio > 0, f"예상 비율 산출 실패: {expected_ratio}"
        
        logger.info("✓ Test 2 통과: RANSAC 캘리브레이션 및 예상 비율 반환 성공")
        return True
    except Exception as e:
        logger.error(f"✗ Test 2 실패: {e}")
        return False

def test_3_new_indicators():
    """Test 3: hand_face_score 신규 지표 연산 검증"""
    try:
        calc = IndicatorCalculator()
        # 손이 얼굴(코)에 매우 가까운 상황 부여
        score = calc.calculate_hand_near_score(
            hand_tips={'right_hand_tips': [(0.51, 0.51)], 'left_hand_tips': []},
            face_center=(0.5, 0.5)
        )
        assert score > 0.8, f"손-얼굴 근접 점수 산출 오류 (점수 낮음): {score}"
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
        # Mock baseline
        bm.baseline_metrics = type('obj', (object,), {'metrics': {'face_shoulder_ratio': 0.5, 'cheek_distance': 0.1}})()
        bm.ransac_model.is_fitted = False # Fallback to default baseline ratio
        
        je = JudgmentEngine(config, bm)
        
        # 거북목 유도: 얼굴이 커지고 비율이 예상보다 커짐
        bad_ind = PostureIndicators(
            cheek_distance=0.15, eye_distance=0.05,
            face_shoulder_ratio=0.65, # 기준(0.5) 대비 상승
            shoulder_width=0.23, shoulder_tilt_deg=0.0,
            neck_offset=0.0, eye_line_tilt=0.0, chin_occlusion=0.0,
            hand_near_face=False, hand_face_score=0.0, timestamp=time.time()
        )
        
        result = je.judge_single_frame(bad_ind)
        assert result.forward_head_likelihood > 0.45, "거북목 새 공식 계산 오류 (점수 미달)"
        
        logger.info(f"✓ Test 4 통과: 신규 점수 공식 동작 성공 (거북목 점수: {result.forward_head_likelihood:.2f})")
        return True
    except Exception as e:
        logger.error(f"✗ Test 4 실패: {e}")
        return False

def test_5_state_machine_hysteresis():
    """Test 5: 상태 머신 Hysteresis (깜빡임 방어) 검증"""
    try:
        config = ConfigManager()
        sm = StateMachine(config)
        
        # 최초 상태
        assert sm.current_state == PostureState.NORMAL
        
        # 나쁜 자세 발생 -> WARNING 진입
        sm.update_state("forward_head")
        assert sm.current_state == PostureState.WARNING, "WARNING 진입 실패"
        
        # 방어 로직 확인: 상태 변경 직후(min_state_hold_sec = 1.8초 이내) 정상 자세를 주입해도 무시되어야 함
        sm.update_state(None)
        assert sm.current_state == PostureState.WARNING, "Hysteresis 실패: 상태가 너무 일찍 풀림"
        
        logger.info("✓ Test 5 통과: Hysteresis 방어 로직 성공")
        return True
    except Exception as e:
        logger.error(f"✗ Test 5 실패: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Phase 6 자동화 테스트 시작")
    print("=" * 50)
    
    results = [
        test_1_filters(),
        test_2_ransac_baseline(),
        test_3_new_indicators(),
        test_4_judgment_engine_new_formula(),
        test_5_state_machine_hysteresis()
    ]
    
    print("=" * 50)
    passed = sum(1 for r in results if r)
    print(f"총 {passed}/{len(results)} 테스트 통과")
    print("=" * 50)