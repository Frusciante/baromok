"""
테마 및 스타일시트

PyQt UI의 색상, 폰트, 스타일 정의
"""
from enum import Enum
from typing import Dict, Tuple


class Colors(Enum):
    """색상 팔레트"""
    PURPLE_PRIMARY = "#7B5BA8"      # 보라 (주요 액션)
    PINK_PRIMARY = "#E85D75"        # 핑크 (강조/경고)
    GRAY_LIGHT = "#F5F5F5"          # 배경 (밝음)
    GRAY_MEDIUM = "#CCCCCC"         # 테두리
    GRAY_DARK = "#999999"           # 텍스트 (약함)
    TEXT_BLACK = "#333333"          # 텍스트 (주요)
    WHITE = "#FFFFFF"               # 흰색
    GREEN_SUCCESS = "#4CAF50"       # 정상 (초록)
    YELLOW_WARNING = "#FFC107"      # 경고 (노랑)
    ORANGE_ALERT = "#FF9800"        # 알림 (주황)
    RED_DANGER = "#F44336"          # 위험 (빨강)


class FontSize:
    """폰트 크기"""
    SMALL = 10
    NORMAL = 12
    MEDIUM = 14
    LARGE = 16
    XLARGE = 18
    TITLE = 24
    HEADING = 28


class Spacing:
    """간격"""
    XS = 4
    SMALL = 8
    NORMAL = 12
    MEDIUM = 16
    LARGE = 24
    XLARGE = 32


