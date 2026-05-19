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
    QButtonGroup,
    QSizePolicy,
    QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPainter, QColor
import logging

from src.ui.styles.theme import Colors, ThemeManager
from src.ui.styles.font_loader import app_font

logger = logging.getLogger(__name__)

# 비대화형 텍스트 요소(라벨, 수치 표시)용 — 테두리/배경 제거
FLAT_LABEL_STYLE = "border: none; background-color: transparent;"

# 슬라이더 — 테두리 없는 깔끔한 스타일
SLIDER_STYLE = """
    QSlider {
        border: none;
        background: transparent;
    }
    QSlider::groove:horizontal {
        height: 6px;
        background: #E3E0F2;
        border: none;
        border-radius: 3px;
    }
    QSlider::sub-page:horizontal {
        background: #4333A6;
        border: none;
        border-radius: 3px;
    }
    QSlider::add-page:horizontal {
        background: #E3E0F2;
        border: none;
        border-radius: 3px;
    }
    QSlider::handle:horizontal {
        width: 16px;
        height: 16px;
        margin: -6px 0;
        background: #4333A6;
        border: 3px solid #FFFFFF;
        border-radius: 9px;
    }
    QSlider::handle:horizontal:hover {
        background: #5343B6;
    }
    QSlider:disabled {
        background: transparent;
    }
    QSlider::sub-page:horizontal:disabled {
        background: #CCCCCC;
    }
    QSlider::handle:horizontal:disabled {
        background: #CCCCCC;
    }
"""


class ToggleSwitch(QCheckBox):
    """슬라이딩 토글 스위치 (QCheckBox API 유지: isChecked/setChecked/stateChanged)"""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        scale = theme_manager.scale_pixel
        self._w = scale(52)
        self._h = scale(28)
        self.setFixedSize(self._w, self._h)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(self._w, self._h)

    def hitButton(self, pos) -> bool:
        # 위젯 전체 영역을 클릭 가능 영역으로
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        radius = h / 2

        # 트랙
        track = QColor("#4333A6") if self.isChecked() else QColor("#CCCCCC")
        if not self.isEnabled():
            track = QColor("#E0E0E0")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(0, 0, w, h, radius, radius)

        # 핸들
        margin = 3
        diameter = h - margin * 2
        x = w - diameter - margin if self.isChecked() else margin
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(int(x), margin, diameter, diameter)


