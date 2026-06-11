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

# 앱 진입점 (src/ui/app.py 또는 main.py)에서 QApplication 만들기 전에 DPI 정책 설정
QApplication.setHighDpiScaleFactorRoundingPolicy(
      Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
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
from src.ui.styles.font_loader import load_bundled_fonts, set_app_font, BUNDLED_FAMILY

logger = get_logger(__name__)


class AlertSignalBridge(QObject):
    """백그라운드 상태 변화를 메인 스레드로 전달하는 브리지"""

    alert_requested = pyqtSignal(str, str)
    sound_requested = pyqtSignal(int)


class baromokApp:
    """바로목 메인 애플리케이션"""

    def __init__(self):
        """초기화"""
        logger.info("바로목 애플리케이션 시작")

        # Qt 애플리케이션
        self.qt_app = QApplication(sys.argv)

        # 번들 폰트 로드
        self.font_family = load_bundled_fonts()
        set_app_font(self.qt_app, self.font_family)

        # 설정
        self.config = ConfigManager()

        # DPI 스케일 (logicalDotsPerInch 사용 — Windows 배율 125%/150% 등 정확히 반영)
        screen = self.qt_app.primaryScreen()
        dpi_scale = screen.logicalDotsPerInch() / 96.0
        logger.info(f"DPI 스케일: {dpi_scale:.2f} (logical DPI: {screen.logicalDotsPerInch()})")

        # 테마
        self.theme_manager = ThemeManager(dpi_scale)

        # 경고 UI 브리지
        self.alert_bridge = AlertSignalBridge()
        self.alert_bridge.alert_requested.connect(self._show_alert_popup)
        self.alert_bridge.sound_requested.connect(self._play_alert_sound)
        self.alert_popup = None
        self.alert_hide_timer = QTimer()
        self.alert_hide_timer.setSingleShot(True)
        self.alert_hide_timer.timeout.connect(self._hide_alert_popup)
        self._last_alert_time = 0.0
        self._last_alert_type = ""
        self._alert_state_lock = threading.Lock()
        self._previous_screen_index = 1

        # 엔진 컴포넌트 초기화 (Phase 2)
        logger.info("엔진 컴포넌트 초기화...")
        self.landmark_extractor = LandmarkExtractor("assets/models")
        self.indicator_calculator = IndicatorCalculator(self.config)
        self.baseline_manager = BaselineManager(self.config)
        # ⬇ [추가] 앱 시작 시 기존 베이스라인 로드 시도
        if self.baseline_manager.load_baseline_from_file():
            logger.info("기존 베이스라인 로드 성공")
        else:
            logger.info("기존 베이스라인 없음 또는 로드 실패")

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

        # 설정 로드 (ConfigManager를 전달하여 기본값 처리)
        self.settings_config = SettingsConfig.load_from_json(
            "data/config.json", self.config
        )
        self._settings_dirty = False
        logger.info("사용자 설정 로드 완료")

        # 로드된 감도를 판정 엔진에 적용
        self.judgment_engine.update_sensitivities(
            self.settings_config.forward_head_sensitivity,
            self.settings_config.recline_sensitivity,
        )

        # 알림음 관리자
        self.sound_manager = SoundManager()
        # 설정에서 로드된 음량을 사운드 매니저에 반영
        try:
            self.sound_manager.set_volume_percent(self.settings_config.sound_volume)
        except Exception:
            logger.debug("사운드 초기 볼륨 반영 실패")

        self._last_sound_time = 0.0
        self._sound_cooldown_seconds = 3.0
        self._last_sound_state = ""

        # 메인 윈도우
        self.main_window = create_main_window(self.config)
        # 뒤로가기 콜백 등록 (현재 화면에 따라 이전 화면으로 복귀)
        try:
            self.main_window.set_back_callback(self._handle_header_back)
            self.main_window.posture_adjust_requested.connect(
                lambda: self.switch_screen(0)
            )
            self.main_window.settings_requested.connect(lambda: self.switch_screen(2))
            self.main_window.statistics_requested.connect(lambda: self.switch_screen(3))
        except Exception:
            logger.debug("메인 윈도우 헤더 버튼 시그널 연결 실패")

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
            self.theme_manager,
            self.camera_worker,
            self.baseline_manager,
            self.sound_manager,
        )
        self.hub_screen = HubScreen(
            self.theme_manager,
            self.session_manager,
            self.baseline_manager,
        )
        self.settings_screen = SettingsScreen(
            self.theme_manager, vars(self.settings_config)  # dataclass를 dict로 변환
        )
        self.statistics_screen = StatisticsScreen(
            self.theme_manager, self.session_manager
        )
        self.detection_screen = DetectionScreen(
            self.theme_manager,
            self.camera_worker,
            self.session_manager,
            self.baseline_manager,
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
        self.baseline_screen.baseline_recommended_signal.connect(
            self._apply_recommended_sensitivities
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
        self.detection_screen.open_baseline_signal.connect(
            lambda: self.switch_screen(0)  # Baseline (재측정)
        )
        self.settings_screen.settings_saved_signal.connect(self._save_settings)
        self.settings_screen.settings_reset_signal.connect(self._reset_settings)
        self.settings_screen.back_to_hub_signal.connect(self._handle_header_back)
        # Settings 화면의 위젯 변경 신호를 실시간 적용하도록 연결
        try:
            for widget in self.settings_screen.category_widgets:
                widget.value_changed_signal.connect(self._on_settings_widget_changed)
                if hasattr(widget, "test_requested_signal"):
                    widget.test_requested_signal.connect(self._test_sound_now)
        except Exception:
            logger.debug("설정 위젯 변경 신호 연결 중 오류 발생")
        self.statistics_screen.back_to_hub_signal.connect(
            lambda: self.switch_screen(1)  # Hub
        )
        self.detection_screen.detection_stopped_signal.connect(self._stop_detection)
        # DetectionScreen의 추가 액션 신호 연결
        self.detection_screen.detection_restart_signal.connect(self._start_detection)
        self.detection_screen.view_results_signal.connect(lambda: self.switch_screen(3))

        # 초기 화면: Hub
        self.main_window.stacked_widget.setCurrentWidget(self.hub_screen)
        self.main_window.set_header_title(self.SCREEN_TITLES[1], show_icon=False)

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

    def _settings_to_dict(self) -> dict:
        """현재 설정 dataclass를 dict 형태로 변환한다."""
        return vars(self.settings_config)

    def _refresh_settings_screen_values(self):
        """설정 화면 위젯을 앱의 최신 설정값으로 동기화한다."""
        settings_dict = self._settings_to_dict()
        if hasattr(self.settings_screen, "update_settings"):
            self.settings_screen.update_settings(settings_dict)
            return

        for widget in self.settings_screen.category_widgets:
            widget.blockSignals(True)
            widget.set_value(settings_dict)
            widget.blockSignals(False)

    def _persist_settings_if_dirty(self, force: bool = False, reason: str = ""):
        """dirty 정책에 따라 설정을 단일 경로로 저장한다."""
        if not force and not self._settings_dirty:
            return

        self.settings_config.save_to_json("data/config.json")
        self._settings_dirty = False
        if reason:
            logger.info("설정 저장 완료 (%s)", reason)
        else:
            logger.info("설정 저장 완료")

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
        """팝업 화면 위치 (x, y) - 현재 모니터 기준 중앙 또는 상단 중앙"""
        if self.alert_popup is None:
            return (0, 0)

        popup_width = self.alert_popup.width()
        popup_height = self.alert_popup.height()

        if popup_width <= 0 or popup_height <= 0:
            size_hint = self.alert_popup.sizeHint()
            popup_width = max(popup_width, size_hint.width())
            popup_height = max(popup_height, size_hint.height())

        screen = None

        try:
            window_handle = self.main_window.windowHandle()
            if window_handle is not None:
                screen = window_handle.screen()
        except Exception:
            screen = None

        if screen is None:
            try:
                center_point = self.main_window.frameGeometry().center()
                screen = self.qt_app.screenAt(center_point)
            except Exception:
                screen = None

        if screen is None:
            screen = self.qt_app.primaryScreen()

        screen_geom = screen.availableGeometry()
        x = screen_geom.x() + (screen_geom.width() - popup_width) // 2

        if self.settings_config.popup_position == "top":
            margin_top = 20
            y = screen_geom.y() + margin_top
        else:  # "center" (기본값)
            y = screen_geom.y() + (screen_geom.height() - popup_height) // 2

        return (x, y)

    SCREEN_TITLES = {
        0: "기준 자세 설정",
        1: "바로목",
        2: "환경설정",
        3: "나의 통계",
        4: "자세 감지",
    }

    def switch_screen(self, screen_index: int):
        """
        화면 전환

        Args:
            screen_index: 화면 인덱스
        """
        if 0 <= screen_index < self.main_window.stacked_widget.count():
            self._previous_screen_index = self.main_window.stacked_widget.currentIndex()

            if self._previous_screen_index == 2 and screen_index != 2:
                self._persist_settings_if_dirty(reason="settings_screen_exit")

            # 이전 화면 정리
            if self._previous_screen_index == 0 and screen_index != 0 and hasattr(self, "baseline_screen"):
                try:
                    self.baseline_screen.cancel_capture()
                    if screen_index != 4:
                        self.baseline_screen.pause_camera_preview()
                except Exception:
                    logger.debug("Baseline 화면 이탈 처리 실패")

            if self._previous_screen_index == 4 and screen_index != 4:
                try:
                    if screen_index != 0 and self.camera_worker.isRunning():
                        self.camera_worker.pause()
                except Exception:
                    logger.debug("Detection 화면 이탈 시 카메라 일시정지 실패")

            # 진입 화면 설정
            if screen_index == 0 and hasattr(self, "baseline_screen"):
                try:
                    self.baseline_screen.cancel_capture()
                    self.baseline_screen.start_camera_preview()
                except Exception:
                    logger.debug("Baseline 화면 진입 시 카메라 시작 실패")

            if screen_index == 1:
                self._start_camera_warmup()

            if screen_index == 2 and hasattr(self, "settings_screen"):
                self._refresh_settings_screen_values()

            # 자세 맞춤/설정/통계/감지 화면으로 이동할 때는 뒤로가기 버튼을 노출한다.
            if screen_index in (0, 2, 3, 4):
                try:
                    self.main_window.show_back_header()
                except Exception:
                    logger.debug("헤더를 뒤로가기 모드로 전환하지 못함")
            else:
                try:
                    self.main_window.show_default_header()
                except Exception:
                    logger.debug("헤더를 기본 모드로 전환하지 못함")

            self.main_window.stacked_widget.setCurrentIndex(screen_index)
            self.main_window.set_header_title(
                self.SCREEN_TITLES.get(screen_index, "바로목"),
                show_icon=(screen_index != 1)
            )
            screen_names = ["baseline", "hub", "settings", "statistics", "detection"]
            logger.info("화면 전환: %s", screen_names[screen_index])
        else:
            logger.warning("잘못된 화면 인덱스: %s", screen_index)

    def _handle_header_back(self):
        """헤더의 뒤로가기 버튼 처리: 직전 화면으로 복귀"""
        current_index = self.main_window.stacked_widget.currentIndex()
        if current_index == 0 and hasattr(self, "baseline_screen"):
            try:
                self.baseline_screen.cancel_capture()
                self.baseline_screen.pause_camera_preview()
            except Exception:
                logger.debug("베이스라인 취소 처리 중 오류")

        if current_index == 3:
            self.switch_screen(1)
            return

        if current_index in (0, 4):
            self.switch_screen(1)
            return

        target_index = self._previous_screen_index
        if target_index == 2:
            target_index = 1

        # 감지 화면으로 복귀하는 경우: 카메라 resume + detection 모드
        if target_index == 4 and hasattr(self, "camera_worker"):
            try:
                self.camera_worker.set_baseline_mode(False)
                if not self.camera_worker.isRunning():
                    self.camera_worker.start()
                elif self.camera_worker.is_paused:
                    self.camera_worker.resume()
            except Exception:
                logger.debug("감지 화면 복귀 시 카메라 재개 실패")

        self.switch_screen(target_index)

        if target_index == 4 and hasattr(self, "detection_screen"):
            try:
                self.detection_screen.on_detection_started()
            except Exception:
                logger.debug("감지 화면 재개 처리 중 오류")

    def _start_detection(self):
        """감지 시작"""
        logger.info("감지 시작")

        # Baseline 존재 여부 확인: 없으면 사용자에게 안내하고
        # 확인 시 Baseline 캡처 화면으로 이동하도록 처리
        try:
            baseline_ok = False
            failure_reason = ""

            try:
                baseline_ok = self.baseline_manager.is_baseline_valid()
                if not baseline_ok:
                    failure_reason = "현재 로드된 Baseline이 유효하지 않습니다."
            except Exception as e:
                failure_reason = f"Baseline 검증 중 오류: {str(e)}"
                logger.debug(f"Baseline 검증 예외: {e}", exc_info=True)

            if not baseline_ok:
                # 저장된 baseline 파일이 있는지 시도 로드
                try:
                    loaded = self.baseline_manager.load_baseline_from_file()
                    if loaded:
                        baseline_ok = self.baseline_manager.is_baseline_valid()
                        if baseline_ok:
                            logger.info(
                                "저장된 Baseline 파일로부터 로드 및 유효성 검증 완료"
                            )
                        else:
                            failure_reason = "저장된 기준자세 파일이 유효하지 않습니다."
                    else:
                        failure_reason = "저장된 기준자세 파일을 찾을 수 없습니다."
                        logger.warning(failure_reason)
                except Exception as e:
                    failure_reason = f"Baseline 파일 로드 실패: {str(e)}"
                    logger.warning(failure_reason, exc_info=True)

            if not baseline_ok:
                # 사용자 확인 대화상자 표시
                from PyQt6.QtWidgets import QMessageBox

                msg = QMessageBox(self.main_window)
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setWindowTitle("기준자세설정 필요")
                msg.setText(
                    f"{failure_reason}\n\n"
                    "기준자세설정 화면으로 이동하겠습니다.\n"
                    "'확인'을 누르면 기준자세 설정 화면으로 이동합니다."
                )
                msg.setStandardButtons(
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
                )
                ok_button = msg.button(QMessageBox.StandardButton.Ok)
                cancel_button = msg.button(QMessageBox.StandardButton.Cancel)
                if ok_button is not None:
                    ok_button.setText("확인")
                if cancel_button is not None:
                    cancel_button.setText("취소")
                ret = msg.exec()
                if ret == QMessageBox.StandardButton.Ok:
                    logger.info("사용자가 Baseline 캡처 화면으로 이동하기로 선택")
                    self.switch_screen(0)
                else:
                    logger.info("사용자가 Baseline 캡처 화면 이동을 취소")
                return

            logger.info("Baseline 유효성 확인 완료: 감지 시작 가능")

        except Exception as e:
            logger.error(f"Baseline 확인 중 예상치 못한 오류: {e}", exc_info=True)
            return

        # baseline이 있으면 기존 감지 시작 흐름 실행
        self.camera_worker.set_baseline_mode(False)
        self.state_machine.reset()
        self._hide_alert_popup()
        # 재시작 시 기존 세션이 end_session() 없이 덮어써지는 버그 방지
        if self.session_manager.current_session is not None:
            self.session_manager.end_session()
        self.session_manager.start_session()

        if not self.camera_worker.isRunning():
            self.camera_worker.start()
        elif self.camera_worker.is_paused:
            self.camera_worker.resume()

        self.switch_screen(4)  # DetectionScreen으로 이동
        self.detection_screen.on_detection_started()

    def _start_camera_warmup(self):
        """허브 화면 진입 시 카메라를 백그라운드에서 예열한다."""
        try:
            if not self.camera_worker.isRunning():
                self.camera_worker.set_baseline_mode(False)
                self.camera_worker.start()
                # 2초 후 일시정지 (이미 충분히 예열됨)
                QTimer.singleShot(2000, self._pause_warmup_camera)
                logger.debug("카메라 예열 시작")
            # 이미 running+paused 상태면 그대로 유지 (이미 예열됨)
        except Exception:
            logger.debug("카메라 예열 시작 실패")

    def _pause_warmup_camera(self):
        """예열 완료 후 허브 화면에 있는 경우에만 카메라를 일시정지한다."""
        try:
            current_index = self.main_window.stacked_widget.currentIndex()
            if (current_index == 1
                    and self.camera_worker.isRunning()
                    and not self.camera_worker.is_paused):
                self.camera_worker.pause()
                logger.debug("카메라 예열 완료, 일시정지 상태로 전환")
        except Exception:
            logger.debug("카메라 예열 일시정지 실패")

    def _handle_baseline_captured(self):
        """Baseline 완료 후 다음 동작 처리"""
        if self.settings_config.auto_start_detection:
            logger.info("자동 감지 시작 설정 활성화: 바로 감지 시작")
            self._start_detection()
        else:
            self.switch_screen(1)  # HubScreen으로 이동

    def _apply_recommended_sensitivities(self, fwd: float, rec: float):
        """자세 맞춤 결과에 따른 권장 감도 자동 적용"""
        logger.info(f"권장 감도 자동 적용: 거북목={fwd:.3f}, 기댄자세={rec:.3f}")

        # 설정값 업데이트
        self.settings_config.forward_head_sensitivity = fwd
        self.settings_config.recline_sensitivity = rec

        # [추가] 초기화 시 돌아갈 권장값으로도 저장
        self.settings_config.recommended_forward_head = fwd
        self.settings_config.recommended_recline = rec

        # 엔진 및 UI 즉시 반영
        self._apply_settings()
        self._refresh_settings_screen_values()

        self._settings_dirty = True
        self._persist_settings_if_dirty(force=True, reason="baseline_recommended")

    def _stop_detection(self):
        """감지 중지"""
        logger.info("감지 중지")
        if self.camera_worker.isRunning():
            self.camera_worker.stop_capture()
        self.session_manager.end_session()
        self._hide_alert_popup()
        self.detection_screen.on_detection_stopped()

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

        if event.to_state.value == "warning":
            self._hide_alert_popup()
            return

        alert_type = "danger"
        # 기본 문구
        message_text = "자세가 흐트러졌어요. 바르게 고쳐 앉아 주세요."

        # 확정된 자세의 알림 문구(config의 alert_message, 단일 소스)를 사용
        try:
            confirmed = event.confirmed_posture
            if confirmed:
                msg = self.config.get_posture_alert_message(confirmed)
                if msg:
                    message_text = msg
        except Exception:
            # 실패 시 기본 메시지 유지
            pass

        now = time.time()
        with self._alert_state_lock:
            if (
                alert_type == self._last_alert_type
                and now - self._last_alert_time
                < self.alert_cooldown_seconds  # 프로퍼티 사용
            ):
                return
            self._last_alert_type = alert_type
            self._last_alert_time = now

        self.alert_bridge.alert_requested.emit(alert_type, message_text)

        # 나쁜 자세로 진입했을 때만 경고음을 별도로 1회 재생한다.
        if event.to_state.value == "bad_posture":
            self._play_bad_posture_sound_once()

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

    def _play_alert_sound(self, volume_percent: int):
        """메인 스레드에서 경고음을 재생한다."""
        try:
            self.sound_manager.play_alert(volume_percent)
        except Exception:
            logger.error("경고음 재생 실패", exc_info=True)

    def _hide_alert_popup(self):
        """알림 팝업 숨김"""
        if self.alert_popup is not None:
            self.alert_popup.hide()

    def _play_bad_posture_sound_once(self):
        """BAD_POSTURE 진입 시에만 중복 없이 경고음을 재생한다."""
        logger.info(
            f"sound check: enabled={self.settings_config.sound_enabled}, "
            f"volume={self.settings_config.sound_volume}, "
            f"last_state={self._last_sound_state}"
        )

        if not self.settings_config.sound_enabled:
            logger.info("sound skipped: sound_enabled=False")
            return

        if self.settings_config.sound_volume <= 0:
            logger.info("sound skipped: sound_volume <= 0")
            return

        now = time.time()
        if (
            self._last_sound_state == "bad_posture"
            and now - self._last_sound_time < self._sound_cooldown_seconds
        ):
            logger.info("sound skipped: cooldown")
            return

        self._last_sound_state = "bad_posture"
        self._last_sound_time = now
        logger.info("sound play requested")
        self.alert_bridge.sound_requested.emit(self.settings_config.sound_volume)

    def _save_settings(self, settings_dict: dict):
        """설정 저장"""
        try:
            # 설정값 업데이트
            any_changed = False
            for key, value in settings_dict.items():
                if hasattr(self.settings_config, key) and getattr(self.settings_config, key) != value:
                    setattr(self.settings_config, key, value)
                    any_changed = True

            # 설정값 즉시 적용
            self._apply_settings()

            if any_changed:
                self._settings_dirty = True

            self._persist_settings_if_dirty(force=any_changed, reason="settings_save_signal")

            logger.info(f"설정 저장 완료: {settings_dict}")
        except Exception as e:
            logger.error(f"설정 저장 실패: {e}")

    def _reset_settings(self):
        """설정 초기화 (기본값으로)"""
        try:
            self.settings_config.reset_to_defaults()
            self._refresh_settings_screen_values()

            # 엔진 즉시 반영
            self._apply_settings()
            self._settings_dirty = True
            self._persist_settings_if_dirty(force=True, reason="settings_reset")
            logger.info("설정이 기본값으로 초기화되었습니다.")
        except Exception as e:
            logger.error(f"설정 초기화 실패: {e}")

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
        logger.info(
            f"  - 거북목 감도: {self.settings_config.forward_head_sensitivity:.3f}"
        )
        logger.info(
            f"  - 기댄자세 감도: {self.settings_config.recline_sensitivity:.3f}"
        )

        # 판정 엔진에 감도 업데이트
        self.judgment_engine.update_sensitivities(
            self.settings_config.forward_head_sensitivity,
            self.settings_config.recline_sensitivity,
        )

        if not self.settings_config.notification_enabled:
            self.alert_hide_timer.stop()
            self._hide_alert_popup()

    def _test_sound_now(self):
        """설정 화면에서 현재 볼륨으로 알림음을 즉시 테스트한다."""
        try:
            self.sound_manager.play_alert(self.settings_config.sound_volume)
        except Exception as e:
            logger.error(f"소리 테스트 실패: {e}", exc_info=True)

        # 사운드 관련 설정 변경 시 SoundManager에 즉시 반영
        try:
            if hasattr(self, "sound_manager"):
                self.sound_manager.set_volume_percent(self.settings_config.sound_volume)
        except Exception:
            logger.debug("사운드 설정 반영 실패")

    def _on_settings_widget_changed(self, value_dict: dict):
        """Settings 위젯의 value_changed_signal을 처리하여 변경을 즉시 반영합니다."""
        try:
            # settings_config에 반영 (메모리상의 설정)
            any_changed = False
            for k, v in value_dict.items():
                if hasattr(self.settings_config, k) and getattr(self.settings_config, k) != v:
                    setattr(self.settings_config, k, v)
                    any_changed = True

            if any_changed:
                self._apply_settings()
                self._settings_dirty = True

            # 사운드 관련 변경은 즉시 SoundManager에 반영
            if "sound_volume" in value_dict and hasattr(self, "sound_manager"):
                try:
                    self.sound_manager.set_volume_percent(
                        self.settings_config.sound_volume
                    )
                except Exception:
                    logger.debug("사운드 볼륨 실시간 반영 실패")

            if "sound_enabled" in value_dict:
                # 알림음 비활성화 시 타이머/사운드 정리
                if not self.settings_config.sound_enabled:
                    self._hide_alert_popup()

        except Exception as e:
            logger.error(f"설정 위젯 변경 처리 실패: {e}", exc_info=True)

    def run(self):
        """애플리케이션 실행"""
        logger.info("애플리케이션 실행")
        self.main_window.show()

        # 앱 실행 중에는 주기적으로 저장하거나 종료 시 저장
        # PyQt 종료 시점 처리를 위해 exec_ 호출 후 저장
        exit_code = self.qt_app.exec()

        # 종료 시 카메라 완전 정지
        try:
            if self.camera_worker.isRunning():
                self.camera_worker.stop_capture()
        except Exception:
            logger.debug("종료 시 카메라 정지 실패")

        # 종료 시 진행 중인 세션을 정상 종료 처리 (end_time/통계 저장)
        try:
            if self.session_manager.current_session is not None:
                self.session_manager.end_session()
        except Exception:
            logger.debug("종료 시 세션 종료 실패")

        # 종료 전 설정 최종 저장 (dirty일 때만)
        self._persist_settings_if_dirty(reason="app_exit")

        # DB 연결 종료
        try:
            self.session_manager.close()
        except Exception:
            logger.debug("종료 시 DB 연결 닫기 실패")

        return exit_code