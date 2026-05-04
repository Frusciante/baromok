"""
PyQt UI 애플리케이션

메인 UI 진입점
"""

import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication
import sys

from src.utils.logger import get_logger
from src.config import ConfigManager
from src.core.landmark_extractor import LandmarkExtractor
from src.core.indicator_calculator import IndicatorCalculator
from src.core.baseline_manager import BaselineManager
from src.core.judgment_engine import JudgmentEngine
from src.core.state_machine import StateMachine, StateTransitionEvent
from src.core.camera_worker import create_camera_worker
from src.core.session_manager import create_session_manager
from src.ui.main_window import create_main_window
from src.ui.screens import (
    BaselineScreen,
    HubScreen,
    SettingsScreen,
    StatisticsScreen,
    DetectionScreen,
)
from src.ui.styles.theme import ThemeManager

logger = get_logger(__name__)


class AlertSignalBridge(QObject):
    """백그라운드 상태 변화를 메인 스레드로 전달하는 브리지"""

    alert_requested = pyqtSignal(str, str)


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

        # 경고 UI 브리지
        self.alert_bridge = AlertSignalBridge()
        self.alert_bridge.alert_requested.connect(self._show_alert_popup)
        self.alert_popup = None
        self.alert_hide_timer = QTimer()
        self.alert_hide_timer.setSingleShot(True)
        self.alert_hide_timer.timeout.connect(self._hide_alert_popup)
        self.alert_cooldown_seconds = float(
            self.config.get_app_setting("alert_cooldown_seconds", 3.0)
        )
        self._last_alert_time = 0.0
        self._last_alert_type = ""

        # 엔진 컴포넌트 초기화 (Phase 2)
        logger.info("엔진 컴포넌트 초기화...")
        self.landmark_extractor = LandmarkExtractor("assets/models")
        self.indicator_calculator = IndicatorCalculator()
        self.baseline_manager = BaselineManager(self.config)
        self.judgment_engine = JudgmentEngine(self.config, self.baseline_manager)
        self.state_machine = StateMachine(self.config)
        self.state_machine.register_state_change_callback(self._handle_state_transition)
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
            logger.info("화면 전환: %s", screen_names[screen_index])
        else:
            logger.warning("잘못된 화면 인덱스: %s", screen_index)

    def _start_detection(self):
        """감지 시작"""
        logger.info("감지 시작")
        self.state_machine.reset()
        self._hide_alert_popup()
        self.session_manager.start_session()
        if not self.camera_worker.isRunning():
            self.camera_worker.start()
        self.switch_screen(4)  # DetectionScreen으로 이동

    def _stop_detection(self):
        """감지 중지"""
        logger.info("감지 중지")
        if self.camera_worker.isRunning() or self.camera_worker.is_running:
            self.camera_worker.stop_capture()
        self.session_manager.end_session()
        self._hide_alert_popup()
        self.switch_screen(1)  # HubScreen으로 이동

    def _handle_state_transition(self, event: StateTransitionEvent):
        """상태 전이 이벤트를 알림 팝업 요청으로 변환"""
        if event.to_state == event.from_state:
            return

        if event.to_state.value == "normal":
            self._hide_alert_popup()
            return

        alert_type = "warning" if event.to_state.value == "warning" else "danger"
        message_map = {
            "warning": "잘못된 자세가 감지되었습니다. 자세를 바로잡아 주세요.",
            "danger": "나쁜 자세가 지속되고 있습니다. 즉시 자세를 바르게 해주세요.",
        }
        message_text = message_map.get(alert_type, "자세를 확인해 주세요.")

        now = time.time()
        if (
            alert_type == self._last_alert_type
            and now - self._last_alert_time < self.alert_cooldown_seconds
        ):
            return

        self._last_alert_type = alert_type
        self._last_alert_time = now
        self.alert_bridge.alert_requested.emit(alert_type, message_text)

    def _show_alert_popup(self, alert_type: str, message_text: str):
        """메인 스레드에서 알림 팝업 표시"""
        if self.alert_popup is None:
            from src.ui.screens import AlertPopup

            self.alert_popup = AlertPopup(self.theme_manager, alert_type, message_text)
            self.alert_popup.close_signal.connect(self._hide_alert_popup)
        else:
            self.alert_popup.set_alert_content(alert_type, message_text)

        self.alert_popup.adjustSize()
        main_geom = self.main_window.geometry()
        popup_width = self.alert_popup.width()
        x = main_geom.x() + (main_geom.width() - popup_width) // 2
        y = main_geom.y() + 24
        self.alert_popup.move(x, y)
        self.alert_popup.show()
        self.alert_popup.raise_()
        self.alert_popup.activateWindow()

        self.alert_hide_timer.stop()
        self.alert_hide_timer.start(3000)

    def _hide_alert_popup(self):
        """알림 팝업 숨김"""
        if self.alert_popup is not None:
            self.alert_popup.hide()

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
        logger.error("애플리케이션 오류: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
