import logging
import cv2
import numpy as np
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel

logger = logging.getLogger(__name__)

RECOGNITION_DIFFICULT_MESSAGE = "인식이 어렵습니다"

def set_recognition_message(label: QLabel, visible: bool):
    """사용자 미탐지 안내 문구 표시/숨김"""
    label.setVisible(visible)
    if visible:
        label.setText(RECOGNITION_DIFFICULT_MESSAGE)
    else:
        label.clear()

def cv2_to_qpixmap(frame: np.ndarray) -> QPixmap:
    """OpenCV 프레임을 QPixmap으로 변환"""
    try:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(
            rgb_frame.data,
            w,
            h,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        )
        return QPixmap.fromImage(qt_image)
    except Exception as e:
        logger.error(f"프레임 변환 실패: {e}")
        return QPixmap()