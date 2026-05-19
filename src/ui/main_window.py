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
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QEvent
from PyQt6.QtGui import QFont, QGuiApplication, QIcon, QPixmap
from PyQt6.QtCore import QTimer
from pathlib import Path
import sys

from src.utils.logger import get_logger
from src.ui.styles.theme import ThemeManager, Colors, FontSize, Spacing
from src.ui.styles.font_loader import app_font

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

        # DPI 스케일 계산 (logicalDotsPerInch로 Windows 배율 정확히 반영)
        self.dpi_scale = QGuiApplication.primaryScreen().logicalDotsPerInch() / 96.0
        self.theme_manager = ThemeManager(self.dpi_scale)

        logger.info(f"MainWindow 초기화 (DPI scale: {self.dpi_scale:.2f})")

        # 기본 설정
        self.setWindowTitle("바로목")
        self.setGeometry(100, 100, 1152, 768)
        self.setFixedSize(1152, 768)

        logo_path = Path(__file__).resolve().parents[2] / "assets" / "ui" / "바로목로고.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        # 프로그램 아이콘 및 작업 표시줄 설정
        current_dir = Path(__file__).resolve().parent # src/ui 폴더 위치
        # 프로젝트 루트 폴더 기준으로 assets/ui/바로목로고.png 경로 지정
        logo_path = current_dir.parent.parent / "assets" / "ui" / "바로목로고.png"

        if logo_path.exists():
            # 시스템 기본 크기(보통 32x32나 48x48)에 맞춰 배율을 적용해 아이콘 생성
            icon_size = int(32 * self.dpi_scale)
            pixmap = QPixmap(str(logo_path)).scaled(
                icon_size, icon_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setWindowIcon(QIcon(pixmap))
        else:
            logger.error(f"로고 아이콘 파일을 찾을 수 없습니다: {logo_path}")

        # Windows 작업 표시줄에 파이썬 인터프리터 로고 대신 바로목 로고 강제 적용
        if sys.platform == "win32":
            import ctypes
            myappid = "baromok.posture.system.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        # ==========================================

        # 스타일 적용 (기존 코드)
        self.setStyleSheet(self.theme_manager.stylesheet)

        # UI 구성 (기존 코드)
        self.setup_ui()

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
        self._header_widget = self._create_header()
        main_layout.addWidget(self._header_widget)

        # 화면 스택
        self.stacked_widget = QStackedWidget()
        self._setup_screens()
        # 스택 변경 시 타이틀 표시를 제어하도록 연결
        try:
            self.stacked_widget.currentChanged.connect(lambda idx: self._update_title_visibility())
        except Exception:
            logger.exception("스택 변경 연결 중 예외")
        # 초기 상태 반영
        try:
            self._update_title_visibility()
        except Exception:
            pass
        main_layout.addWidget(self.stacked_widget, 1)

        # 하단 푸터
        footer = self._create_footer()
        main_layout.addWidget(footer)

        central_widget.setLayout(main_layout)

    def _create_header(self) -> QWidget:
        """상단 헤더 생성"""
        header = QWidget()
        header.setObjectName("app_header")
        header.setFixedHeight(int(95 * self.dpi_scale))

        layout = QHBoxLayout()
        layout.setContentsMargins(
            int(16 * self.dpi_scale),
            int(12 * self.dpi_scale),
            int(16 * self.dpi_scale),
            int(12 * self.dpi_scale),
        )
        layout.setSpacing(int(12 * self.dpi_scale))

        # 뒤로가기 버튼 (왼쪽)
        back_btn = QPushButton("←")
        back_btn.setFont(app_font(int(48 * self.dpi_scale), QFont.Weight.Bold))
        back_btn.setFixedSize(int(52 * self.dpi_scale), int(52 * self.dpi_scale))
        back_btn.clicked.connect(self._on_back_clicked)
        back_btn.setVisible(False)
        layout.addWidget(back_btn)

        icon_dir = Path(__file__).resolve().parents[2] / "assets" / "ui"
        self._icon_dir = icon_dir

        # 화면별 타이틀 아이콘 + 타이틀 (아이콘-텍스트 간격 5px)
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(int(5 * self.dpi_scale))

        self.header_icon = QLabel()
        self.header_icon.setObjectName("header_icon")
        self.header_icon.setFixedSize(
            int(48 * self.dpi_scale), int(48 * self.dpi_scale)
        )
        self.header_icon.setScaledContents(True)
        self.header_icon.setVisible(False)
        title_layout.addWidget(self.header_icon)

        # 타이틀 — 크기/굵기는 전역 QSS(#header_title)에서 지정
        self.header_title = QLabel("바로목")
        self.header_title.setObjectName("header_title")
        title_layout.addWidget(self.header_title)

        layout.addLayout(title_layout)

        layout.addStretch()

        def create_header_button(text: str, icon_name: str, callback):
            btn = QToolButton()
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            default_icon = icon_dir / icon_name
            purple_icon = icon_dir / (Path(icon_name).stem + "_purple.png")
            btn.setIcon(QIcon(str(default_icon)))
            btn.setIconSize(QSize(int(34 * self.dpi_scale), int(34 * self.dpi_scale)))
            btn.setText(text)
            btn.setFont(app_font(int(12 * self.dpi_scale)))
            base_width = int((104 if text == "기준자세설정" else 96) * self.dpi_scale) # 기준자세설정 버튼만 좌우 길이 조정
            base_height = int(72 * self.dpi_scale)
            pressed_width = int((102 if text == "기준자세설정" else 94) * self.dpi_scale)
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

            def on_click_wrapper():
                try:
                    callback()
                except Exception:
                    logger.exception("Header 버튼 콜백 실행 중 예외")
                try:
                    self._set_header_icons("purple")
                except Exception:
                    logger.exception("헤더 아이콘 보라색으로 변경 중 예외")

            btn.clicked.connect(on_click_wrapper)
            btn._default_icon = default_icon
            btn._purple_icon = purple_icon
            btn.installEventFilter(self)

            layout.addWidget(btn)
            return btn

        self._posture_adjust_btn = create_header_button(
            "기준자세설정", "icon_posture.png", self.posture_adjust_requested.emit
        )

        self._settings_btn = create_header_button(
            "환경설정", "icon_settings.png", self.settings_requested.emit
        )
        self._statistics_btn = create_header_button(
            "나의 통계", "icon_stats.png", self.statistics_requested.emit
        )

        # 뒤로가기 버튼 (기본 숨김)
        back_btn = QPushButton("← 이전")
        back_btn.setFont(app_font(int(60 * self.dpi_scale), QFont.Weight.Bold))
        back_btn.setFixedSize(int(120 * self.dpi_scale), int(52 * self.dpi_scale))
        back_btn.clicked.connect(self._on_back_clicked)
        back_btn.setVisible(False)
        layout.addWidget(back_btn)

        self._back_btn = back_btn
        self._back_callback = None
        self._title_label = self.header_title

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
        # 기본 헤더로 복원될 때 아이콘도 기본 상태로 되돌림
        if hasattr(self, "_set_header_icons"):
            try:
                self._set_header_icons("default")
                
                # [오류 수정 및 버그 해결]
                # QCursor.pos()를 사용해 마우스 절대 좌표를 정확히 가져옵니다.
                from PyQt6.QtGui import QCursor
                cursor_pos = self.mapFromGlobal(QCursor.pos())
                
                # 마우스가 버튼들 영역 내에 있는지 검사 후 보라색 아이콘 적용
                for btn in [self._posture_adjust_btn, self._settings_btn, self._statistics_btn]:
                    if btn.isVisible() and btn.geometry().contains(cursor_pos):
                        if hasattr(btn, "_purple_icon") and btn._purple_icon.exists():
                            btn.setIcon(QIcon(str(btn._purple_icon)))
            except Exception:
                logger.exception("헤더 아이콘 복원 중 예외")

    def _update_title_visibility(self):
        """헤더 타이틀은 항상 표시 (화면별 텍스트는 set_header_title로 변경)"""
        if hasattr(self, "header_title"):
            self.header_title.setVisible(True)

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
        notice.setFont(app_font(int(12 * self.dpi_scale)))
        notice.setStyleSheet(f"color: {Colors.GRAY_DARK.value};")
        layout.addWidget(notice)

        layout.addStretch()

        footer.setLayout(layout)
        return footer

    def _set_header_icons(self, theme: str):
        """헤더 버튼 아이콘을 변경합니다. theme: 'default' 또는 'purple'"""
        def apply_icon(btn, kind: str):
            try:
                if kind == "purple" and hasattr(btn, "_purple_icon") and btn._purple_icon.exists():
                    btn.setIcon(QIcon(str(btn._purple_icon)))
                elif hasattr(btn, "_default_icon") and btn._default_icon.exists():
                    btn.setIcon(QIcon(str(btn._default_icon)))
            except Exception:
                logger.exception("아이콘 적용 중 예외")

        apply_icon(self._posture_adjust_btn, theme)
        apply_icon(self._settings_btn, theme)
        apply_icon(self._statistics_btn, theme)

    def eventFilter(self, obj, event):
        """버튼 마우스 엔터/리브 이벤트로 아이콘 변경 처리"""
        try:
            if event.type() == QEvent.Type.Enter:
                if hasattr(obj, "_purple_icon") and obj._purple_icon.exists():
                    obj.setIcon(QIcon(str(obj._purple_icon)))
                    return True
            elif event.type() == QEvent.Type.Leave:
                if hasattr(obj, "_default_icon") and obj._default_icon.exists():
                    obj.setIcon(QIcon(str(obj._default_icon)))
                    return True
        except Exception:
            logger.exception("eventFilter 처리 중 예외")
        return super().eventFilter(obj, event)

    def _setup_screens(self):
        """화면 설정 (Phase 3에서 순차적으로 추가)"""
        # 현재는 placeholder 화면만 추가
        # Phase 3에서 실제 화면들을 추가할 예정

        # 임시 화면
        placeholder = QWidget()
        placeholder_layout = QVBoxLayout()
        placeholder_label = QLabel("화면 준비 중...\n(Phase 3에서 구현)")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setFont(app_font(19))
        placeholder_layout.addWidget(placeholder_label)
        placeholder.setLayout(placeholder_layout)

        self.stacked_widget.addWidget(placeholder)
        self.stacked_widget.setCurrentWidget(placeholder)
        # 초기 화면 참조 저장 (아이콘 전환 조건으로 사용)
        self._initial_placeholder = placeholder

    # 화면 타이틀별 좌측 아이콘
    _HEADER_ICONS = {
        "바로목": "바로목로고.png",
        "환경설정": "icon_settings.png",
        "기준 자세 설정": "icon_posture.png",
        "나의 통계": "icon_stats.png",
    }

    def set_header_title(self, title: str, show_icon: bool = True):
        """헤더 타이틀 텍스트 및 좌측 아이콘 변경"""
        self.header_title.setText(title)

        if not show_icon:
            self.header_icon.setVisible(False)
            return

        icon_name = self._HEADER_ICONS.get(title)
        if icon_name:
            icon_path = self._icon_dir / icon_name
            if icon_path.exists():
                self.header_icon.setPixmap(QPixmap(str(icon_path)))
                self.header_icon.setVisible(True)
                return
        self.header_icon.setVisible(False)

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
