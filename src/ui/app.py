"""
PyQt UI 애플리케이션

메인 UI 진입점
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
import sys
from pathlib import Path

from src.utils.logger import get_logger
from src.config import ConfigManager
from src.core.landmark_extractor import LandmarkExtractor
from src.core.indicator_calculator import IndicatorCalculator
from src.core.baseline_manager import BaselineManager
from src.core.judgment_engine import JudgmentEngine
from src.core.state_machine import StateMachine
from src.core.camera_worker import create_camera_worker
from src.core.session_manager import create_session_manager
from src.ui.main_window import create_main_window
from src.ui.screens import (
    BaselineScreen,
    HubScreen,
    SettingsScreen,
    StatisticsScreen,
    DetectionScreen,
    AlertPopup,
)
from src.ui.styles.theme import ThemeManager

logger = get_logger(__name__)


class BarorokApp:
    """바로목 메인 애플리케이션"""

    def __init__(self):
        """초기화"""
        logger.info("바로목 애플리케이션 시작")

        # Qt 애플리케이션
        self.qt_app = QApplication(sys.argv)

        # 설정
        self.config = ConfigManager()

        # DPI 스케일
        screen = self.qt_app.primaryScreen()
        dpi_scale = screen.devicePixelRatio()
        logger.info(f"DPI 스케일: {dpi_scale:.2f}")

        # 테마
        self.theme_manager = ThemeManager(dpi_scale)

        # 엔진 컴포넌트 초기화 (Phase 2)
        logger.info("엔진 컴포넌트 초기화...")
        self.landmark_extractor = LandmarkExtractor(self.config)
        self.indicator_calculator = IndicatorCalculator()
        self.baseline_manager = BaselineManager(self.config)
        self.judgment_engine = JudgmentEngine(self.config, self.baseline_manager)
        self.state_machine = StateMachine(self.config)
        logger.info("✓ 엔진 컴포넌트 준비 완료")

        # 비즈니스 로직 초기화 (Phase 4)
        logger.info("비즈니스 로직 초기화...")
        self.session_manager = create_session_manager(self.config)
        logger.info("✓ 세션 관리자 준비 완료")

        # 카메라 워커 초기화 (Phase 4)
        logger.info("카메라 워커 초기화...")
        self.camera_worker = create_camera_worker(
            self.landmark_extractor,
            self.indicator_calculator,
            self.judgment_engine,
            self.state_machine,
            self.config,
        )
        logger.info("✓ 카메라 워커 준비 완료")

        # 메인 윈도우
        self.main_window = create_main_window(self.config)

        # 화면 생성 및 등록
        self._setup_screens()

        logger.info("바로목 애플리케이션 초기화 완료")

    def _setup_screens(self):
        """화면 설정"""
        logger.info("화면 설정 시작")

        # 기존 placeholder 제거
        while self.main_window.stacked_widget.count() > 0:
            self.main_window.stacked_widget.removeWidget(
                self.main_window.stacked_widget.widget(0)
            )

        # 의존성 주입과 함께 화면 생성
        self.baseline_screen = BaselineScreen(self.theme_manager, self.camera_worker)
        self.hub_screen = HubScreen(self.theme_manager)
        self.settings_screen = SettingsScreen(self.theme_manager)
        self.statistics_screen = StatisticsScreen(
            self.theme_manager, self.session_manager
        )
        self.detection_screen = DetectionScreen(
            self.theme_manager, self.camera_worker, self.session_manager
        )

        # 화면 등록
        self.main_window.stacked_widget.addWidget(self.baseline_screen)
        self.main_window.stacked_widget.addWidget(self.hub_screen)
        self.main_window.stacked_widget.addWidget(self.settings_screen)
        self.main_window.stacked_widget.addWidget(self.statistics_screen)
        self.main_window.stacked_widget.addWidget(self.detection_screen)

        # 신호 연결
        self.baseline_screen.baseline_captured_signal.connect(
            lambda: self.switch_screen(1)  # Hub로 이동
        )
        self.hub_screen.start_detection_signal.connect(self._start_detection)
        self.hub_screen.open_settings_signal.connect(
            lambda: self.switch_screen(2)  # Settings
        )
        self.hub_screen.open_statistics_signal.connect(
            lambda: self.switch_screen(3)  # Statistics
        )
        self.settings_screen.back_to_hub_signal.connect(
            lambda: self.switch_screen(1)  # Hub
        )
        self.statistics_screen.back_to_hub_signal.connect(
            lambda: self.switch_screen(1)  # Hub
        )
        self.detection_screen.detection_stopped_signal.connect(self._stop_detection)

        # 초기 화면: Hub
        self.main_window.stacked_widget.setCurrentWidget(self.hub_screen)

        logger.info("화면 설정 완료 (5개 화면 등록)")

    def switch_screen(self, screen_index: int):
        """
        화면 전환

        Args:
            screen_index: 화면 인덱스
        """
        if 0 <= screen_index < self.main_window.stacked_widget.count():
            self.main_window.stacked_widget.setCurrentIndex(screen_index)
            screen_names = ["baseline", "hub", "settings", "statistics", "detection"]
            logger.info(f"화면 전환: {screen_names[screen_index]}")
        else:
            logger.warning(f"잘못된 화면 인덱스: {screen_index}")

    def _start_detection(self):
        """감지 시작"""
        logger.info("감지 시작")
        self.session_manager.start_session()
        self.camera_worker.start()
        self.switch_screen(4)  # DetectionScreen으로 이동

    def _stop_detection(self):
        """감지 중지"""
        logger.info("감지 중지")
        self.camera_worker.stop_capture()
        self.session_manager.end_session()
        self.switch_screen(1)  # HubScreen으로 이동

    def run(self):
        """애플리케이션 실행"""
        logger.info("애플리케이션 실행")
        self.main_window.show()
        return self.qt_app.exec()


def main():
    """메인 진입점"""
    try:
        app = BarorokApp()
        sys.exit(app.run())
    except Exception as e:
        logger.error(f"애플리케이션 오류: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
