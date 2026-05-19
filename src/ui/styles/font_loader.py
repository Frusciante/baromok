"""
번들 폰트 로더

앱에 포함된 Noto Sans KR 폰트를 로드하여
어떤 컴퓨터에서든 동일한 폰트로 렌더링되도록 보장
"""

from pathlib import Path
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtWidgets import QApplication

from src.utils.logger import get_logger

logger = get_logger(__name__)

FONT_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"
BUNDLED_FAMILY = "Noto Sans KR"


def load_bundled_fonts() -> str:
    """
    번들 폰트를 QFontDatabase에 등록한다.

    Returns:
        등록된 폰트 패밀리 이름. 실패 시 시스템 폴백 이름.
    """
    font_path = FONT_DIR / "NotoSansKR-Variable.ttf"

    if not font_path.exists():
        logger.warning(f"번들 폰트 파일 없음: {font_path}")
        return _system_fallback()

    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id == -1:
        logger.warning("번들 폰트 로드 실패")
        return _system_fallback()

    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        logger.warning("번들 폰트에서 패밀리를 찾을 수 없음")
        return _system_fallback()

    family = families[0]
    logger.info(f"번들 폰트 로드 완료: {family}")
    return family


def _system_fallback() -> str:
    """시스템에 설치된 한글 폰트 중 사용 가능한 것을 반환"""
    for name in ["Malgun Gothic", "맑은 고딕", "나눔고딕", "Apple SD Gothic Neo"]:
        if QFontDatabase.hasFamily(name):
            logger.info(f"폴백 폰트 사용: {name}")
            return name
    return "sans-serif"


def set_app_font(app: QApplication, family: str, size: int = 12) -> None:
    """QApplication 기본 폰트를 설정"""
    font = QFont(family, size)
    app.setFont(font)
