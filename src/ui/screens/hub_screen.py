from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
)
from src.ui.styles.theme import ThemeManager

class HubScreen(QWidget):
    """메인 허브 화면"""

    start_detection_signal = pyqtSignal()
    open_settings_signal = pyqtSignal()
    open_statistics_signal = pyqtSignal()
    open_baseline_signal = pyqtSignal()

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.theme_manager = theme_manager
        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # 상단 영역: 가로 레이아웃 (일러스트 + 버튼)
        top_layout = QHBoxLayout()
        top_layout.setSpacing(30)

        # 왼쪽: 일러스트 영역
        illust_frame = QFrame()
        illust_frame.setStyleSheet(f"background-color: transparent; border: none;")
        illust_frame.setMaximumWidth(self.theme_manager.scale_pixel(520))
        illust_layout = QVBoxLayout(illust_frame)
        illust_layout.setContentsMargins(0, 0, 0, 0)
        illust_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        illust_label = QLabel()
        illust_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 홈 일러스트 로드
        image_path_candidates = [
            Path("assets/ui/바로목로고.png"),
            Path("assets/ui/home_illustration.svg"),
        ]
        for image_path in image_path_candidates:
            if not image_path.exists():
                continue
            try:
                pixmap = QPixmap(str(image_path))
                if pixmap.isNull():
                    continue
                scaled_pixmap = pixmap.scaledToHeight(
                    self.theme_manager.scale_pixel(380),
                    Qt.TransformationMode.SmoothTransformation,
                )
                illust_label.setPixmap(scaled_pixmap)
                break
            except Exception:
                continue
        else:
            illust_label.setText("[일러스트]")

        illust_layout.addWidget(illust_label, alignment=Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(illust_frame, 0, Qt.AlignmentFlag.AlignCenter)

        # 오른쪽: 버튼 영역 (세로 배치)
        button_layout = QVBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(12)

        def create_btn(text, signal):
            btn = QPushButton(text)
            btn.setFixedHeight(self.theme_manager.scale_pixel(48))
            btn.setFixedWidth(self.theme_manager.scale_pixel(360))
            btn.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(14), QFont.Weight.Bold))
            btn.clicked.connect(signal.emit)
            button_layout.addWidget(btn)

        create_btn("카메라 거리 캘리브레이션", self.open_baseline_signal)
        create_btn("환경 설정", self.open_settings_signal)
        create_btn("나의 통계", self.open_statistics_signal)

        top_layout.addLayout(button_layout, 1)
        main_layout.addLayout(top_layout, 1)
        main_layout.addStretch()

        start_btn = QPushButton("바로목 감지 시작")
        start_btn.setFixedHeight(self.theme_manager.scale_pixel(56))
        start_btn.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(20), QFont.Weight.Bold))
        start_btn.clicked.connect(self.start_detection_signal.emit)
        main_layout.addWidget(start_btn)

        self.setLayout(main_layout)