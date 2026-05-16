"""설정 화면 위젯 모듈

카테고리별 상세 설정 UI 컴포넌트
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QSlider,
    QRadioButton,
    QButtonGroup,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import logging

from src.ui.styles.theme import Colors, ThemeManager

logger = logging.getLogger(__name__)


class NotificationSettingsWidget(QWidget):
    """알림 설정 위젯: 토글 + 슬라이더"""

    value_changed_signal = pyqtSignal(dict)

    def __init__(self, theme_manager: ThemeManager, initial_config: dict = None):
        super().__init__()
        self.theme_manager = theme_manager
        self.config = initial_config or {}
        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)
        self.setObjectName("settings_card")
        self.setStyleSheet(
            f"#settings_card {{ background-color: {Colors.WHITE.value}; border: 1px solid #E3E0F2; border-radius: 12px; }}"
        )

        # 토글 섹션
        toggle_layout = QHBoxLayout()
        toggle_label = QLabel("나쁜 자세 감지 알림")
        toggle_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(12)))

        self.toggle = QCheckBox()
        self.toggle.setChecked(self.config.get("notification_enabled", True))
        self.toggle.stateChanged.connect(self._on_toggle_changed)

        toggle_layout.addWidget(toggle_label)
        toggle_layout.addStretch()
        toggle_layout.addWidget(self.toggle)
        layout.addLayout(toggle_layout)

        # 슬라이더 섹션
        slider_layout = QVBoxLayout()
        slider_layout.setSpacing(12)

        # 슬라이더 헤더 (라벨 + 현재값)
        header_layout = QHBoxLayout()
        slider_label = QLabel("알림 간격")
        slider_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(11)))

        self.value_label = QLabel("30초")
        self.value_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(11), QFont.Weight.Bold)
        )
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        header_layout.addWidget(slider_label)
        header_layout.addStretch()
        header_layout.addWidget(self.value_label)
        slider_layout.addLayout(header_layout)

        # 슬라이더
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(5)
        self.slider.setMaximum(60)
        self.slider.setValue(self.config.get("notification_interval", 30))
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(5)
        self.slider.setSingleStep(1)
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.slider)

        # 슬라이더 범위 표시
        range_layout = QHBoxLayout()
        min_label = QLabel("5초")
        min_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(10)))
        max_label = QLabel("60초")
        max_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(10)))
        range_layout.addWidget(min_label)
        range_layout.addStretch()
        range_layout.addWidget(max_label)
        slider_layout.addLayout(range_layout)

        layout.addLayout(slider_layout)

        self.setLayout(layout)

        # 초기 상태 설정
        self._sync_slider_state()

    def _on_toggle_changed(self):
        """토글 변경 시"""
        self._sync_slider_state()
        self._emit_value_changed()

    def _on_slider_changed(self, value: int):
        """슬라이더 변경 시"""
        self.value_label.setText(f"{value}초")
        self._emit_value_changed()

    def _sync_slider_state(self):
        """토글 상태에 따라 슬라이더 활성화/비활성화"""
        is_enabled = self.toggle.isChecked()
        self.slider.setEnabled(is_enabled)
        self.value_label.setEnabled(is_enabled)

    def _emit_value_changed(self):
        """값 변경 신호 발생"""
        self.value_changed_signal.emit(
            {
                "notification_enabled": self.toggle.isChecked(),
                "notification_interval": self.slider.value(),
            }
        )

    def get_value(self) -> dict:
        """현재 설정값 반환"""
        return {
            "notification_enabled": self.toggle.isChecked(),
            "notification_interval": self.slider.value(),
        }

    def set_value(self, config: dict):
        """설정값 설정"""
        self.toggle.setChecked(config.get("notification_enabled", True))
        self.slider.setValue(config.get("notification_interval", 30))
        self.value_label.setText(f"{self.slider.value()}초")
        self._sync_slider_state()


class SoundSettingsWidget(QWidget):
    """소리 설정 위젯: 토글 + 슬라이더"""

    value_changed_signal = pyqtSignal(dict)

    def __init__(self, theme_manager: ThemeManager, initial_config: dict = None):
        super().__init__()
        self.theme_manager = theme_manager
        self.config = initial_config or {}
        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # 토글
        toggle_layout = QHBoxLayout()
        toggle_label = QLabel("알림음 활성화")
        toggle_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(12)))

        self.toggle = QCheckBox()
        self.toggle.setChecked(self.config.get("sound_enabled", True))
        self.toggle.stateChanged.connect(self._on_toggle_changed)

        toggle_layout.addWidget(toggle_label)
        toggle_layout.addStretch()
        toggle_layout.addWidget(self.toggle)
        layout.addLayout(toggle_layout)

        # 슬라이더
        slider_layout = QVBoxLayout()
        slider_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        slider_label = QLabel("소리 크기")
        slider_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(11)))

        self.volume_label = QLabel("70%")
        self.volume_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(11), QFont.Weight.Bold)
        )
        self.volume_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        header_layout.addWidget(slider_label)
        header_layout.addStretch()
        header_layout.addWidget(self.volume_label)
        slider_layout.addLayout(header_layout)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(self.config.get("sound_volume", 70))
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(10)
        self.slider.setSingleStep(1)
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.slider)

        range_layout = QHBoxLayout()
        min_label = QLabel("음소거")
        min_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(10)))
        max_label = QLabel("최대")
        max_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(10)))
        range_layout.addWidget(min_label)
        range_layout.addStretch()
        range_layout.addWidget(max_label)
        slider_layout.addLayout(range_layout)

        layout.addLayout(slider_layout)

        self.setLayout(layout)
        self._sync_slider_state()

    def _on_toggle_changed(self):
        """토글 변경 시"""
        self._sync_slider_state()
        self._emit_value_changed()

    def _on_slider_changed(self, value: int):
        """슬라이더 변경 시"""
        self.volume_label.setText(f"{value}%")
        self._emit_value_changed()

    def _sync_slider_state(self):
        """토글 상태에 따라 슬라이더 활성화/비활성화"""
        is_enabled = self.toggle.isChecked()
        self.slider.setEnabled(is_enabled)
        self.volume_label.setEnabled(is_enabled)

    def _emit_value_changed(self):
        """값 변경 신호 발생"""
        self.value_changed_signal.emit(
            {
                "sound_enabled": self.toggle.isChecked(),
                "sound_volume": self.slider.value(),
            }
        )

    def get_value(self) -> dict:
        """현재 설정값 반환"""
        return {
            "sound_enabled": self.toggle.isChecked(),
            "sound_volume": self.slider.value(),
        }

    def set_value(self, config: dict):
        """설정값 설정"""
        self.toggle.setChecked(config.get("sound_enabled", True))
        self.slider.setValue(config.get("sound_volume", 70))
        self.volume_label.setText(f"{self.slider.value()}%")
        self._sync_slider_state()


class PopupSettingsWidget(QWidget):
    """팝업 설정 위젯: 라디오 + 토글 + 슬라이더"""

    value_changed_signal = pyqtSignal(dict)

    def __init__(self, theme_manager: ThemeManager, initial_config: dict = None):
        super().__init__()
        self.theme_manager = theme_manager
        self.config = initial_config or {}
        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # 팝업 위치 선택 (라디오)
        position_label = QLabel("팝업 표시 위치")
        position_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(12), QFont.Weight.Bold)
        )
        position_label.setStyleSheet(f"color: {Colors.PURPLE_PRIMARY.value};")
        layout.addWidget(position_label)

        self.position_group = QButtonGroup()
        position_layout = QHBoxLayout()
        position_layout.setSpacing(20)

        self.radio_center = QRadioButton("화면 중앙")
        self.radio_center.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(11))
        )
        self._apply_radio_button_style(self.radio_center)

        self.radio_top = QRadioButton("화면 상단")
        self.radio_top.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(11))
        )
        self._apply_radio_button_style(self.radio_top)

        self.position_group.addButton(self.radio_center, 0)
        self.position_group.addButton(self.radio_top, 1)

        if self.config.get("popup_position", "center") == "center":
            self.radio_center.setChecked(True)
        else:
            self.radio_top.setChecked(True)

        self.position_group.buttonClicked.connect(self._emit_value_changed)

        position_layout.addWidget(self.radio_center)
        position_layout.addWidget(self.radio_top)
        position_layout.addStretch()
        layout.addLayout(position_layout)

        # 팝업 자동 닫기 (토글 + 슬라이더)
        auto_close_layout = QHBoxLayout()
        auto_close_label = QLabel("팝업 자동 닫기")
        auto_close_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(12))
        )
        auto_close_label.setStyleSheet(f"color: {Colors.PURPLE_PRIMARY.value};")

        self.auto_close_toggle = QCheckBox()
        self.auto_close_toggle.setChecked(self.config.get("popup_auto_close", True))
        self.auto_close_toggle.stateChanged.connect(self._on_auto_close_toggled)

        auto_close_layout.addWidget(auto_close_label)
        auto_close_layout.addStretch()
        auto_close_layout.addWidget(self.auto_close_toggle)
        layout.addLayout(auto_close_layout)

        # 자동 닫기 시간 슬라이더
        time_slider_layout = QVBoxLayout()
        time_slider_layout.setSpacing(12)

        time_header_layout = QHBoxLayout()
        time_label = QLabel("자동 닫기 시간")
        time_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(11)))
        time_label.setStyleSheet(f"color: {Colors.PURPLE_PRIMARY.value};")

        self.time_value_label = QLabel("5초")
        self.time_value_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(11), QFont.Weight.Bold)
        )
        self.time_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        time_header_layout.addWidget(time_label)
        time_header_layout.addStretch()
        time_header_layout.addWidget(self.time_value_label)
        time_slider_layout.addLayout(time_header_layout)

        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setMinimum(3)
        self.time_slider.setMaximum(10)
        self.time_slider.setValue(self.config.get("popup_auto_close_time", 5))
        self.time_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.time_slider.setTickInterval(1)
        self.time_slider.setSingleStep(1)
        self.time_slider.valueChanged.connect(self._on_time_slider_changed)
        time_slider_layout.addWidget(self.time_slider)

        time_range_layout = QHBoxLayout()
        time_min = QLabel("3초")
        time_min.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(10)))
        time_max = QLabel("10초")
        time_max.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(10)))
        time_range_layout.addWidget(time_min)
        time_range_layout.addStretch()
        time_range_layout.addWidget(time_max)
        time_slider_layout.addLayout(time_range_layout)

        layout.addLayout(time_slider_layout)

        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._sync_time_slider_state()

    def _on_auto_close_toggled(self):
        """자동 닫기 토글 변경"""
        self._sync_time_slider_state()
        self._emit_value_changed()

    def _on_time_slider_changed(self, value: int):
        """시간 슬라이더 변경"""
        self.time_value_label.setText(f"{value}초")
        self._emit_value_changed()

    def _sync_time_slider_state(self):
        """토글 상태에 따라 시간 슬라이더 활성화/비활성화"""
        is_enabled = self.auto_close_toggle.isChecked()
        self.time_slider.setEnabled(is_enabled)
        self.time_value_label.setEnabled(is_enabled)

    def _apply_radio_button_style(self, radio_button: QRadioButton):
        """라디오 버튼에 커스텀 스타일 적용"""
        stylesheet = """
            QRadioButton {
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
            }
            QRadioButton::indicator:unchecked {
                background-color: white;
                border: 2px solid #8B7BA8;
            }
            QRadioButton::indicator:checked {
                background-color: #7B68A6;
                border: 2px solid #7B68A6;
            }
        """
        radio_button.setStyleSheet(stylesheet)

    def _emit_value_changed(self):
        """값 변경 신호 발생"""
        self.value_changed_signal.emit(
            {
                "popup_position": (
                    "center" if self.radio_center.isChecked() else "top"
                ),
                "popup_auto_close": self.auto_close_toggle.isChecked(),
                "popup_auto_close_time": self.time_slider.value(),
            }
        )

    def get_value(self) -> dict:
        """현재 설정값 반환"""
        return {
            "popup_position": ("center" if self.radio_center.isChecked() else "top"),
            "popup_auto_close": self.auto_close_toggle.isChecked(),
            "popup_auto_close_time": self.time_slider.value(),
        }

    def set_value(self, config: dict):
        """설정값 설정"""
        position = config.get("popup_position", "center")
        if position == "center":
            self.radio_center.setChecked(True)
        else:
            self.radio_top.setChecked(True)

        self.auto_close_toggle.setChecked(config.get("popup_auto_close", True))
        self.time_slider.setValue(config.get("popup_auto_close_time", 5))
        self.time_value_label.setText(f"{self.time_slider.value()}초")
        self._sync_time_slider_state()


class AutoStartSettingsWidget(QWidget):
    """자동 시작 설정 위젯: 토글"""

    value_changed_signal = pyqtSignal(dict)

    def __init__(self, theme_manager: ThemeManager, initial_config: dict = None):
        super().__init__()
        self.theme_manager = theme_manager
        self.config = initial_config or {}
        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)
        self.setObjectName("settings_card")
        self.setStyleSheet(
            f"#settings_card {{ background-color: {Colors.WHITE.value}; border: 1px solid #E3E0F2; border-radius: 12px; }}"
        )

        # 토글
        toggle_layout = QHBoxLayout()
        toggle_label = QLabel("프로그램 시작 시 감지 자동 시작")
        toggle_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(12)))
        toggle_label.setStyleSheet(f"color: {Colors.PURPLE_PRIMARY.value};")

        self.toggle = QCheckBox()
        self.toggle.setChecked(self.config.get("auto_start_detection", False))
        self.toggle.stateChanged.connect(self._emit_value_changed)

        toggle_layout.addWidget(toggle_label)
        toggle_layout.addStretch()
        toggle_layout.addWidget(self.toggle)
        layout.addLayout(toggle_layout)

        # 설명
        description = QLabel(
            "프로그램 시작 후 Baseline을 완료하면\n" "자동으로 자세 감지가 시작됩니다."
        )
        description.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(10)))
        description.setStyleSheet(f"color: {Colors.GRAY_DARK.value};")
        layout.addWidget(description)

        self.setLayout(layout)

    def _emit_value_changed(self):
        """값 변경 신호 발생"""
        self.value_changed_signal.emit(
            {
                "auto_start_detection": self.toggle.isChecked(),
            }
        )

    def get_value(self) -> dict:
        """현재 설정값 반환"""
        return {
            "auto_start_detection": self.toggle.isChecked(),
        }

    def set_value(self, config: dict):
        """설정값 설정"""
        self.toggle.setChecked(config.get("auto_start_detection", False))
