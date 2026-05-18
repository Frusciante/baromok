"""
메인 윈도우

PyQt 메인 애플리케이션 윈도우 및 화면 관리
"""

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QLabel,
    QPushButton,
    QToolButton,
    QApplication,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QGuiApplication, QIcon
from PyQt6.QtCore import QTimer
from pathlib import Path
import sys

from src.utils.logger import get_logger
from src.ui.styles.theme import ThemeManager, Colors, FontSize, Spacing

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """메인 윈도우"""

    # 신호
    screen_changed_signal = pyqtSignal(str)
    posture_adjust_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    statistics_requested = pyqtSignal()

    def __init__(self, config=None):
        """
        초기화

        Args:
            config: 설정 관리자 (Phase 4에서 사용)
        """
        super().__init__()

        self.config = config

        # DPI 스케일 계산
        self.dpi_scale = QGuiApplication.primaryScreen().devicePixelRatio()
        self.theme_manager = ThemeManager(self.dpi_scale)

        logger.info(f"MainWindow 초기화 (DPI scale: {self.dpi_scale:.2f})")

        # 기본 설정
        self.setWindowTitle("바로목 - 자세 측정 시스템")
        self.setGeometry(100, 100, 1152, 768)
        self.setFixedSize(1152, 768)

        # 스타일 적용
        self.setStyleSheet(self.theme_manager.stylesheet)

        # UI 구성
        self.setup_ui()

        logger.info("MainWindow 구성 완료")

    def setup_ui(self):
        """UI 구성"""
        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 메인 레이아웃
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 상단 헤더
        header = self._create_header()
        main_layout.addWidget(header)

        # 화면 스택
        self.stacked_widget = QStackedWidget()
        self._setup_screens()
        main_layout.addWidget(self.stacked_widget, 1)

        # 하단 푸터
        footer = self._create_footer()
        main_layout.addWidget(footer)

        central_widget.setLayout(main_layout)

    def _create_header(self) -> QWidget:
        """상단 헤더 생성"""
        header = QWidget()
        header.setFixedHeight(int(95 * self.dpi_scale))
        header.setStyleSheet(f"background-color: {Colors.PURPLE_PRIMARY.value};")

        layout = QHBoxLayout()
        layout.setContentsMargins(
            int(16 * self.dpi_scale),
            int(12 * self.dpi_scale),
            int(16 * self.dpi_scale),
            int(12 * self.dpi_scale),
        )
        layout.setSpacing(int(12 * self.dpi_scale))

        # 앱 이름
        title = QLabel("바로목")
        title_font = QFont("Noto Sans KR", int(54 * self.dpi_scale), QFont.Weight.Bold)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {Colors.WHITE.value};")
        layout.addWidget(title)

        # 스트래치 (오른쪽 공간)
        layout.addStretch()

        icon_dir = Path(__file__).resolve().parents[2] / "assets" / "ui"

        def create_header_button(text: str, icon_name: str, callback):
            btn = QToolButton()
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setIcon(QIcon(str(icon_dir / icon_name)))
            btn.setIconSize(QSize(int(34 * self.dpi_scale), int(34 * self.dpi_scale)))
            btn.setText(text)
            btn.setFont(QFont("Noto Sans KR", int(9 * self.dpi_scale)))
            base_width = int(96 * self.dpi_scale)
            base_height = int(72 * self.dpi_scale)
            pressed_width = int(94 * self.dpi_scale)
            pressed_height = int(70 * self.dpi_scale)
            btn.setFixedSize(base_width, base_height)
            btn.setStyleSheet(f"""
                QToolButton {{
                    background-color: transparent;
                    color: {Colors.WHITE.value};
                    border: 1px solid rgba(255, 255, 255, 0.35);
                    border-radius: {int(8 * self.dpi_scale)}px;
                    padding: {int(6 * self.dpi_scale)}px {int(8 * self.dpi_scale)}px {int(3 * self.dpi_scale)}px {int(8 * self.dpi_scale)}px;
                }}
                QToolButton:hover {{
                    background-color: {Colors.WHITE.value};
                    color: {Colors.PURPLE_PRIMARY.value};
                }}
                QToolButton:pressed {{
                    background-color: #ECEBFC;
                    color: {Colors.PURPLE_PRIMARY.value};
                }}
            """)
            btn.pressed.connect(lambda b=btn: b.setFixedSize(pressed_width, pressed_height))
            btn.released.connect(lambda b=btn: b.setFixedSize(base_width, base_height))
            btn.clicked.connect(callback)
            layout.addWidget(btn)
            return btn

        self._posture_adjust_btn = create_header_button(
            "자세 맞춤", "icon_posture.png", self.posture_adjust_requested.emit
        )
        self._settings_btn = create_header_button(
            "환경설정", "icon_settings.png", self.settings_requested.emit
        )
        self._statistics_btn = create_header_button(
            "나의 통계", "icon_stats.png", self.statistics_requested.emit
        )

        # 뒤로가기 버튼 (기본 숨김). 일부 화면에서는 이 버튼을 대신 노출하도록 함
        back_btn = QPushButton("←")
        back_btn.setFont(QFont("Noto Sans KR", int(16 * self.dpi_scale)))
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Colors.WHITE.value};
                border: none;
                width: {int(40 * self.dpi_scale)}px;
                height: {int(40 * self.dpi_scale)}px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.15);
            }}
        """)
        back_btn.clicked.connect(self._on_back_clicked)
        back_btn.setVisible(False)
        layout.addWidget(back_btn)

        self._back_btn = back_btn
        self._back_callback = None

        header.setLayout(layout)
        return header

    def _on_back_clicked(self):
        """헤더의 뒤로가기 버튼 클릭 처리: 등록된 콜백 호출"""
        if callable(self._back_callback):
            try:
                self._back_callback()
            except Exception:
                logger.exception("Back callback 실행 중 예외 발생")

    def set_back_callback(self, callback):
        """뒤로가기 버튼에 콜백 등록"""
        self._back_callback = callback

    def show_back_header(self):
        """뒤로가기 모드: 뒤로가기 버튼 보이기"""
        if hasattr(self, "_back_btn"):
            self._back_btn.setVisible(True)
        if hasattr(self, "_posture_adjust_btn"):
            self._posture_adjust_btn.setVisible(False)
        if hasattr(self, "_settings_btn"):
            self._settings_btn.setVisible(False)
        if hasattr(self, "_statistics_btn"):
            self._statistics_btn.setVisible(False)

    def show_default_header(self):
        """기본 모드: 뒤로가기 버튼 숨기기"""
        if hasattr(self, "_back_btn"):
            self._back_btn.setVisible(False)
        if hasattr(self, "_posture_adjust_btn"):
            self._posture_adjust_btn.setVisible(True)
        if hasattr(self, "_settings_btn"):
            self._settings_btn.setVisible(True)
        if hasattr(self, "_statistics_btn"):
            self._statistics_btn.setVisible(True)

    def _create_footer(self) -> QWidget:
        """하단 푸터 생성"""
        footer = QWidget()
        footer.setFixedHeight(int(40 * self.dpi_scale))
        footer.setStyleSheet(f"background-color: {Colors.GRAY_LIGHT.value};")

        layout = QHBoxLayout()
        layout.setContentsMargins(
            int(16 * self.dpi_scale),
            int(8 * self.dpi_scale),
            int(16 * self.dpi_scale),
            int(8 * self.dpi_scale),
        )

        # 안내 문구
        notice = QLabel(
            "본 애플리케이션은 의료 진단 도구가 아니며, 정보 제공 목적으로만 사용됩니다."
        )
        notice.setFont(QFont("Noto Sans KR", int(9 * self.dpi_scale)))
        notice.setStyleSheet(f"color: {Colors.GRAY_DARK.value};")
        layout.addWidget(notice)

        layout.addStretch()

        footer.setLayout(layout)
        return footer

    def _setup_screens(self):
        """화면 설정 (Phase 3에서 순차적으로 추가)"""
        # 현재는 placeholder 화면만 추가
        # Phase 3에서 실제 화면들을 추가할 예정

        # 임시 화면
        placeholder = QWidget()
        placeholder_layout = QVBoxLayout()
        placeholder_label = QLabel("화면 준비 중...\n(Phase 3에서 구현)")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setFont(QFont("Noto Sans KR", 16))
        placeholder_layout.addWidget(placeholder_label)
        placeholder.setLayout(placeholder_layout)

        self.stacked_widget.addWidget(placeholder)
        self.stacked_widget.setCurrentWidget(placeholder)

    def switch_to_screen(self, screen_name: str):
        """
        화면 전환

        Args:
            screen_name: 화면 이름
        """
        # Phase 3/4에서 구현
        logger.info(f"화면 전환: {screen_name}")
        self.screen_changed_signal.emit(screen_name)

    def closeEvent(self, event):
        """종료 이벤트 처리"""
        logger.info("애플리케이션 종료")
        event.accept()


def create_main_window(config=None) -> MainWindow:
    """메인 윈도우 생성"""
    return MainWindow(config)