class NoWheelSlider(QSlider):
    """마우스 휠 이벤트를 무시하는 슬라이더

    슬라이더 위에서 휠을 굴려도 값이 바뀌지 않고,
    이벤트가 상위 스크롤 영역으로 전달되어 화면만 스크롤된다.
    값은 클릭 후 드래그로만 변경된다.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 포커스 사각형(테두리) 제거
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(SLIDER_STYLE)

    def wheelEvent(self, event):
        event.ignore()


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
        layout.setContentsMargins(11, 10, 11, 10)
        layout.setSpacing(10)
        self.setObjectName("settings_card")
        self.setStyleSheet(
            f"#settings_card {{ background-color: {Colors.WHITE.value}; border: 1px solid #E3E0F2; border-radius: 12px; }}"
        )

        # 토글 섹션
        toggle_layout = QHBoxLayout()
        toggle_label = QLabel("나쁜 자세 감지 알림")
        toggle_label.setFont(app_font(self.theme_manager.scale_pixel(14)))
        toggle_label.setStyleSheet(FLAT_LABEL_STYLE)

        self.toggle = ToggleSwitch(self.theme_manager)
        self.toggle.setChecked(self.config.get("notification_enabled", True))
        self.toggle.stateChanged.connect(self._on_toggle_changed)

        toggle_layout.addWidget(toggle_label)
        toggle_layout.addStretch()
        toggle_layout.addWidget(self.toggle)
        layout.addLayout(toggle_layout)

        # 슬라이더 섹션
        slider_layout = QVBoxLayout()
        slider_layout.setSpacing(6)

        # 슬라이더 헤더 (라벨 + 현재값)
        header_layout = QHBoxLayout()
        slider_label = QLabel("알림 간격")
        slider_label.setFont(app_font(self.theme_manager.scale_pixel(13)))
        slider_label.setStyleSheet(FLAT_LABEL_STYLE)

        self.value_label = QLabel("30초")
        self.value_label.setFont(
            app_font(self.theme_manager.scale_pixel(13), QFont.Weight.Bold)
        )
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.value_label.setStyleSheet(FLAT_LABEL_STYLE)

        header_layout.addWidget(slider_label)
        header_layout.addStretch()
        header_layout.addWidget(self.value_label)
        slider_layout.addLayout(header_layout)

        # 슬라이더
        self.slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(5)
        self.slider.setMaximum(60)
        self.slider.setValue(self.config.get("notification_interval", 30))
        self.slider.setSingleStep(1)
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.slider)

        # 슬라이더 범위 표시
        range_layout = QHBoxLayout()
        min_label = QLabel("5초")
        min_label.setFont(app_font(self.theme_manager.scale_pixel(12)))
        min_label.setStyleSheet(FLAT_LABEL_STYLE)
        max_label = QLabel("60초")
        max_label.setFont(app_font(self.theme_manager.scale_pixel(12)))
        max_label.setStyleSheet(FLAT_LABEL_STYLE)
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
    test_requested_signal = pyqtSignal()

    def __init__(self, theme_manager: ThemeManager, initial_config: dict = None):
        super().__init__()
        self.theme_manager = theme_manager
        self.config = initial_config or {}
        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(11, 10, 11, 10)
        layout.setSpacing(10)

        # 토글
        toggle_layout = QHBoxLayout()
        toggle_label = QLabel("알림음 활성화")
        toggle_label.setFont(app_font(self.theme_manager.scale_pixel(14)))
        toggle_label.setStyleSheet(FLAT_LABEL_STYLE)

        self.toggle = ToggleSwitch(self.theme_manager)
        self.toggle.setChecked(self.config.get("sound_enabled", True))
        self.toggle.stateChanged.connect(self._on_toggle_changed)

        toggle_layout.addWidget(toggle_label)
        toggle_layout.addStretch()
        toggle_layout.addWidget(self.toggle)
        layout.addLayout(toggle_layout)

        # 슬라이더
        slider_layout = QVBoxLayout()
        slider_layout.setSpacing(6)

        header_layout = QHBoxLayout()
        slider_label = QLabel("소리 크기")
        slider_label.setFont(app_font(self.theme_manager.scale_pixel(13)))
        slider_label.setStyleSheet(FLAT_LABEL_STYLE)

        self.volume_label = QLabel("70%")
        self.volume_label.setFont(
            app_font(self.theme_manager.scale_pixel(13), QFont.Weight.Bold)
        )
        self.volume_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.volume_label.setStyleSheet(FLAT_LABEL_STYLE)

        header_layout.addWidget(slider_label)
        header_layout.addStretch()
        header_layout.addWidget(self.volume_label)
        slider_layout.addLayout(header_layout)

        self.slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(self.config.get("sound_volume", 70))
        self.slider.setSingleStep(1)
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.slider)

        range_layout = QHBoxLayout()
        min_label = QLabel("음소거")
        min_label.setFont(app_font(self.theme_manager.scale_pixel(12)))
        min_label.setStyleSheet(FLAT_LABEL_STYLE)
        max_label = QLabel("최대")
        max_label.setFont(app_font(self.theme_manager.scale_pixel(12)))
        max_label.setStyleSheet(FLAT_LABEL_STYLE)
        range_layout.addWidget(min_label)
        range_layout.addStretch()
        range_layout.addWidget(max_label)
        slider_layout.addLayout(range_layout)

        self.test_btn = QPushButton("소리 테스트")
        self.test_btn.setFixedHeight(self.theme_manager.scale_pixel(36))
        self.test_btn.clicked.connect(lambda _checked=False: self.test_requested_signal.emit())
        self.test_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {Colors.WHITE.value};
                color: {Colors.PURPLE_PRIMARY.value};
                border: 1px solid {Colors.PURPLE_PRIMARY.value};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: #F4F0FF;
            }}
        """
        )
        slider_layout.addWidget(self.test_btn)

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
        # 사용자가 소리 활성화를 끄더라도 슬라이더는 조절할 수 있게 둡니다.
        # 실제 재생 여부는 앱 레이어에서 `sound_enabled`를 확인하여 처리합니다.
        self.slider.setEnabled(True)
        self.volume_label.setEnabled(True)

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
        layout.setContentsMargins(11, 2, 11, 10)
        layout.setSpacing(10)

        # 팝업 위치 선택 — 라벨과 버튼을 좁은 간격으로 묶음
        position_section = QVBoxLayout()
        position_section.setContentsMargins(0, 0, 0, 0)
        position_section.setSpacing(3)

        position_label = QLabel("팝업 표시 위치")
        position_label.setFont(
            app_font(self.theme_manager.scale_pixel(14), QFont.Weight.Bold)
        )
        position_label.setStyleSheet(
            f"color: {Colors.PURPLE_PRIMARY.value}; {FLAT_LABEL_STYLE}"
        )
        position_section.addWidget(position_label)

        self.position_group = QButtonGroup()
        self.position_group.setExclusive(True)
        position_layout = QHBoxLayout()
        position_layout.setSpacing(8)

        self.radio_center = self._create_segment_button("화면 중앙")
        self.radio_top = self._create_segment_button("화면 상단")

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
        position_section.addLayout(position_layout)
        layout.addLayout(position_section)

        # 팝업 자동 닫기 (토글 + 슬라이더)
        auto_close_layout = QHBoxLayout()
        auto_close_label = QLabel("팝업 자동 닫기")
        auto_close_label.setFont(
            app_font(self.theme_manager.scale_pixel(14))
        )
        auto_close_label.setStyleSheet(
            f"color: {Colors.PURPLE_PRIMARY.value}; {FLAT_LABEL_STYLE}"
        )

        self.auto_close_toggle = ToggleSwitch(self.theme_manager)
        self.auto_close_toggle.setChecked(self.config.get("popup_auto_close", True))
        self.auto_close_toggle.stateChanged.connect(self._on_auto_close_toggled)

        auto_close_layout.addWidget(auto_close_label)
        auto_close_layout.addStretch()
        auto_close_layout.addWidget(self.auto_close_toggle)
        layout.addLayout(auto_close_layout)

        # 자동 닫기 시간 슬라이더
        time_slider_layout = QVBoxLayout()
        time_slider_layout.setSpacing(6)

        time_header_layout = QHBoxLayout()
        time_label = QLabel("자동 닫기 시간")
        time_label.setFont(app_font(self.theme_manager.scale_pixel(13)))
        time_label.setStyleSheet(
            f"color: {Colors.PURPLE_PRIMARY.value}; {FLAT_LABEL_STYLE}"
        )

        self.time_value_label = QLabel("5초")
        self.time_value_label.setFont(
            app_font(self.theme_manager.scale_pixel(13), QFont.Weight.Bold)
        )
        self.time_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.time_value_label.setStyleSheet(FLAT_LABEL_STYLE)

        time_header_layout.addWidget(time_label)
        time_header_layout.addStretch()
        time_header_layout.addWidget(self.time_value_label)
        time_slider_layout.addLayout(time_header_layout)

        self.time_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.time_slider.setMinimum(3)
        self.time_slider.setMaximum(10)
        self.time_slider.setValue(self.config.get("popup_auto_close_time", 5))
        self.time_slider.setSingleStep(1)
        self.time_slider.valueChanged.connect(self._on_time_slider_changed)
        time_slider_layout.addWidget(self.time_slider)

        time_range_layout = QHBoxLayout()
        time_min = QLabel("3초")
        time_min.setFont(app_font(self.theme_manager.scale_pixel(12)))
        time_min.setStyleSheet(FLAT_LABEL_STYLE)
        time_max = QLabel("10초")
        time_max.setFont(app_font(self.theme_manager.scale_pixel(12)))
        time_max.setStyleSheet(FLAT_LABEL_STYLE)
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

    def _create_segment_button(self, text: str) -> QPushButton:
        """팝업 위치 선택용 세그먼트(필) 버튼 생성"""
        scale = self.theme_manager.scale_pixel
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFont(app_font(scale(13), QFont.Weight.Bold))
        btn.setFixedHeight(scale(42))
        btn.setMinimumWidth(scale(130))
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #F0EDFF;
                color: {Colors.PURPLE_PRIMARY.value};
                border: none;
                border-radius: {scale(12)}px;
                padding: {scale(8)}px {scale(20)}px;
            }}
            QPushButton:hover {{
                background-color: #E3DCFF;
            }}
            QPushButton:checked {{
                background-color: {Colors.PURPLE_PRIMARY.value};
                color: {Colors.WHITE.value};
            }}
        """)
        return btn

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
        layout.setContentsMargins(11, 10, 11, 10)
        layout.setSpacing(10)
        self.setObjectName("settings_card")
        self.setStyleSheet(
            f"#settings_card {{ background-color: {Colors.WHITE.value}; border: 1px solid #E3E0F2; border-radius: 12px; }}"
        )

        # 토글
        toggle_layout = QHBoxLayout()
        toggle_label = QLabel("프로그램 시작 시 감지 자동 시작")
        toggle_label.setFont(app_font(self.theme_manager.scale_pixel(14)))
        toggle_label.setStyleSheet(
            f"color: {Colors.PURPLE_PRIMARY.value}; {FLAT_LABEL_STYLE}"
        )

        self.toggle = ToggleSwitch(self.theme_manager)
        self.toggle.setChecked(self.config.get("auto_start_detection", False))
        self.toggle.stateChanged.connect(self._emit_value_changed)

        toggle_layout.addWidget(toggle_label)
        toggle_layout.addStretch()
        toggle_layout.addWidget(self.toggle)
        layout.addLayout(toggle_layout)

        # 설명
        description = QLabel(
            "프로그램 시작 후 Baseline을 완료하면 자동으로 자세 감지가 시작됩니다."
        )
        description.setFont(app_font(self.theme_manager.scale_pixel(12)))
        description.setStyleSheet(
            f"color: {Colors.GRAY_DARK.value}; {FLAT_LABEL_STYLE}"
        )
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


class SensitivitySettingsWidget(QWidget):
    """민감도 설정 위젯: 슬라이더로 조절"""

    value_changed_signal = pyqtSignal(dict)
    reset_requested_signal = pyqtSignal()

    # 감도 범위
    FWD_MIN, FWD_MAX = 0.03, 0.07
    REC_MIN, REC_MAX = 0.01, 0.03

    def __init__(self, theme_manager: ThemeManager, initial_config: dict = None):
        super().__init__()
        self.theme_manager = theme_manager
        self.config = initial_config or {}

        # 현재 값 (설정 파일에서 로드, 범위 내로 클램프)
        self.fwd_val = self._clamp(
            self.config.get("forward_head_sensitivity", 0.05),
            self.FWD_MIN, self.FWD_MAX,
        )
        self.rec_val = self._clamp(
            self.config.get("recline_sensitivity", 0.02),
            self.REC_MIN, self.REC_MAX,
        )

        self.setup_ui()

    @staticmethod
    def _clamp(val: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, val))

    @staticmethod
    def _to_slider(val: float, lo: float, hi: float) -> int:
        """실수값 → 슬라이더 위치(0~100)"""
        val = max(lo, min(hi, val))
        return round((val - lo) / (hi - lo) * 100)

    @staticmethod
    def _from_slider(pos: int, lo: float, hi: float) -> float:
        """슬라이더 위치(0~100) → 실수값"""
        return lo + (pos / 100.0) * (hi - lo)

    def setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(11, 10, 11, 10)
        layout.setSpacing(9)

        self.setObjectName("settings_card")
        self.setStyleSheet(
            f"#settings_card {{ background-color: {Colors.WHITE.value}; border: 1px solid #E3E0F2; border-radius: 12px; }}"
        )

        # 상단 헤더 (제목 + 초기화 버튼)
        header_layout = QHBoxLayout()
        title_main = QLabel("정밀 감지 설정")
        title_main.setFont(app_font(self.theme_manager.scale_pixel(15), QFont.Weight.Bold))
        title_main.setStyleSheet(
            f"color: {Colors.PURPLE_PRIMARY.value}; {FLAT_LABEL_STYLE}"
        )

        self.reset_btn = QPushButton("감도 초기화")
        self.reset_btn.setFixedSize(self.theme_manager.scale_pixel(120), self.theme_manager.scale_pixel(40))
        self.reset_btn.setFont(app_font(self.theme_manager.scale_pixel(12), QFont.Weight.Bold))
        self.reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PURPLE_PRIMARY.value};
                color: {Colors.WHITE.value};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #5343B6;
            }}
        """)
        self.reset_btn.clicked.connect(self.reset_requested_signal.emit)

        header_layout.addWidget(title_main)
        header_layout.addStretch()
        header_layout.addWidget(self.reset_btn)
        layout.addLayout(header_layout)

        # 거북목 감도 슬라이더
        self.fwd_slider, self.fwd_label = self._create_slider_row(
            "거북목 감도 (낮을수록 민감)",
            self.fwd_val, self.FWD_MIN, self.FWD_MAX,
            self._on_fwd_slider_changed,
        )
        layout.addLayout(self._last_row_layout)

        # 기댄 자세 감도 슬라이더
        self.rec_slider, self.rec_label = self._create_slider_row(
            "기댄 자세 감도 (낮을수록 민감)",
            self.rec_val, self.REC_MIN, self.REC_MAX,
            self._on_rec_slider_changed,
        )
        layout.addLayout(self._last_row_layout)

        # 설명
        description = QLabel(
            "값이 낮을수록 작은 변화에도 알림이 발생하며,\n높을수록 확실한 변화가 있을 때만 알림이 발생합니다."
        )
        description.setFont(app_font(self.theme_manager.scale_pixel(12)))
        description.setStyleSheet(
            f"color: {Colors.GRAY_DARK.value}; {FLAT_LABEL_STYLE}"
        )
        layout.addWidget(description)

        self.setLayout(layout)

    def _create_slider_row(self, title, initial_val, lo, hi, on_changed):
        """슬라이더 조절 행 생성

        반환: (slider, value_label) — 행 레이아웃은 self._last_row_layout에 저장
        """
        row_layout = QVBoxLayout()
        row_layout.setSpacing(5)

        # 헤더 (제목 + 현재 수치)
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setFont(app_font(self.theme_manager.scale_pixel(14), QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: #1A1A1A; {FLAT_LABEL_STYLE}")

        value_label = QLabel(f"{initial_val:.3f}")
        value_label.setFont(app_font(self.theme_manager.scale_pixel(14), QFont.Weight.Bold))
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        value_label.setStyleSheet(f"color: #4333A6; {FLAT_LABEL_STYLE}")

        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(value_label)
        row_layout.addLayout(header)

        # 슬라이더
        slider = NoWheelSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(self._to_slider(initial_val, lo, hi))
        slider.setSingleStep(1)
        slider.valueChanged.connect(on_changed)
        row_layout.addWidget(slider)

        # 범위 표시 (0 / 100)
        range_layout = QHBoxLayout()
        min_label = QLabel("0")
        min_label.setFont(app_font(self.theme_manager.scale_pixel(12)))
        min_label.setStyleSheet(FLAT_LABEL_STYLE)
        max_label = QLabel("100")
        max_label.setFont(app_font(self.theme_manager.scale_pixel(12)))
        max_label.setStyleSheet(FLAT_LABEL_STYLE)
        range_layout.addWidget(min_label)
        range_layout.addStretch()
        range_layout.addWidget(max_label)
        row_layout.addLayout(range_layout)

        self._last_row_layout = row_layout
        return slider, value_label

    def _on_fwd_slider_changed(self, pos: int):
        self.fwd_val = self._from_slider(pos, self.FWD_MIN, self.FWD_MAX)
        self.fwd_label.setText(f"{self.fwd_val:.3f}")
        self._emit_value_changed()

    def _on_rec_slider_changed(self, pos: int):
        self.rec_val = self._from_slider(pos, self.REC_MIN, self.REC_MAX)
        self.rec_label.setText(f"{self.rec_val:.3f}")
        self._emit_value_changed()

    def _emit_value_changed(self):
        self.value_changed_signal.emit({
            "forward_head_sensitivity": self.fwd_val,
            "recline_sensitivity": self.rec_val
        })

    def get_value(self) -> dict:
        return {
            "forward_head_sensitivity": self.fwd_val,
            "recline_sensitivity": self.rec_val
        }

    def set_value(self, config: dict):
        self.fwd_val = self._clamp(
            config.get("forward_head_sensitivity", 0.05),
            self.FWD_MIN, self.FWD_MAX,
        )
        self.rec_val = self._clamp(
            config.get("recline_sensitivity", 0.02),
            self.REC_MIN, self.REC_MAX,
        )
        self.fwd_slider.blockSignals(True)
        self.rec_slider.blockSignals(True)
        self.fwd_slider.setValue(self._to_slider(self.fwd_val, self.FWD_MIN, self.FWD_MAX))
        self.rec_slider.setValue(self._to_slider(self.rec_val, self.REC_MIN, self.REC_MAX))
        self.fwd_slider.blockSignals(False)
        self.rec_slider.blockSignals(False)
        self.fwd_label.setText(f"{self.fwd_val:.3f}")
        self.rec_label.setText(f"{self.rec_val:.3f}")