def get_stylesheet(dpi_scale: float = 1.0) -> str:
    """
    메인 스타일시트 반환
    
    Args:
        dpi_scale: DPI 스케일 (1.0 = 100%)
        
    Returns:
        QSS 스타일시트 문자열
    """
    # 폰트 크기 스케일
    normal_font = int(FontSize.NORMAL * dpi_scale)
    medium_font = int(FontSize.MEDIUM * dpi_scale)
    large_font = int(FontSize.LARGE * dpi_scale)
    title_font = int(FontSize.TITLE * dpi_scale)
    
    # 간격 스케일
    spacing_normal = int(Spacing.NORMAL * dpi_scale)
    spacing_medium = int(Spacing.MEDIUM * dpi_scale)
    spacing_large = int(Spacing.LARGE * dpi_scale)
    
    # 버튼 크기
    button_height = int(40 * dpi_scale)
    button_radius = int(10 * dpi_scale)
    
    return f"""
    /* 기본 설정 */
    QMainWindow {{
        background-color: {Colors.GRAY_LIGHT.value};
        font-family: "Segoe UI", "나눔고딕", sans-serif;
        font-size: {normal_font}pt;
    }}
    
    QWidget {{
        background-color: {Colors.GRAY_LIGHT.value};
        color: {Colors.TEXT_BLACK.value};
    }}
    
    /* 라벨 */
    QLabel {{
        color: {Colors.TEXT_BLACK.value};
        font-size: {normal_font}pt;
        background-color: transparent;
    }}
    
    QLabel#title {{
        font-size: {title_font}pt;
        font-weight: bold;
        color: {Colors.TEXT_BLACK.value};
    }}
    
    QLabel#heading {{
        font-size: {large_font}pt;
        font-weight: bold;
        color: {Colors.PURPLE_PRIMARY.value};
    }}
    
    QLabel#subtitle {{
        font-size: {medium_font}pt;
        color: {Colors.GRAY_DARK.value};
    }}
    
    QLabel#status_normal {{
        color: {Colors.GREEN_SUCCESS.value};
        font-weight: bold;
    }}
    
    QLabel#status_warning {{
        color: {Colors.ORANGE_ALERT.value};
        font-weight: bold;
    }}
    
    QLabel#status_bad {{
        color: {Colors.RED_DANGER.value};
        font-weight: bold;
    }}
    
    /* 버튼 - 일반 */
    QPushButton {{
        background-color: {Colors.PURPLE_PRIMARY.value};
        color: {Colors.WHITE.value};
        border: none;
        border-radius: {button_radius}px;
        padding: {int(8 * dpi_scale)}px {int(16 * dpi_scale)}px;
        font-size: {normal_font}pt;
        font-weight: bold;
        height: {button_height}px;
        outline: none;
    }}
    
    QPushButton:hover {{
        background-color: #6A4E91;
        cursor: pointer;
    }}
    
    QPushButton:pressed {{
        background-color: #5A3E81;
    }}
    
    QPushButton:disabled {{
        background-color: {Colors.GRAY_DARK.value};
        color: {Colors.GRAY_LIGHT.value};
        cursor: not-allowed;
    }}
    
    /* 버튼 - 세컨더리 (아웃라인) */
    QPushButton#secondary {{
        background-color: transparent;
        border: 2px solid {Colors.PURPLE_PRIMARY.value};
        color: {Colors.PURPLE_PRIMARY.value};
    }}
    
    QPushButton#secondary:hover {{
        background-color: {Colors.PURPLE_PRIMARY.value};
        color: {Colors.WHITE.value};
    }}
    
    /* 버튼 - 취소 */
    QPushButton#cancel {{
        background-color: {Colors.GRAY_MEDIUM.value};
    }}
    
    QPushButton#cancel:hover {{
        background-color: {Colors.GRAY_DARK.value};
    }}
    
    /* 버튼 - 위험 (빨강) */
    QPushButton#danger {{
        background-color: {Colors.RED_DANGER.value};
    }}
    
    QPushButton#danger:hover {{
        background-color: #E53935;
    }}
    
    /* 슬라이더 */
    QSlider::groove:horizontal {{
        background-color: {Colors.GRAY_MEDIUM.value};
        height: {int(6 * dpi_scale)}px;
        border-radius: {int(3 * dpi_scale)}px;
    }}
    
    QSlider::handle:horizontal {{
        background-color: {Colors.PURPLE_PRIMARY.value};
        width: {int(16 * dpi_scale)}px;
        margin: -{int(5 * dpi_scale)}px 0px;
        border-radius: {int(8 * dpi_scale)}px;
    }}
    
    QSlider::handle:horizontal:hover {{
        background-color: #6A4E91;
    }}
    
    /* 진행바 */
    QProgressBar {{
        border: none;
        background-color: {Colors.GRAY_MEDIUM.value};
        border-radius: {int(5 * dpi_scale)}px;
        height: {int(10 * dpi_scale)}px;
        text-align: center;
    }}
    
    QProgressBar::chunk {{
        background-color: {Colors.PURPLE_PRIMARY.value};
        border-radius: {int(5 * dpi_scale)}px;
    }}
    
    /* 체크박스 */
    QCheckBox {{
        spacing: {int(6 * dpi_scale)}px;
        color: {Colors.TEXT_BLACK.value};
    }}
    
    QCheckBox::indicator {{
        width: {int(18 * dpi_scale)}px;
        height: {int(18 * dpi_scale)}px;
        border-radius: {int(4 * dpi_scale)}px;
    }}
    
    QCheckBox::indicator:unchecked {{
        background-color: {Colors.WHITE.value};
        border: 2px solid {Colors.GRAY_MEDIUM.value};
    }}
    
    QCheckBox::indicator:checked {{
        background-color: {Colors.PURPLE_PRIMARY.value};
        border: 2px solid {Colors.PURPLE_PRIMARY.value};
    }}
    
    QCheckBox::indicator:checked::after {{
        content: "✓";
        color: {Colors.WHITE.value};
    }}
    
    /* 라디오 버튼 */
    QRadioButton {{
        spacing: {int(6 * dpi_scale)}px;
        color: {Colors.TEXT_BLACK.value};
    }}
    
    QRadioButton::indicator {{
        width: {int(18 * dpi_scale)}px;
        height: {int(18 * dpi_scale)}px;
        border-radius: {int(9 * dpi_scale)}px;
    }}
    
    QRadioButton::indicator:unchecked {{
        background-color: {Colors.WHITE.value};
        border: 2px solid {Colors.GRAY_MEDIUM.value};
    }}
    
    QRadioButton::indicator:checked {{
        background-color: {Colors.WHITE.value};
        border: 2px solid {Colors.PURPLE_PRIMARY.value};
    }}
    
    QRadioButton::indicator:checked::after {{
        width: {int(8 * dpi_scale)}px;
        height: {int(8 * dpi_scale)}px;
        background-color: {Colors.PURPLE_PRIMARY.value};
        border-radius: {int(4 * dpi_scale)}px;
    }}
    
    /* 콤보박스 */
    QComboBox {{
        background-color: {Colors.WHITE.value};
        border: 1px solid {Colors.GRAY_MEDIUM.value};
        border-radius: {button_radius}px;
        padding: {int(6 * dpi_scale)}px {int(12 * dpi_scale)}px;
        font-size: {normal_font}pt;
        min-height: {int(32 * dpi_scale)}px;
    }}
    
    QComboBox:hover {{
        border: 1px solid {Colors.PURPLE_PRIMARY.value};
    }}
    
    QComboBox::drop-down {{
        border: none;
        background-color: transparent;
    }}
    
    /* 라인에딧 */
    QLineEdit {{
        background-color: {Colors.WHITE.value};
        border: 1px solid {Colors.GRAY_MEDIUM.value};
        border-radius: {button_radius}px;
        padding: {int(6 * dpi_scale)}px {int(12 * dpi_scale)}px;
        font-size: {normal_font}pt;
        min-height: {int(32 * dpi_scale)}px;
    }}
    
    QLineEdit:focus {{
        border: 2px solid {Colors.PURPLE_PRIMARY.value};
    }}
    
    /* 스핀박스 */
    QSpinBox {{
        background-color: {Colors.WHITE.value};
        border: 1px solid {Colors.GRAY_MEDIUM.value};
        border-radius: {button_radius}px;
        padding: {int(4 * dpi_scale)}px {int(8 * dpi_scale)}px;
        font-size: {normal_font}pt;
        min-height: {int(32 * dpi_scale)}px;
    }}
    
    /* 탭 */
    QTabWidget::pane {{
        border: 1px solid {Colors.GRAY_MEDIUM.value};
        background-color: {Colors.WHITE.value};
    }}
    
    QTabBar::tab {{
        background-color: {Colors.GRAY_LIGHT.value};
        border: 1px solid {Colors.GRAY_MEDIUM.value};
        padding: {int(8 * dpi_scale)}px {int(16 * dpi_scale)}px;
        margin-right: {int(2 * dpi_scale)}px;
    }}
    
    QTabBar::tab:selected {{
        background-color: {Colors.WHITE.value};
        border: 2px solid {Colors.PURPLE_PRIMARY.value};
        color: {Colors.PURPLE_PRIMARY.value};
        font-weight: bold;
    }}
    
    /* 스크롤바 */
    QScrollBar:vertical {{
        background-color: {Colors.GRAY_LIGHT.value};
        width: {int(12 * dpi_scale)}px;
        border: none;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {Colors.GRAY_MEDIUM.value};
        border-radius: {int(6 * dpi_scale)}px;
        min-height: {int(20 * dpi_scale)}px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {Colors.PURPLE_PRIMARY.value};
    }}
    
    QScrollBar:horizontal {{
        background-color: {Colors.GRAY_LIGHT.value};
        height: {int(12 * dpi_scale)}px;
        border: none;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {Colors.GRAY_MEDIUM.value};
        border-radius: {int(6 * dpi_scale)}px;
        min-width: {int(20 * dpi_scale)}px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: {Colors.PURPLE_PRIMARY.value};
    }}
    
    /* 프레임 (카드) */
    QFrame#card {{
        background-color: {Colors.WHITE.value};
        border: 1px solid {Colors.GRAY_MEDIUM.value};
        border-radius: {button_radius}px;
        padding: {spacing_medium}px;
    }}
    
    /* 다이얼로그 */
    QDialog {{
        background-color: {Colors.GRAY_LIGHT.value};
    }}
    
    QMessageBox {{
        background-color: {Colors.GRAY_LIGHT.value};
    }}
    """


class ThemeManager:
    """테마 관리자"""
    
    def __init__(self, dpi_scale: float = 1.0):
        """
        초기화
        
        Args:
            dpi_scale: DPI 스케일 (1.0 = 100%)
        """
        self.dpi_scale = dpi_scale
        self.stylesheet = get_stylesheet(dpi_scale)
    
    def get_color(self, color_enum: Colors) -> str:
        """색상 반환"""
        return color_enum.value
    
    def scale_pixel(self, pixel: int) -> int:
        """픽셀을 DPI에 맞춰 스케일링"""
        return int(pixel * self.dpi_scale)
    
    def get_button_size(self) -> Tuple[int, int]:
        """버튼 기본 크기 반환 (너비, 높이)"""
        return (self.scale_pixel(100), self.scale_pixel(40))
    
    def get_font_size(self, size: FontSize) -> int:
        """폰트 크기 반환"""
        return self.scale_pixel(size.value)


def create_theme_manager(dpi_scale: float = 1.0) -> ThemeManager:
    """테마 관리자 생성"""
    return ThemeManager(dpi_scale)
