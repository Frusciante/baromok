import sys
import os
import unittest
from unittest.mock import MagicMock
import numpy as np
from pathlib import Path
from PyQt6.QtCore import QEventLoop

# 프로젝트 루트를 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

from src.core.indicator_calculator import IndicatorCalculator, PostureIndicators
from src.core.baseline_manager import BaselineManager
from src.core.judgment_engine import JudgmentEngine, PostureType
from src.core.judge_workers import ForwardHeadWorker, ReclineWorker, PostureJudgeManager
from src.config import ConfigManager

class TestLeaningAlgorithmV3MultiThread(unittest.TestCase):
    """멀티스레드 기반 알고리즘 검증 테스트 (v1.2)"""

    def setUp(self):
        self.config = ConfigManager()
        self.calculator = IndicatorCalculator(self.config)
        self.baseline_manager = BaselineManager(self.config, data_dir="data_test")
        # Coordinator
        self.engine = JudgmentEngine(self.config, self.baseline_manager)

    def test_recline_worker_logic(self):
        """기댄 자세 워커 로직 단독 검증"""
        worker = ReclineWorker(self.config, self.baseline_manager)
        # EMA 필터 무력화
        worker.filter.alpha = 1.0
        
        # 결과 수집용 변수
        self.received_result = None
        worker.result_ready.connect(self._on_result)

        # Baseline 설정
        self.baseline_manager.shoulder_height_model.fit([0.4, 0.5, 0.6], [0.7, 0.7, 0.7])
        
        # 1. 바른 자세
        ind_good = PostureIndicators(
            cheek_distance=0.1, eye_distance=0.06, face_vertical_length=0.15,
            head_height=0.7, shoulder_width=0.5, shoulder_tilt_deg=0.0,
            neck_offset=0.1, eye_line_tilt=0.0, hand_near_face=False,
            chin_occlusion=0.0, eye_symmetry_ratio=0.02, cheek_symmetry_ratio=0.02,
            chin_alignment_offset=0.02, timestamp=100.0
        )
        worker.handle_indicators(ind_good)
        self.assertLess(self.received_result["likelihood"], 0.2)
        
        # 2. 기댄 자세 (높이 낮아짐)
        ind_lean = PostureIndicators(
            cheek_distance=0.1, eye_distance=0.06, face_vertical_length=0.15,
            head_height=0.672, shoulder_width=0.5, shoulder_tilt_deg=0.0,
            neck_offset=0.1, eye_line_tilt=0.0, hand_near_face=False,
            chin_occlusion=0.0, eye_symmetry_ratio=0.02, cheek_symmetry_ratio=0.02,
            chin_alignment_offset=0.02, timestamp=101.0
        )
        worker.handle_indicators(ind_lean)
        self.assertGreaterEqual(self.received_result["likelihood"], 0.4)

    def test_multi_posture_simultaneous_detection(self):
        """여러 자세 동시 감지 검증 (Manager & Engine 연동)"""
        manager = PostureJudgeManager(self.config, self.baseline_manager)
        
        # 모든 워커의 EMA 필터 무력화
        for w in manager.workers.values():
            w.filter.alpha = 1.0
            
        # Mocking Models
        self.baseline_manager.shoulder_height_model.fit([0.4, 0.5, 0.6], [0.7, 0.7, 0.7])
        self.baseline_manager.shoulder_cheek_model.fit([0.4, 0.5, 0.6], [0.1, 0.1, 0.1])
        
        # 거북목(Cheek 상승) + 기댄 자세(Height 하락) 동시 유도
        ind_both = PostureIndicators(
            cheek_distance=0.15, # Exp: 0.1 -> Dev: +50% (거북목)
            eye_distance=0.06,
            face_vertical_length=0.15,
            head_height=0.672,   # Exp: 0.7 -> Dev: -4% (기댄 자세)
            shoulder_width=0.5,
            shoulder_tilt_deg=0.0,
            neck_offset=0.1,
            eye_line_tilt=0.0,
            hand_near_face=False,
            chin_occlusion=0.0,
            eye_symmetry_ratio=0.02,
            cheek_symmetry_ratio=0.02,
            chin_alignment_offset=0.02,
            timestamp=200.0
        )
        
        # 비동기 결과 수집을 위한 루프
        loop = QEventLoop()
        captured_results = []
        
        def _handle(results):
            captured_results.extend(results)
            loop.quit()
            
        manager.all_results_ready.connect(_handle)
        manager.broadcast_indicators(ind_both)
        loop.exec() # 결과가 올 때까지 대기
        
        # 취합 및 검증
        final_res = self.engine.process_worker_results(captured_results, 200.0)
        
        # 두 자세 모두 active_postures에 포함되어야 함
        active_types = [p["posture_type"] for p in final_res.active_postures]
        self.assertIn("forward_head", active_types)
        self.assertIn("recline", active_types)
        print(f"동시 감지 성공: {active_types}")

        manager.stop_all()

    def test_recline_eye_close_conflict_resolution(self):
        """화면 가까움 시 기댄 자세 억제 로직 검증"""
        # 결과 시뮬레이션: Recline과 EyeClose가 모두 Triggered 된 상황
        simulated_results = [
            {"posture_type": "recline", "likelihood": 0.8, "triggered": True},
            {"posture_type": "eye_close", "likelihood": 0.9, "triggered": True},
            {"posture_type": "forward_head", "likelihood": 0.1, "triggered": False}
        ]
        
        final_res = self.engine.process_worker_results(simulated_results, 300.0)
        
        active_types = [p["posture_type"] for p in final_res.active_postures]
        
        # 1. eye_close는 포함되어야 함
        self.assertIn("eye_close", active_types)
        # 2. recline은 강제로 제거(억제)되어야 함
        self.assertNotIn("recline", active_types)
        print(f"충돌 해결 검증 완료: {active_types} (recline 억제됨)")

    def _on_result(self, res):
        self.received_result = res

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication([]) # QThread/Signal 사용을 위해 필요
    unittest.main()
