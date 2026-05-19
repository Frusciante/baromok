from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QWidget
)
from src.ui.styles.theme import Colors, ThemeManager
from src.ui.styles.font_loader import app_font

class AlertPopup(QWidget):
    """알림 팝업 (배너 & 토스트)"""

    close_signal = pyqtSignal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        alert_type: str = "warning",
        message_text: str = "알림 메시지",
    ):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.theme_manager = theme_manager
        self.alert_type = alert_type
        self.message_text = message_text
        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        layout = QHBoxLayout()
        layout.setContentsMargins(
            self.theme_manager.scale_pixel(12),
            self.theme_manager.scale_pixel(8),
            self.theme_manager.scale_pixel(12),
            self.theme_manager.scale_pixel(8),
        )
        layout.setSpacing(10)

        self.message_label = QLabel(self.message_text)
        self.message_label.setFont(app_font(self.theme_manager.scale_pixel(15), QFont.Weight.Bold))
        self.message_label.setStyleSheet(f"color: {Colors.WHITE.value};")
        layout.addWidget(self.message_label, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(self.theme_manager.scale_pixel(24), self.theme_manager.scale_pixel(24))
        close_btn.setStyleSheet(f"""
            background-color: rgba(255, 255, 255, 0.3); color: {Colors.WHITE.value}; border: none; border-radius: 3px;
        """)
        close_btn.clicked.connect(self.close_signal.emit)
        layout.addWidget(close_btn)

        self.setLayout(layout)
        self.setFixedHeight(self.theme_manager.scale_pixel(40))
        self.set_alert_content(self.alert_type, self.message_text)

    def set_alert_content(self, alert_type: str, message_text: str):
        """팝업 종류와 메시지 갱신"""
        self.alert_type = alert_type
        self.message_text = message_text
        bg_color = {"warning": Colors.YELLOW_WARNING.value, "danger": Colors.RED_DANGER.value, "info": Colors.PURPLE_PRIMARY.value}.get(self.alert_type, Colors.YELLOW_WARNING.value)
        self.setStyleSheet(f"background-color: {bg_color}; border-radius: 5px;")
        self.message_label.setText(self.message_text)