import logging
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget
)
from src.ui.styles.theme import Colors, ThemeManager
from src.ui.styles.font_loader import app_font
from .helpers import set_recognition_message, cv2_to_qpixmap, RECOGNITION_DIFFICULT_MESSAGE

logger = logging.getLogger(__name__)

class DetectionScreen(QWidget):
    """감지 진행 화면"""

    detection_paused_signal = pyqtSignal()
    detection_stopped_signal = pyqtSignal()
    detection_restart_signal = pyqtSignal()
    view_results_signal = pyqtSignal()
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
        self.is_session_stopped = False
        self._waiting_for_first_frame = False
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
        layout.setSpacing(15)

        # [상단 헤더 정보] 상태, 자세 판정, 각도 정보를 한 줄에 배치
        header_info_layout = QHBoxLayout()
        
        self.status_label = QLabel("바른 자세")
        self.status_label.setFont(app_font(self.theme_manager.scale_pixel(17), QFont.Weight.Bold))
        self.status_label.setObjectName("status_normal")
        header_info_layout.addWidget(self.status_label)
        
        header_info_layout.addSpacing(20)
        
        self.posture_label = QLabel("감지 중")
        self.posture_label.setFont(app_font(self.theme_manager.scale_pixel(16), QFont.Weight.Bold))
        self.posture_label.setStyleSheet(f"color: {Colors.PRIMARY.value};")
        header_info_layout.addWidget(self.posture_label)
        
        header_info_layout.addStretch()
        
        self.pitch_label = QLabel("고개 각도: -°")
        self.pitch_label.setFont(app_font(self.theme_manager.scale_pixel(14)))
        self.pitch_label.setStyleSheet(f"color: {Colors.GRAY_DARK.value};")
        header_info_layout.addWidget(self.pitch_label)
        
        settings_btn = QPushButton("⚙ 설정")
        settings_btn.setFixedSize(self.theme_manager.scale_pixel(70), self.theme_manager.scale_pixel(32))
        settings_btn.clicked.connect(self.open_settings_signal.emit)
        header_info_layout.addWidget(settings_btn)
        
        layout.addLayout(header_info_layout)

        # 중앙 메인 레이아웃 (좌: 프리뷰/시간, 우: 가드)
        main_center_layout = QHBoxLayout()
        main_center_layout.setSpacing(20)
        
        # [좌측 영역]
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)

        self.time_label = QLabel("00:00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setFont(app_font(self.theme_manager.scale_pixel(42), QFont.Weight.Bold))
        left_panel.addWidget(self.time_label)

        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet(f"""
            background-color: {Colors.WHITE.value};
            border: 1px solid {Colors.GRAY_MEDIUM.value};
            border-radius: 12px;
        """)
        self.preview_frame.setMinimumHeight(self.theme_manager.scale_pixel(340))
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self._preview_stack = QStackedWidget()
        self._spinner_label = QLabel("카메라 연결 중...")
        self._spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_stack.addWidget(self._spinner_label)
        self.preview_label = QLabel("[카메라 프리뷰]")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_stack.addWidget(self.preview_label)
        self._preview_stack.setCurrentIndex(1)
        preview_layout.addWidget(self._preview_stack)
        self.preview_frame.setLayout(preview_layout)
        left_panel.addWidget(self.preview_frame, 1)

        self.recognition_label = QLabel("")
        self.recognition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recognition_label.setFont(app_font(self.theme_manager.scale_pixel(14), QFont.Weight.Bold))
        self.recognition_label.setStyleSheet(f"color: {Colors.RED_DANGER.value};")
        set_recognition_message(self.recognition_label, False)
        left_panel.addWidget(self.recognition_label)

        # [추가] 안내 메시지 라벨
        self.session_msg_label = QLabel("")
        self.session_msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session_msg_label.setFont(app_font(self.theme_manager.scale_pixel(13), QFont.Weight.Bold))
        self.session_msg_label.setWordWrap(True)
        self.session_msg_label.hide()
        left_panel.addWidget(self.session_msg_label)
        
        main_center_layout.addLayout(left_panel, 3)

        # [우측 영역] 가이드 패널
        from src.ui.widgets.settings_widgets import CorrectPostureGuideWidget
        self.guide_panel = CorrectPostureGuideWidget(self.theme_manager, vertical=True)
        self.guide_panel.setStyleSheet(f"background-color: #F8F9FF; border: 1px solid #E3E0F2; border-radius: 15px;")
        main_center_layout.addWidget(self.guide_panel, 2)
        
        layout.addLayout(main_center_layout)

        # 하단 세부 지표 및 버튼
        footer_layout = QHBoxLayout()
        
        details_layout = QVBoxLayout()
        self.cheek_detail_label = QLabel("광대 거리: -")
        self.cheek_detail_label.setFont(app_font(self.theme_manager.scale_pixel(13)))
        self.cheek_detail_label.setStyleSheet(f"color: {Colors.GRAY_DARK.value};")
        details_layout.addWidget(self.cheek_detail_label)

        self.distance_label = QLabel("화면 거리: - cm")
        self.distance_label.setFont(app_font(self.theme_manager.scale_pixel(14), QFont.Weight.Bold))
        self.distance_label.setStyleSheet(f"color: {Colors.GRAY_MEDIUM.value};")
        details_layout.addWidget(self.distance_label)
        footer_layout.addLayout(details_layout)
        
        footer_layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        for btn_name, callback, is_danger in [
            ("재측정", self._recalibrate, False),
            ("일시정지", self._pause_detection, False),
            ("종료", self._stop_detection, True)
        ]:
            btn = QPushButton(btn_name)
            btn.setFixedSize(self.theme_manager.scale_pixel(90), self.theme_manager.scale_pixel(40))
            if is_danger: btn.setObjectName("danger")
            btn.clicked.connect(callback)
            button_layout.addWidget(btn)
            if btn_name == "일시정지": self.pause_btn = btn
            elif btn_name == "재측정": self.recalibrate_btn = btn
            elif btn_name == "종료": self.stop_btn = btn
            
        footer_layout.addLayout(button_layout)
        layout.addLayout(footer_layout)

        # 세션 종료 후 버튼
        self.post_stop_button_layout = QHBoxLayout()
        self.restart_btn = QPushButton("다시 시작")
        self.restart_btn.setFixedSize(self.theme_manager.scale_pixel(120), self.theme_manager.scale_pixel(40))
        self.restart_btn.clicked.connect(self.detection_restart_signal.emit)
        self.results_btn = QPushButton("결과 보기")
        self.results_btn.setFixedSize(self.theme_manager.scale_pixel(120), self.theme_manager.scale_pixel(40))
        self.results_btn.clicked.connect(self.view_results_signal.emit)
        self.post_stop_button_layout.addStretch()
        self.post_stop_button_layout.addWidget(self.restart_btn)
        self.post_stop_button_layout.addWidget(self.results_btn)
        self.post_stop_button_layout.addStretch()
        self.restart_btn.hide(); self.results_btn.hide()
        layout.addLayout(self.post_stop_button_layout)
        
        self.setLayout(layout)

    def _on_frame_processed(self, frame_data: dict):
        if self.is_session_stopped:
            return
        if frame_data.get("posture_type") == "baseline":
            return

        # 세션 기록은 UI 렌더링과 독립적으로 먼저 수행
        try:
            if self.session_manager and getattr(self.session_manager, "current_session", None) is not None:
                self.session_manager.add_frame_data(frame_data)
        except Exception as e:
            logger.error(f"프레임 기록 실패: {e}")

        # UI 업데이트
        try:
            if self._waiting_for_first_frame:
                self._waiting_for_first_frame = False
                self._preview_stack.setCurrentIndex(1)
            annotated_frame = frame_data.get("frame")
            if annotated_frame is not None:
                pixmap = cv2_to_qpixmap(annotated_frame)
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
            else:
                set_recognition_message(self.recognition_label, False)
                self._update_posture_status(
                    frame_data.get("state", "NORMAL"),
                    frame_data.get("posture_type", "normal"),
                    frame_data.get("probability", 0.0),
                    frame_data.get("display_label", ""),
                )

                current_cheek = indicators.cheek_distance
                if self.baseline_manager and indicators.shoulder_width is not None:
                    expected_cheek = self.baseline_manager.get_expected_cheek(indicators.shoulder_width)
                    deviation = (current_cheek - expected_cheek) / expected_cheek if expected_cheek > 0 else 0
                    self.cheek_detail_label.setText(f"광대 거리: {current_cheek:.3f} (예상: {expected_cheek:.3f}, 편차: {deviation*100:+.1f}%)")
                else:
                    self.cheek_detail_label.setText(f"광대 거리: {current_cheek:.3f} (어깨 미감지)")

                dist_cm = indicators.eye_screen_distance_cm
                if dist_cm is not None:
                    self.distance_label.setText(f"화면 거리: {dist_cm:.1f} cm")
                else:
                    self.distance_label.setText("화면 거리: - cm")

                # 고개 각도 표시
                current_pitch = indicators.face_pitch_deg
                if self.baseline_manager:
                    baseline_metrics = self.baseline_manager.get_baseline_metrics()
                    if baseline_metrics and "face_pitch_deg" in baseline_metrics.metrics:
                        base_pitch = baseline_metrics.metrics["face_pitch_deg"]
                        pitch_diff = current_pitch - base_pitch
                        self.pitch_label.setText(f"고개 각도: {current_pitch:+.1f}° (편차: {pitch_diff:+.1f}°)")
                    else:
                        self.pitch_label.setText(f"고개 각도: {current_pitch:+.1f}° (기준 없음)")
                else:
                    self.pitch_label.setText(f"고개 각도: {current_pitch:+.1f}°")
        except Exception as e:
            logger.error(f"프레임 처리 오류: {e}")

    def _update_posture_status(self, state: str, posture_type: str, probability: float, display_label: str = ""):
        from src.config import get_config
        korean_label = display_label if display_label else get_config().get_posture_label(posture_type)
        self.posture_label.setText(f"{korean_label} ({probability:.1%})")
        
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
        self.time_timer.stop()
        self.pause_btn.setText("일시정지")
        self.is_detection_paused = False
        self.detection_stopped_signal.emit()

    def on_detection_started(self):
        self.is_session_stopped = False
        self.is_detection_paused = False
        self._waiting_for_first_frame = True
        self._preview_stack.setCurrentIndex(0)
        
        self.status_label.setText("바른 자세")
        self.status_label.setObjectName("status_normal")
        self.status_label.style().polish(self.status_label)
        
        # 자세 라벨 초기화
        self.posture_label.setText("감지 중")
        self.posture_label.setStyleSheet("")
        
        # 안내 박스 숨김
        self.session_msg_label.hide()
        
        self.cheek_detail_label.setText("광대 거리: - (예상: -)")
        self.distance_label.setText("화면 거리: - cm")
        self.pause_btn.setText("일시정지")
        self.pause_btn.setEnabled(True)
        self.recalibrate_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        
        try:
            self.restart_btn.hide()
            self.results_btn.hide()
        except: pass
        
        self._update_elapsed_time()
        self.time_timer.start(1000)

    def on_detection_stopped(self):
        """감지 중단 시 UI 처리 (마지막 자세 유지 + 강조 안내 박스)"""
        self.is_session_stopped = True
        self.time_timer.stop()
        self.is_detection_paused = False
        
        self.pause_btn.setEnabled(False)
        self.recalibrate_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        
        self.status_label.setText("세션 종료됨")
        self.status_label.setObjectName("status_warning")
        self.status_label.style().polish(self.status_label)
        
        # 1. 마지막 자세 텍스트 유지 (글자색만 변경)
        self.posture_label.setStyleSheet("color: #888888;")
        
        # 2. 강조 안내 박스 활성화 (보라색 테마 적용)
        self.session_msg_label.setText("감지가 종료되었습니다.\n아래 버튼으로 다시 시작하거나 결과를 확인하세요.")
        self.session_msg_label.setStyleSheet(f"""
            QLabel {{
                color: #FFFFFF;
                background-color: {Colors.PURPLE_PRIMARY.value}; 
                border: 2px solid #E3DCFF;
                border-radius: 12px;
                padding: 15px;
                margin-top: 15px;
            }}
        """)
        self.session_msg_label.show()
        
        # 버튼 보이기
        try:
            self.restart_btn.show()
            self.results_btn.show()
        except: pass

    def showEvent(self, event):
        super().showEvent(event)
        if self.camera_worker and self.camera_worker.is_running and not self.is_detection_paused: self.time_timer.start(1000)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.time_timer.stop()

    def _on_camera_error(self, error_msg: str):
        self.is_session_stopped = True
        self.preview_label.setText(f"오류: {error_msg}")
        self.status_label.setText("카메라 오류")
        self.time_timer.stop()
        self.pause_btn.setText("일시정지")
        self.is_detection_paused = False
