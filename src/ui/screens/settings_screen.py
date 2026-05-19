from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget, QMessageBox
)
from src.ui.styles.theme import Colors, ThemeManager
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
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)
        scroll_content.setLayout(scroll_layout)

        categories = [
            "알림 설정",
            "소리 설정",
            "팝업 설정",
            "감도 설정",
            "컴퓨터 부팅 시\n프로그램 자동 시작",
        ]
        category_widget_classes = [
            NotificationSettingsWidget,
            SoundSettingsWidget,
            PopupSettingsWidget,
            SensitivitySettingsWidget,
            AutoStartSettingsWidget,
        ]

        for cat, widget_class in zip(categories, category_widget_classes):
            row_frame = QFrame()
            row_frame.setStyleSheet(
                f"background-color: {Colors.WHITE.value}; border: 1px solid #E3E0F2; border-radius: {self.theme_manager.scale_pixel(8)}px;"
            )
            row_frame.setMinimumHeight(self.theme_manager.scale_pixel(220))
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(16, 16, 16, 16)
            row_layout.setSpacing(16)
            row_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            category_label = QLabel(cat)
            category_label.setFixedWidth(self.theme_manager.scale_pixel(210))
            category_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            category_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(16), QFont.Weight.Bold))
            category_label.setStyleSheet(
                f"background-color: {Colors.PURPLE_PRIMARY.value}; color: {Colors.WHITE.value}; "
                f"border-radius: {self.theme_manager.scale_pixel(10)}px; padding: {self.theme_manager.scale_pixel(10)}px;"
            )

            widget = widget_class(self.theme_manager, self.settings_config)
            if cat == "팝업 설정":
                row_frame.setMinimumHeight(self.theme_manager.scale_pixel(360))
                widget.setMinimumHeight(self.theme_manager.scale_pixel(320))
            elif cat == "감도 설정":
                # 감도 설정 칸의 높이를 늘려 입력 박스와 설명이 여유 있게 보이도록 조정
                row_frame.setMinimumHeight(self.theme_manager.scale_pixel(340))
                widget.setMinimumHeight(self.theme_manager.scale_pixel(300))
                # 로컬 초기화 신호 연결
                if hasattr(widget, "reset_requested_signal"):
                    widget.reset_requested_signal.connect(self._reset_settings)
            else:
                widget.setMinimumHeight(self.theme_manager.scale_pixel(188))
            
            widget.value_changed_signal.connect(self._on_widget_value_changed)
            self.category_widgets.append(widget)

            row_layout.addWidget(category_label)
            row_layout.addWidget(widget, 1)
            row_frame.setLayout(row_layout)
            scroll_layout.addWidget(row_frame)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1)

        # 하단 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)

        confirm_btn = QPushButton("저장 및 적용")
        confirm_btn.setFixedSize(self.theme_manager.scale_pixel(200), self.theme_manager.scale_pixel(56))
        confirm_btn.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(20), QFont.Weight.Bold))
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
        reply = QMessageBox.question(
            self, "감도 초기화",
            "민감도 설정을 마지막 자세 맞춤 기반 권장값으로 초기화하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.settings_reset_signal.emit()
