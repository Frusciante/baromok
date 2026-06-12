import sys
import os
import unittest
from unittest.mock import MagicMock
import numpy as np
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

from src.core.indicator_calculator import IndicatorCalculator, PostureIndicators
from src.core.baseline_manager import BaselineManager
from src.core.judgment_engine import JudgmentEngine, PostureType
from src.config import ConfigManager

class TestLeaningAlgorithmV2(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        self.calculator = IndicatorCalculator(self.config)
        self.baseline_manager = BaselineManager(self.config, data_dir="data_test")
        self.engine = JudgmentEngine(self.config, self.baseline_manager)
        
        # EMA 필터의 영향을 줄이기 위해 alpha를 1.0으로 설정하거나 여러 번 호출
        for filter_name in self.engine.likes_filters:
            self.engine.likes_filters[filter_name].alpha = 1.0

    def test_head_height_calculation(self):
        """머리 높이 계산 검증"""
        landmarks = {
            'left_eye': (0.4, 0.2),
            'right_eye': (0.6, 0.2),
            'left_cheek': (0.4, 0.4),
            'right_cheek': (0.6, 0.4)
        }
        h = self.calculator.calculate_head_height(
            landmarks['left_eye'], landmarks['right_eye'],
            landmarks['left_cheek'], landmarks['right_cheek']
        )
        self.assertAlmostEqual(h, 0.7)

    def test_baseline_height_model(self):
        """Baseline 높이 RANSAC 모델 피팅 및 로드 검증"""
        self.baseline_manager.reset()
        self.baseline_manager.start_baseline_collection()
        
        # 선형 관계 생성: 
        # height = 0.5 * shoulder + 0.2
        # height = 2.0 * eye + 0.1
        for i in range(50):
            sw = 0.3 + (i * 0.01)
            ed = 0.05 + (i * 0.002)
            hh_sw = 0.5 * sw + 0.2
            hh_ed = 2.0 * ed + 0.1
            # 여기서는 hh를 하나로 고정하여 두 모델이 각각의 x에 대해 학습되도록 함
            hh = (hh_sw + hh_ed) / 2.0 
            
            ind = PostureIndicators(
                cheek_distance=0.1, eye_distance=ed, face_vertical_length=0.15,
                head_height=hh, shoulder_width=sw, shoulder_tilt_deg=0.0,
                neck_offset=0.1, eye_line_tilt=0.0, hand_near_face=False,
                chin_occlusion=0.0, timestamp=float(i)
            )
            self.baseline_manager.add_frame_to_collection(ind)
        
        success = self.baseline_manager.finish_baseline_collection()
        self.assertTrue(success)
        self.assertTrue(self.baseline_manager.shoulder_height_model.is_fitted)
        self.assertTrue(self.baseline_manager.eye_height_model.is_fitted)
        
        # 로드 검증
        self.baseline_manager.save_baseline_to_file()
        new_manager = BaselineManager(self.config, data_dir="data_test")
        self.assertTrue(new_manager.load_baseline_from_file())
        self.assertTrue(new_manager.shoulder_height_model.is_fitted)
        self.assertTrue(new_manager.eye_height_model.is_fitted)

    def test_recline_judgment(self):
        """기댄 자세 판정 로직 검증 (높이 기반)"""
        # Baseline 설정
        self.baseline_manager.reset()
        self.baseline_manager.baseline_metrics = MagicMock()
        self.baseline_manager.baseline_metrics.metrics = {
            "head_height": 0.7,
            "shoulder_width": 0.5,
            "eye_distance": 0.06,
            "cheek_distance": 0.1
        }
        # 모델 수동 피팅
        self.baseline_manager.shoulder_height_model.fit([0.4, 0.5, 0.6], [0.7, 0.7, 0.7])
        self.baseline_manager.eye_height_model.fit([0.05, 0.06, 0.07], [0.7, 0.7, 0.7])
        self.baseline_manager.shoulder_cheek_model.fit([0.4, 0.5, 0.6], [0.1, 0.1, 0.1])
        
        # 1. 바른 자세 (deviation ~ 0)
        ind_good = PostureIndicators(
            cheek_distance=0.1, eye_distance=0.06, face_vertical_length=0.15,
            head_height=0.7, shoulder_width=0.5, shoulder_tilt_deg=0.0,
            neck_offset=0.1, eye_line_tilt=0.0, hand_near_face=False,
            chin_occlusion=0.0, eye_symmetry_ratio=0.0, cheek_symmetry_ratio=0.0,
            chin_alignment_offset=0.0, timestamp=100.0
        )
        res_good = self.engine.judge_single_frame(ind_good)
        self.assertLess(res_good.recline_likelihood, 0.2)
        
        # 2. 기댄 자세 (어깨 기반)
        ind_lean_sh = PostureIndicators(
            cheek_distance=0.1, eye_distance=0.06, face_vertical_length=0.15,
            head_height=0.672, shoulder_width=0.5, shoulder_tilt_deg=0.0,
            neck_offset=0.1, eye_line_tilt=0.0, hand_near_face=False,
            chin_occlusion=0.0, eye_symmetry_ratio=0.0, cheek_symmetry_ratio=0.0,
            chin_alignment_offset=0.0, timestamp=101.0
        )
        res_lean_sh = self.engine.judge_single_frame(ind_lean_sh)
        self.assertGreaterEqual(res_lean_sh.recline_likelihood, 0.4)
        
        # 3. 기댄 자세 (눈 기반 - 어깨 없음)
        ind_lean_eye = PostureIndicators(
            cheek_distance=0.1, eye_distance=0.06, face_vertical_length=0.15,
            head_height=0.672, shoulder_width=None, shoulder_tilt_deg=None,
            neck_offset=0.1, eye_line_tilt=0.0, hand_near_face=False,
            chin_occlusion=0.0, eye_symmetry_ratio=0.0, cheek_symmetry_ratio=0.0,
            chin_alignment_offset=0.0, timestamp=102.0
        )
        res_lean_eye = self.engine.judge_single_frame(ind_lean_eye)
        self.assertGreaterEqual(res_lean_eye.recline_likelihood, 0.4)

if __name__ == "__main__":
    unittest.main()
