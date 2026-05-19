from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
    QGridLayout, QWidget, QMessageBox
)
from src.ui.styles.theme import Colors, ThemeManager
from src.ui.styles.font_loader import app_font
from src.config import get_config

class SettingsScreen(QWidget):
    """환경 설정 화면"""

    settings_saved_signal = pyqtSignal(dict)
    settings_reset_signal = pyqtSignal()
    back_to_hub_signal = pyqtSignal()

    def __init__(self, theme_manager: ThemeManager, settings_config: dict = None):
        super().__init__()
        self.theme_manager = theme_manager
        self.settings_config = settings_config or {}
        self.category_widgets = []
        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        from src.ui.widgets.settings_widgets import (
            AutoStartSettingsWidget,
            NotificationSettingsWidget,
            PopupSettingsWidget,
            SoundSettingsWidget,
            SensitivitySettingsWidget,
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(9)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(8)
        grid_layout.setVerticalSpacing(8)
        scroll_content.setLayout(grid_layout)

        # (카테고리명, 위젯 클래스, grid 위치 (row, col, rowspan, colspan))
        category_specs = [
            ("알림 설정", NotificationSettingsWidget, (0, 0, 1, 1)),
            ("소리 설정", SoundSettingsWidget, (0, 1, 1, 1)),
            ("팝업 설정", PopupSettingsWidget, (1, 0, 1, 1)),
            ("감도 설정", SensitivitySettingsWidget, (1, 1, 1, 1)),
            ("자동 감지 시작", AutoStartSettingsWidget, (2, 0, 1, 2)),
        ]

        for cat, widget_class, (row, col, rspan, cspan) in category_specs:
            row_frame = QFrame()
            row_frame.setStyleSheet(
                f"background-color: {Colors.WHITE.value}; border: 1px solid #E3E0F2; border-radius: {self.theme_manager.scale_pixel(8)}px;"
            )
            row_frame.setMinimumHeight(self.theme_manager.scale_pixel(126))
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(8, 8, 8, 8)
            row_layout.setSpacing(9)
            row_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            category_label = QLabel(cat)
            category_label.setFixedWidth(self.theme_manager.scale_pixel(97))
            category_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            category_label.setFont(app_font(self.theme_manager.scale_pixel(13), QFont.Weight.Bold))
            category_label.setStyleSheet(
                f"background-color: {Colors.PURPLE_PRIMARY.value}; color: {Colors.WHITE.value}; "
                f"border-radius: {self.theme_manager.scale_pixel(8)}px; padding: {self.theme_manager.scale_pixel(5)}px;"
            )
            category_label.setWordWrap(True)

            widget = widget_class(self.theme_manager, self.settings_config)
            if cat == "팝업 설정":
                row_frame.setMinimumHeight(self.theme_manager.scale_pixel(232))
                widget.setMinimumHeight(self.theme_manager.scale_pixel(204))
            elif cat == "감도 설정":
                row_frame.setMinimumHeight(self.theme_manager.scale_pixel(218))
                widget.setMinimumHeight(self.theme_manager.scale_pixel(189))
                if hasattr(widget, "reset_requested_signal"):
                    widget.reset_requested_signal.connect(self._reset_settings)
            elif cat == "소리 설정":
                row_frame.setMinimumHeight(self.theme_manager.scale_pixel(218))
                widget.setMinimumHeight(self.theme_manager.scale_pixel(189))
            else:
                widget.setMinimumHeight(self.theme_manager.scale_pixel(115))

            widget.value_changed_signal.connect(self._on_widget_value_changed)
            self.category_widgets.append(widget)

            row_layout.addWidget(category_label)
            row_layout.addWidget(widget, 1)
            row_frame.setLayout(row_layout)
            grid_layout.addWidget(row_frame, row, col, rspan, cspan)

        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        grid_layout.setRowStretch(3, 1)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1)

        # 하단 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)

        confirm_btn = QPushButton("저장")
        confirm_btn.setFixedSize(self.theme_manager.scale_pixel(168), self.theme_manager.scale_pixel(43))
        confirm_btn.setFont(app_font(self.theme_manager.scale_pixel(17), QFont.Weight.Bold))
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PURPLE_PRIMARY.value};
                color: {Colors.WHITE.value};
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: #5343B6;
            }}
        """)
        confirm_btn.clicked.connect(self._save_settings)
        
        button_layout.addStretch()
        button_layout.addWidget(confirm_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _on_widget_value_changed(self, value_dict: dict):
        self.settings_config.update(value_dict)

    def _save_settings(self):
        all_settings = {}
        for widget in self.category_widgets:
            all_settings.update(widget.get_value())
        self.settings_saved_signal.emit(all_settings)
        self.back_to_hub_signal.emit()

    def _reset_settings(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("감도 초기화")
        msg.setText(
            "민감도 설정을 마지막 자세 맞춤 기반 권장값으로 초기화하시겠습니까?"
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

        reply = msg.exec()
        if reply == QMessageBox.StandardButton.Ok:
            self.settings_reset_signal.emit()
