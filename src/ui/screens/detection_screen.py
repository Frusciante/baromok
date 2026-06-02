import logging
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
)
from src.ui.styles.theme import Colors, ThemeManager
from src.ui.styles.font_loader import app_font
from .helpers import set_recognition_message, cv2_to_qpixmap, RECOGNITION_DIFFICULT_MESSAGE

logger = logging.getLogger(__name__)

class DetectionScreen(QWidget):
    """감지 진행 화면"""

    detection_paused_signal = pyqtSignal()
    detection_stopped_signal = pyqtSignal()
    open_settings_signal = pyqtSignal()
    open_baseline_signal = pyqtSignal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        camera_worker=None,
        session_manager=None,
        baseline_manager=None,
    ):
        super().__init__()
        self.theme_manager = theme_manager
        self.camera_worker = camera_worker
        self.session_manager = session_manager
        self.baseline_manager = baseline_manager
        self.start_time = None
        self.elapsed_time = 0
        self.is_detection_paused = False
        self.setup_ui()

        if self.camera_worker:
            self.camera_worker.frame_processed_signal.connect(self._on_frame_processed)
            self.camera_worker.error_signal.connect(self._on_camera_error)

        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self._update_elapsed_time)

    def setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        top_layout = QHBoxLayout()
        self.status_label = QLabel("준비중")
        self.status_label.setFont(app_font(self.theme_manager.scale_pixel(17), QFont.Weight.Bold))
        self.status_label.setObjectName("status_normal")
        top_layout.addWidget(self.status_label)
        top_layout.addStretch()

        settings_btn = QPushButton("⚙ 설정")
        settings_btn.setFixedHeight(self.theme_manager.scale_pixel(32))
        settings_btn.clicked.connect(self.open_settings_signal.emit)
        top_layout.addWidget(settings_btn)
        layout.addLayout(top_layout)

        self.time_label = QLabel("00:00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setFont(app_font(self.theme_manager.scale_pixel(51), QFont.Weight.Bold))
        layout.addWidget(self.time_label)

        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet(f"""
            background-color: {Colors.WHITE.value};
            border: 1px solid {Colors.GRAY_MEDIUM.value};
        """)
        self.preview_frame.setMinimumHeight(self.theme_manager.scale_pixel(300))
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_label = QLabel("[카메라 프리뷰]")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_label)
        self.preview_frame.setLayout(preview_layout)
        layout.addWidget(self.preview_frame, 1)

        self.recognition_label = QLabel("")
        self.recognition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recognition_label.setFont(app_font(self.theme_manager.scale_pixel(15), QFont.Weight.Bold))
        self.recognition_label.setStyleSheet(f"color: {Colors.RED_DANGER.value};")
        set_recognition_message(self.recognition_label, False)
        layout.addWidget(self.recognition_label)

        self.posture_label = QLabel("감지 중")
        self.posture_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.posture_label.setFont(app_font(self.theme_manager.scale_pixel(19), QFont.Weight.Bold))
        layout.addWidget(self.posture_label)

        self.cheek_detail_label = QLabel("광대 거리: - (예상: -)")
        self.cheek_detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cheek_detail_label.setFont(app_font(self.theme_manager.scale_pixel(15)))
        self.cheek_detail_label.setStyleSheet(f"color: {Colors.GRAY_DARK.value};")
        layout.addWidget(self.cheek_detail_label)

        self.distance_label = QLabel("화면 거리: - cm")
        self.distance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.distance_label.setFont(app_font(self.theme_manager.scale_pixel(16), QFont.Weight.Bold))
        self.distance_label.setStyleSheet(f"color: {Colors.GRAY_MEDIUM.value};")
        layout.addWidget(self.distance_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.recalibrate_btn = QPushButton("재측정")
        self.recalibrate_btn.setFixedHeight(self.theme_manager.scale_pixel(40))
        self.recalibrate_btn.clicked.connect(self._recalibrate)
        button_layout.addWidget(self.recalibrate_btn)

        self.pause_btn = QPushButton("일시정지")
        self.pause_btn.setFixedHeight(self.theme_manager.scale_pixel(40))
        self.pause_btn.clicked.connect(self._pause_detection)
        button_layout.addWidget(self.pause_btn)

        stop_btn = QPushButton("종료")
        stop_btn.setFixedHeight(self.theme_manager.scale_pixel(40))
        stop_btn.setObjectName("danger")
        stop_btn.clicked.connect(self._stop_detection)
        button_layout.addWidget(stop_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _on_frame_processed(self, frame_data: dict):
        try:
            if frame_data.get("posture_type") == "baseline": return
            annotated_frame = frame_data.get("frame")
            if annotated_frame is not None:
                pixmap = cv2_to_qpixmap(annotated_frame)
                # 프레임의 실제 비율을 유지하며 가용한 공간에 맞춤 (밑이 잘리지 않도록)
                scaled_pixmap = pixmap.scaled(
                    self.preview_frame.width(),
                    self.preview_frame.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                self.preview_label.setPixmap(scaled_pixmap)

            indicators = frame_data.get("indicators")
            if indicators is None:
                self.posture_label.setText(RECOGNITION_DIFFICULT_MESSAGE)
                self.cheek_detail_label.setText("광대 거리: - (예상: -)")
                return

            set_recognition_message(self.recognition_label, False)
            self._update_posture_status(frame_data.get("state", "NORMAL"), frame_data.get("posture_type", "normal"), frame_data.get("probability", 0.0))

            # 광대 거리 정보 업데이트
            current_cheek = indicators.cheek_distance
            if self.baseline_manager:
                expected_cheek = self.baseline_manager.get_expected_cheek(indicators.shoulder_width)
                deviation = (current_cheek - expected_cheek) / expected_cheek if expected_cheek > 0 else 0
                self.cheek_detail_label.setText(f"광대 거리: {current_cheek:.3f} (예상: {expected_cheek:.3f}, 편차: {deviation*100:+.1f}%)")
            else:
                self.cheek_detail_label.setText(f"광대 거리: {current_cheek:.3f}")

            # 화면 거리 업데이트
            dist_cm = indicators.eye_screen_distance_cm
            if dist_cm is not None:
                self.distance_label.setText(f"화면 거리: {dist_cm:.1f} cm")
            else:
                self.distance_label.setText("화면 거리: - cm")

            if self.session_manager and getattr(self.session_manager, "current_session", None) is not None:
                self.session_manager.add_frame_data(frame_data)
        except Exception as e:
            logger.error(f"프레임 처리 오류: {e}")

    def _update_posture_status(self, state: str, posture_type: str, probability: float):
        posture_map = {
            "normal": "바른 자세",
            "forward_head": "거북목",
            "recline": "기댄 자세",
            "chin_rest_estimated": "턱 받침",
            "eye_close": "화면 가까움",
            "turned_head": "고개 돌린 자세",
            "baseline": "자세 맞춤 중"
        }
        self.posture_label.setText(f"{posture_map.get(posture_type, '알 수 없음')} ({probability:.1%})")
        state_text = {"normal": "바른 자세", "warning": "경고", "bad_posture": "나쁜 자세", "NORMAL": "바른 자세", "WARNING": "경고", "BAD_POSTURE": "나쁜 자세"}
        self.status_label.setText(state_text.get(state, "상태 알 수 없음"))
        state_colors = {"normal": "status_normal", "warning": "status_warning", "bad_posture": "status_bad", "NORMAL": "status_normal", "WARNING": "status_warning", "BAD_POSTURE": "status_bad"}
        self.status_label.setObjectName(state_colors.get(state, "status_normal"))
        self.status_label.style().polish(self.status_label)

    def _update_elapsed_time(self):
        if self.camera_worker:
            elapsed = self.camera_worker.get_elapsed_time()
            self.time_label.setText(f"{elapsed // 3600:02d}:{(elapsed % 3600) // 60:02d}:{elapsed % 60:02d}")

    def _pause_detection(self):
        if self.camera_worker:
            if self.is_detection_paused:
                self.camera_worker.resume()
                self.time_timer.start(1000)
                self.pause_btn.setText("일시정지")
                self.is_detection_paused = False
            else:
                self.camera_worker.pause()
                self.time_timer.stop()
                self.pause_btn.setText("재개")
                self.is_detection_paused = True
            self.detection_paused_signal.emit()

    def _recalibrate(self):
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.pause()
        self.time_timer.stop()
        self.is_detection_paused = False
        self.pause_btn.setText("일시정지")
        self.open_baseline_signal.emit()

    def _stop_detection(self):
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.pause()
        self.time_timer.stop()
        self.pause_btn.setText("일시정지")
        self.is_detection_paused = False
        self.detection_stopped_signal.emit()

    def on_detection_started(self):
        self.is_detection_paused = False
        self.pause_btn.setText("일시정지")
        self._update_elapsed_time()
        self.time_timer.start(1000)

    def showEvent(self, event):
        super().showEvent(event)
        if self.camera_worker and self.camera_worker.is_running and not self.is_detection_paused: self.time_timer.start(1000)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.time_timer.stop()

    def _on_camera_error(self, error_msg: str):
        self.preview_label.setText(f"오류: {error_msg}")
        self.status_label.setText("카메라 오류")
        self.time_timer.stop()
        self.pause_btn.setText("일시정지")
        self.is_detection_paused = False
