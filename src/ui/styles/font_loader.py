"""
번들 폰트 로더

앱에 포함된 Pretendard 폰트를 로드하여
어떤 컴퓨터에서든 동일한 폰트로 렌더링되도록 보장
"""

from pathlib import Path
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtWidgets import QApplication

from src.utils.logger import get_logger

logger = get_logger(__name__)

FONT_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"
BUNDLED_FAMILY = "Pretendard"

# 굵기별 폰트 파일 (모두 같은 패밀리 "Pretendard")
FONT_FILES = [
    "Pretendard-Regular.otf",
    "Pretendard-Bold.otf",
]


def load_bundled_fonts() -> str:
    """
    번들 폰트를 QFontDatabase에 등록한다.

    Returns:
        등록된 폰트 패밀리 이름. 실패 시 시스템 폴백 이름.
    """
    loaded_family = None

    for file_name in FONT_FILES:
        font_path = FONT_DIR / file_name
        if not font_path.exists():
            logger.warning(f"번들 폰트 파일 없음: {font_path}")
            continue

        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id == -1:
            logger.warning(f"번들 폰트 로드 실패: {file_name}")
            continue

        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            loaded_family = families[0]

    if loaded_family is None:
        logger.warning("번들 폰트를 하나도 로드하지 못함")
        return _system_fallback()

    logger.info(f"번들 폰트 로드 완료: {loaded_family}")
    return loaded_family


def _system_fallback() -> str:
    """시스템에 설치된 한글 폰트 중 사용 가능한 것을 반환"""
    for name in ["Malgun Gothic", "맑은 고딕", "나눔고딕", "Apple SD Gothic Neo"]:
        if QFontDatabase.hasFamily(name):
            logger.info(f"폴백 폰트 사용: {name}")
            return name
    return "sans-serif"


def _apply_render_hints(font: QFont) -> QFont:
    """폰트에 안티앨리어싱/고품질 렌더링 전략을 적용"""
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
    )
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def app_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """번들 폰트로 QFont를 생성 (안티앨리어싱 적용)"""
    font = QFont(BUNDLED_FAMILY, size, weight)
    return _apply_render_hints(font)


def set_app_font(app: QApplication, family: str, size: int = 12) -> None:
    """QApplication 기본 폰트를 설정"""
    font = QFont(family, size)
    _apply_render_hints(font)
    app.setFont(font)
