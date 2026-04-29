"""UI 화면 모듈"""
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QImage
import logging

from src.ui.styles.theme import ThemeManager, Colors

logger = logging.getLogger(__name__)


def cv2_to_qpixmap(frame: np.ndarray) -> QPixmap:
    """OpenCV 프레임을 QPixmap으로 변환"""
    try:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qt_image)
    except Exception as e:
        logger.error(f"프레임 변환 실패: {e}")
        return QPixmap()


class BaselineScreen(QWidget):
    """초기 바른자세 촬영 화면"""
    
    baseline_captured_signal = pyqtSignal()
    
    def __init__(self, theme_manager: ThemeManager, camera_worker=None):
        super().__init__()
        self.theme_manager = theme_manager
        self.camera_worker = camera_worker
        self.capture_duration = 50
        self.capture_elapsed = 0
        self.setup_ui()
        
        if self.camera_worker:
            self.camera_worker.frame_processed_signal.connect(self._on_frame_processed)
            self.camera_worker.error_signal.connect(self._on_camera_error)
    
    def setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        title = QLabel("초기 바른자세 촬영")
        title.setFont(QFont("Segoe UI", self.theme_manager.scale_pixel(24), QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet(f"""
            background-color: {Colors.WHITE.value};
            border: 1px solid {Colors.GRAY_MEDIUM.value};
            border-radius: 10px;
        """)
        self.preview_frame.setMinimumHeight(self.theme_manager.scale_pixel(400))
        preview_layout = QVBoxLayout()
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setText("카메라 프리뷰")
        self.preview_label.setStyleSheet(f"color: {Colors.GRAY_DARK.value};")
        preview_layout.addWidget(self.preview_label)
        self.preview_frame.setLayout(preview_layout)
        layout.addWidget(self.preview_frame, 1)
        
        guide = QLabel(
            "바른 자세로 촬영하세요:\n"
            "• 카메라와 거리: 50-60cm\n"
            "• 등 & 허리: 의자에 붙인 상태\n"
            "• 무릎: 90도\n"
            "• 팔꿈치: 90도\n"
            "• 턱: 자연스러운 위치"
        )
        guide.setFont(QFont("Segoe UI", self.theme_manager.scale_pixel(12)))
        layout.addWidget(guide)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        self.capture_btn = QPushButton("촬영 시작")
        self.capture_btn.setFixedHeight(self.theme_manager.scale_pixel(50))
        self.capture_btn.setFont(QFont("Segoe UI", self.theme_manager.scale_pixel(16), QFont.Weight.Bold))
        self.capture_btn.clicked.connect(self.start_capture)
        layout.addWidget(self.capture_btn)
        
        self.setLayout(layout)
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self._update_progress)
    
    def start_capture(self):
        """촬영 시작"""
        if self.camera_worker is None:
            logger.warning("카메라 워커 없음")
            return
        
        self.capture_elapsed = 0
        self.progress_bar.setValue(0)
        self.capture_btn.setEnabled(False)
        self.capture_btn.setText("촬영 중... (5초)")
        
        self.camera_worker.start()
        self.capture_timer.start(100)
        logger.info("초기화 촬영 시작")
    
    def _update_progress(self):
        """진행바 업데이트"""
        self.capture_elapsed += 1
        progress = int((self.capture_elapsed / self.capture_duration) * 100)
        self.progress_bar.setValue(min(progress, 100))
        
        if self.capture_elapsed >= self.capture_duration:
            self.capture_timer.stop()
            self.camera_worker.stop_capture()
            self.capture_btn.setEnabled(True)
            self.capture_btn.setText("촬영 시작")
            logger.info("초기화 촬영 완료")
            self.baseline_captured_signal.emit()
    
    def _on_frame_processed(self, frame_data: dict):
        """프레임 처리 완료 시 호출"""
        try:
            annotated_frame = frame_data.get('frame')
            if annotated_frame is not None:
                pixmap = cv2_to_qpixmap(annotated_frame)
                scaled_pixmap = pixmap.scaledToWidth(
                    self.preview_frame.width() - 4,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.preview_label.setPixmap(scaled_pixmap)
        except Exception as e:
            logger.error(f"프리뷰 업데이트 실패: {e}")
    
    def _on_camera_error(self, error_msg: str):
        """카메라 오류"""
        logger.error(f"카메라 오류: {error_msg}")
        self.capture_timer.stop()
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("촬영 시작")
        self.preview_label.setText(f"오류: {error_msg}")


class HubScreen(QWidget):
    """메인 허브 화면"""
    
    start_detection_signal = pyqtSignal()
    open_settings_signal = pyqtSignal()
    open_statistics_signal = pyqtSignal()
    
    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.theme_manager = theme_manager
        self.setup_ui()
    
    def setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        illust = QLabel("[일러스트 영역]")
        illust.setAlignment(Qt.AlignmentFlag.AlignCenter)
        illust.setMinimumHeight(self.theme_manager.scale_pixel(300))
        illust.setStyleSheet(f"background-color: {Colors.GRAY_LIGHT.value};")
        layout.addWidget(illust, 1)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        settings_btn = QPushButton("환경 설정")
        settings_btn.setFixedSize(*self.theme_manager.get_button_size())
        settings_btn.clicked.connect(self.open_settings_signal.emit)
        button_layout.addWidget(settings_btn)
        
        stats_btn = QPushButton("나의 통계")
        stats_btn.setFixedSize(*self.theme_manager.get_button_size())
        stats_btn.clicked.connect(self.open_statistics_signal.emit)
        button_layout.addWidget(stats_btn)
        
        layout.addLayout(button_layout)
        
        start_btn = QPushButton("바로록 감지 시작")
        start_btn.setFixedHeight(self.theme_manager.scale_pixel(50))
        start_btn.setFont(QFont("Segoe UI", self.theme_manager.scale_pixel(16), QFont.Weight.Bold))
        start_btn.clicked.connect(self.start_detection_signal.emit)
        layout.addWidget(start_btn)
        
        self.setLayout(layout)


class SettingsScreen(QWidget):
    """환경 설정 화면"""
    
    settings_saved_signal = pyqtSignal(dict)
    back_to_hub_signal = pyqtSignal()
    
    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.theme_manager = theme_manager
        self.setup_ui()
    
    def setup_ui(self):
        """UI 구성"""
        layout = QHBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        left_layout = QVBoxLayout()
        categories = ["알림 설정", "소리 설정", "팝업 설정", "자동 시작"]
        for cat in categories:
            btn = QPushButton(cat)
            btn.setFixedHeight(self.theme_manager.scale_pixel(40))
            btn.setObjectName("secondary")
            left_layout.addWidget(btn)
        left_layout.addStretch()
        layout.addLayout(left_layout)
        
        right_layout = QVBoxLayout()
        right_label = QLabel("[설정값 UI]\n(향후 구현)")
        right_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(right_label, 1)
        
        confirm_btn = QPushButton("확인")
        confirm_btn.setFixedHeight(self.theme_manager.scale_pixel(40))
        confirm_btn.clicked.connect(self._save_settings)
        right_layout.addWidget(confirm_btn)
        
        layout.addLayout(right_layout, 1)
        self.setLayout(layout)
    
    def _save_settings(self):
        """설정 저장"""
        self.settings_saved_signal.emit({})


class StatisticsScreen(QWidget):
    """통계 화면"""
    
    back_to_hub_signal = pyqtSignal()
    
    def __init__(self, theme_manager: ThemeManager, session_manager=None):
        super().__init__()
        self.theme_manager = theme_manager
        self.session_manager = session_manager
        self.setup_ui()
    
    def setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        title = QLabel("최근 10개 세션 바른자세 유지율")
        title.setFont(QFont("Segoe UI", self.theme_manager.scale_pixel(18), QFont.Weight.Bold))
        layout.addWidget(title)
        
        chart = QLabel("[차트 영역]\n(Phase 5에서 matplotlib/PyQtGraph)")
        chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart.setMinimumHeight(self.theme_manager.scale_pixel(350))
        chart.setStyleSheet(f"background-color: {Colors.WHITE.value};")
        layout.addWidget(chart, 1)
        
        avg_text = "데이터 없음"
        if self.session_manager:
            recent = self.session_manager.load_recent_sessions(1)
            if recent:
                avg_pct = recent[0].statistics.get('good_posture_percentage', 0)
                avg_text = f"평균 유지율: {avg_pct:.1f}%"
        
        avg_label = QLabel(avg_text)
        avg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avg_label.setFont(QFont("Segoe UI", self.theme_manager.scale_pixel(14), QFont.Weight.Bold))
        layout.addWidget(avg_label)
        
        back_btn = QPushButton("돌아가기")
        back_btn.setFixedHeight(self.theme_manager.scale_pixel(40))
        back_btn.clicked.connect(self.back_to_hub_signal.emit)
        layout.addWidget(back_btn)
        
        self.setLayout(layout)


class DetectionScreen(QWidget):
    """감지 진행 화면"""
    
    detection_paused_signal = pyqtSignal()
    detection_stopped_signal = pyqtSignal()
    
    def __init__(self, theme_manager: ThemeManager, camera_worker=None, session_manager=None):
        super().__init__()
        self.theme_manager = theme_manager
        self.camera_worker = camera_worker
        self.session_manager = session_manager
        self.start_time = None
        self.elapsed_time = 0
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
        self.status_label.setFont(QFont("Segoe UI", self.theme_manager.scale_pixel(14), QFont.Weight.Bold))
        self.status_label.setObjectName("status_normal")
        top_layout.addWidget(self.status_label)
        top_layout.addStretch()
        settings_btn = QPushButton("⚙ 설정")
        settings_btn.setFixedHeight(self.theme_manager.scale_pixel(32))
        top_layout.addWidget(settings_btn)
        layout.addLayout(top_layout)
        
        self.time_label = QLabel("00:00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setFont(QFont("Segoe UI", self.theme_manager.scale_pixel(48), QFont.Weight.Bold))
        layout.addWidget(self.time_label)
        
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet(f"""
            background-color: {Colors.WHITE.value};
            border: 1px solid {Colors.GRAY_MEDIUM.value};
        """)
        self.preview_frame.setMinimumHeight(self.theme_manager.scale_pixel(300))
        preview_layout = QVBoxLayout()
        self.preview_label = QLabel("[카메라 프리뷰]")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_label)
        self.preview_frame.setLayout(preview_layout)
        layout.addWidget(self.preview_frame, 1)
        
        self.posture_label = QLabel("감지 중")
        self.posture_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.posture_label.setFont(QFont("Segoe UI", self.theme_manager.scale_pixel(16), QFont.Weight.Bold))
        layout.addWidget(self.posture_label)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        pause_btn = QPushButton("일시정지")
        pause_btn.setFixedHeight(self.theme_manager.scale_pixel(40))
        pause_btn.clicked.connect(self._pause_detection)
        button_layout.addWidget(pause_btn)
        
        stop_btn = QPushButton("종료")
        stop_btn.setFixedHeight(self.theme_manager.scale_pixel(40))
        stop_btn.setObjectName("danger")
        stop_btn.clicked.connect(self._stop_detection)
        button_layout.addWidget(stop_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _on_frame_processed(self, frame_data: dict):
        """프레임 처리 완료 시 호출"""
        try:
            annotated_frame = frame_data.get('frame')
            if annotated_frame is not None:
                pixmap = cv2_to_qpixmap(annotated_frame)
                scaled_pixmap = pixmap.scaledToWidth(
                    self.preview_frame.width() - 4,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.preview_label.setPixmap(scaled_pixmap)
            
            state = frame_data.get('state', 'NORMAL')
            posture_type = frame_data.get('posture_type', 'normal')
            probability = frame_data.get('probability', 0.0)
            self._update_posture_status(state, posture_type, probability)
            
            if self.session_manager:
                self.session_manager.add_frame_data(frame_data)
        
        except Exception as e:
            logger.error(f"프레임 처리 오류: {e}")
    
    def _update_posture_status(self, state: str, posture_type: str, probability: float):
        """자세 상태 업데이트"""
        posture_map = {
            'normal': '바른 자세',
            'forward_head': '거북목',
            'recline': '기댄 자세',
            'crossed_leg_estimated': '다리 꼬기',
            'chin_rest_estimated': '턱 받침'
        }
        
        posture_text = posture_map.get(posture_type, '알 수 없음')
        self.posture_label.setText(f"{posture_text} ({probability:.1%})")
        
        state_colors = {
            'NORMAL': 'status_normal',
            'WARNING': 'status_warning',
            'BAD_POSTURE': 'status_bad'
        }
        self.status_label.setObjectName(state_colors.get(state, 'status_normal'))
        self.status_label.style().polish(self.status_label)
    
    def _update_elapsed_time(self):
        """경과 시간 업데이트"""
        if self.camera_worker:
            elapsed = self.camera_worker.get_elapsed_time()
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            self.time_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def _pause_detection(self):
        """일시정지"""
        if self.camera_worker:
            self.camera_worker.pause()
            self.time_timer.stop()
            self.detection_paused_signal.emit()
    
    def _stop_detection(self):
        """감지 중지"""
        if self.camera_worker:
            self.camera_worker.stop_capture()
            self.time_timer.stop()
            self.detection_stopped_signal.emit()
    
    def showEvent(self, event):
        """화면 표시 시"""
        super().showEvent(event)
        if self.camera_worker and self.camera_worker.is_running:
            self.time_timer.start(1000)
    
    def hideEvent(self, event):
        """화면 숨김 시"""
        super().hideEvent(event)
        self.time_timer.stop()
    
    def _on_camera_error(self, error_msg: str):
        """카메라 오류"""
        logger.error(f"카메라 오류: {error_msg}")
        self.preview_label.setText(f"오류: {error_msg}")
        self.time_timer.stop()


class AlertPopup(QWidget):
    """알림 팝업 (배너 & 토스트)"""
    
    close_signal = pyqtSignal()
    
    def __init__(self, theme_manager: ThemeManager, alert_type: str = "warning"):
        super().__init__()
        self.theme_manager = theme_manager
        self.alert_type = alert_type
        self.setup_ui()
    
    def setup_ui(self):
        """UI 구성"""
        layout = QHBoxLayout()
        layout.setContentsMargins(
            self.theme_manager.scale_pixel(12),
            self.theme_manager.scale_pixel(8),
            self.theme_manager.scale_pixel(12),
            self.theme_manager.scale_pixel(8)
        )
        layout.setSpacing(10)
        
        color_map = {
            "warning": Colors.YELLOW_WARNING.value,
            "danger": Colors.RED_DANGER.value,
            "info": Colors.PURPLE_PRIMARY.value
        }
        bg_color = color_map.get(self.alert_type, Colors.YELLOW_WARNING.value)
        
        self.setStyleSheet(f"""
            background-color: {bg_color};
            border-radius: 5px;
        """)
        
        message = QLabel("알림 메시지")
        message.setFont(QFont("Segoe UI", self.theme_manager.scale_pixel(12), QFont.Weight.Bold))
        message.setStyleSheet(f"color: {Colors.WHITE.value};")
        layout.addWidget(message, 1)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(
            self.theme_manager.scale_pixel(24),
            self.theme_manager.scale_pixel(24)
        )
        close_btn.setStyleSheet(f"""
            background-color: rgba(255, 255, 255, 0.3);
            color: {Colors.WHITE.value};
            border: none;
            border-radius: 3px;
        """)
        close_btn.clicked.connect(self.close_signal.emit)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
        self.setFixedHeight(self.theme_manager.scale_pixel(40))
