"""
PyQt UI 애플리케이션

메인 UI 진입점
"""

import time
import threading

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QPushButton,
    QCheckBox,
    QRadioButton,
    QToolButton,
)
import sys

from src.utils.logger import get_logger
from src.config import ConfigManager, SettingsConfig
from src.core.landmark_extractor import LandmarkExtractor
from src.core.indicator_calculator import IndicatorCalculator
from src.core.baseline_manager import BaselineManager
from src.core.judgment_engine import JudgmentEngine
from src.core.state_machine import StateMachine, StateTransitionEvent
from src.core.camera_worker import create_camera_worker
from src.core.session_manager import create_session_manager
from src.core.sound_manager import SoundManager
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


class baromokApp:
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
        self._last_alert_time = 0.0
        self._last_alert_type = ""
        self._previous_screen_index = 1

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

        # 설정 로드
        self.settings_config = SettingsConfig.load_from_json("data/config.json")
        logger.info("사용자 설정 로드 완료")
        # 알림음 관리자
        self.sound_manager = SoundManager()
        self._sound_playing = False
        self._last_sound_time = 0.0
        self._sound_cooldown_seconds = 3.0

        # 메인 윈도우
        self.main_window = create_main_window(self.config)

        # 화면 생성 및 등록
        self._setup_screens()
        self._apply_interactive_cursor_policy()

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
        self.baseline_screen = BaselineScreen(
            self.theme_manager, self.camera_worker, self.baseline_manager
        )
        self.hub_screen = HubScreen(self.theme_manager)
        self.settings_screen = SettingsScreen(
            self.theme_manager, vars(self.settings_config)  # dataclass를 dict로 변환
        )
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
            self._handle_baseline_captured
        )
        self.hub_screen.open_baseline_signal.connect(
            lambda: self.switch_screen(0)  # Baseline
        )
        self.hub_screen.start_detection_signal.connect(self._start_detection)
        self.hub_screen.open_settings_signal.connect(
            lambda: self.switch_screen(2)  # Settings
        )
        self.hub_screen.open_statistics_signal.connect(
            lambda: self.switch_screen(3)  # Statistics
        )
        self.detection_screen.open_settings_signal.connect(
            lambda: self.switch_screen(2)  # Settings
        )
        self.settings_screen.settings_saved_signal.connect(self._save_settings)
        self.settings_screen.back_to_hub_signal.connect(self._return_from_settings)
        self.statistics_screen.back_to_hub_signal.connect(
            lambda: self.switch_screen(1)  # Hub
        )
        self.detection_screen.detection_stopped_signal.connect(self._stop_detection)

        # 초기 화면: Hub
        self.main_window.stacked_widget.setCurrentWidget(self.hub_screen)

        logger.info("화면 설정 완료 (5개 화면 등록)")

    def _apply_interactive_cursor_policy(self):
        """QSS의 cursor 규칙 대신 코드에서 인터랙티브 위젯 커서를 적용한다."""
        interactive_widgets = self.main_window.findChildren(
            (QPushButton, QCheckBox, QRadioButton, QToolButton)
        )
        for widget in interactive_widgets:
            if widget.isEnabled():
                widget.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                widget.setCursor(Qt.CursorShape.ArrowCursor)

    # ========== 프로퍼티: 설정값 실시간 반영 ==========
    @property
    def alert_cooldown_seconds(self) -> float:
        """알림 쿨다운 시간 (초) - 설정값에서 실시간 읽음"""
        return float(self.settings_config.notification_interval)

    @property
    def popup_timeout_ms(self) -> int:
        """팝업 자동 닫기 타이머 (밀리초) - 0이면 타이머 비활성화"""
        if self.settings_config.popup_auto_close:
            return int(self.settings_config.popup_auto_close_time * 1000)
        else:
            return 0

    @property
    def popup_position_xy(self) -> tuple:
        """팝업 화면 위치 (x, y) - 중앙 또는 상단"""
        if self.alert_popup is None:
            return (0, 0)

        main_geom = self.main_window.geometry()
        popup_width = self.alert_popup.width()
        popup_height = self.alert_popup.height()

        if self.settings_config.popup_position == "top":
            # 화면 상단 중앙 (상단에서 20px 아래)
            x = main_geom.x() + (main_geom.width() - popup_width) // 2
            y = main_geom.y() + 20
        else:  # "center" (기본값)
            # 화면 중앙
            x = main_geom.x() + (main_geom.width() - popup_width) // 2
            y = main_geom.y() + (main_geom.height() - popup_height) // 2

        return (x, y)

    def switch_screen(self, screen_index: int):
        """
        화면 전환

        Args:
            screen_index: 화면 인덱스
        """
        if 0 <= screen_index < self.main_window.stacked_widget.count():
            self._previous_screen_index = self.main_window.stacked_widget.currentIndex()
            self.main_window.stacked_widget.setCurrentIndex(screen_index)
            screen_names = ["baseline", "hub", "settings", "statistics", "detection"]
            logger.info("화면 전환: %s", screen_names[screen_index])
        else:
            logger.warning("잘못된 화면 인덱스: %s", screen_index)

    def _return_from_settings(self):
        """설정 화면에서 마지막 화면으로 복귀"""
        target_index = self._previous_screen_index
        if target_index == 2:
            target_index = 1
        self.switch_screen(target_index)

    def _start_detection(self):
        """감지 시작"""
        logger.info("감지 시작")
        self.camera_worker.set_baseline_mode(False)
        if self.camera_worker.is_paused:
            self.camera_worker.resume()
        self.state_machine.reset()
        self._hide_alert_popup()
        self.session_manager.start_session()
        if not self.camera_worker.isRunning():
            self.camera_worker.start()
        self.switch_screen(4)  # DetectionScreen으로 이동
        self.detection_screen.on_detection_started()

    def _handle_baseline_captured(self):
        """Baseline 완료 후 다음 동작 처리"""
        if self.settings_config.auto_start_detection:
            logger.info("자동 감지 시작 설정 활성화: 바로 감지 시작")
            self._start_detection()
        else:
            self.switch_screen(1)  # HubScreen으로 이동

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

        if not self.settings_config.notification_enabled:
            self._hide_alert_popup()
            self._last_alert_type = ""
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
            and now - self._last_alert_time
            < self.alert_cooldown_seconds  # 프로퍼티 사용
        ):
            return

        self._last_alert_type = alert_type
        self._last_alert_time = now
        self.alert_bridge.alert_requested.emit(alert_type, message_text)

    def _show_alert_popup(self, alert_type: str, message_text: str):
        """메인 스레드에서 알림 팝업 표시"""
        if not self.settings_config.notification_enabled:
            return

        if self.alert_popup is None:
            from src.ui.screens import AlertPopup

            self.alert_popup = AlertPopup(self.theme_manager, alert_type, message_text)
            self.alert_popup.close_signal.connect(self._hide_alert_popup)
        else:
            self.alert_popup.set_alert_content(alert_type, message_text)

        self.alert_popup.adjustSize()

        # 팝업 위치 동적 계산 (프로퍼티 사용)
        x, y = self.popup_position_xy
        self.alert_popup.move(x, y)
        self.alert_popup.show()
        self.alert_popup.raise_()
        self.alert_popup.activateWindow()

        # 타이머 동적 설정 (프로퍼티 사용)
        timeout_ms = self.popup_timeout_ms
        self.alert_hide_timer.stop()
        if timeout_ms > 0:
            self.alert_hide_timer.start(timeout_ms)
            logger.debug(f"팝업 타이머 시작: {timeout_ms}ms")
        else:
            logger.debug("팝업 타이머 비활성화 (수동 닫기)")
        # 알림음 재생
        if self.settings_config.sound_enabled:
            self._play_alert_sound_async()

    def _hide_alert_popup(self):
        """알림 팝업 숨김"""
        if self.alert_popup is not None:
            self.alert_popup.hide()

    def _play_alert_sound_async(self):
        """알림음을 UI 스레드를 막지 않도록 백그라운드에서 재생"""
        if not self.settings_config.sound_enabled:
            return

        now = time.time()
        if now - self._last_sound_time < self._sound_cooldown_seconds:
            return

        if self._sound_playing:
            return

        self._last_sound_time = now
        self._sound_playing = True

        def _play():
            try:
                self.sound_manager.play_alert(self.settings_config.sound_volume)
            except Exception as e:
                logger.error(f"알림음 재생 실패: {e}", exc_info=True)
            finally:
                self._sound_playing = False

        thread = threading.Thread(target=_play, daemon=True)
        thread.start()

    def _save_settings(self, settings_dict: dict):
        """설정 저장"""
        try:
            # 설정값 업데이트
            for key, value in settings_dict.items():
                if hasattr(self.settings_config, key):
                    setattr(self.settings_config, key, value)

            # JSON 파일에 저장
            self.settings_config.save_to_json("data/config.json")

            # 설정값 즉시 적용
            self._apply_settings()

            logger.info(f"설정 저장 완료: {settings_dict}")
        except Exception as e:
            logger.error(f"설정 저장 실패: {e}")

    def _apply_settings(self):
        """설정값 즉시 적용"""
        logger.info("설정값 적용:")
        logger.info(f"  - 알림 활성화: {self.settings_config.notification_enabled}")
        logger.info(f"  - 알림 간격: {self.settings_config.notification_interval}초")
        logger.info(f"  - 팝업 위치: {self.settings_config.popup_position}")
        logger.info(
            f"  - 팝업 자동 닫기: {self.settings_config.popup_auto_close} "
            f"({self.settings_config.popup_auto_close_time}초)"
        )

        if not self.settings_config.notification_enabled:
            self.alert_hide_timer.stop()
            self._hide_alert_popup()

    def run(self):
        """애플리케이션 실행"""
        logger.info("애플리케이션 실행")
        self.main_window.show()
        return self.qt_app.exec()


def main():
    """메인 진입점"""
    try:
        app = baromokApp()
        sys.exit(app.run())
    except Exception as e:
        logger.error("애플리케이션 오류: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
