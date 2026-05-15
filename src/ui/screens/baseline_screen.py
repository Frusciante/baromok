import logging
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget
)
from src.ui.styles.theme import Colors, ThemeManager
from src.ui.widgets.chart_widgets import CalibrationScatterChart
from .helpers import set_recognition_message, cv2_to_qpixmap

logger = logging.getLogger(__name__)

class BaselineScreen(QWidget):
    """초기 바른자세 촬영 화면 (20단계 Move-Burst 모델)"""

    baseline_captured_signal = pyqtSignal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        camera_worker=None,
        baseline_manager=None,
        sound_manager=None,
    ):
        super().__init__()
        self.theme_manager = theme_manager
        self.camera_worker = camera_worker
        self.baseline_manager = baseline_manager
        self.sound_manager = sound_manager

        # 기본값 설정
        self.total_steps = 20
        self.wait_seconds = 5.0
        self.collect_seconds = 1.0
        
        # 설정에서 캘리브레이션 파라미터 로드
        if self.baseline_manager and self.baseline_manager.config:
            baseline_config = self.baseline_manager.config.get_baseline_config()
            capture_config = baseline_config.get("capture", {})
            self.total_steps = capture_config.get("expected_samples", self.total_steps)
            self.wait_seconds = capture_config.get("wait_seconds", self.wait_seconds)
            self.collect_seconds = capture_config.get("collect_seconds", self.collect_seconds)

        self.current_step = 1
        self.step_state = "WAIT"
        self.step_ticks = 0
        self.total_elapsed_ticks = 0
        self.received_frame_count = 0
        self.valid_baseline_frame_count = 0
        self.is_capturing_baseline = False

        self.setup_ui()

        if self.camera_worker:
            self.camera_worker.frame_processed_signal.connect(self._on_frame_processed)
            self.camera_worker.error_signal.connect(self._on_camera_error)

    def setup_ui(self):
        """UI 구성 (가독성 개선 및 이중 진행 바 추가)"""
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)

        title = QLabel("카메라 거리 캘리브레이션")
        title.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(24), QFont.Weight.Bold)
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 카메라 프리뷰 영역
        # 프리뷰 및 그래프 영역
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # 1. 카메라 프리뷰
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet(f"""
            background-color: {Colors.WHITE.value};
            border: 2px solid {Colors.GRAY_MEDIUM.value};
            border-radius: 15px;
        """)
        self.preview_frame.setMinimumHeight(self.theme_manager.scale_pixel(380))
        preview_vbox = QVBoxLayout()
        self.preview_label = QLabel("카메라 프리뷰")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_vbox.addWidget(self.preview_label)
        self.preview_frame.setLayout(preview_vbox)
        content_layout.addWidget(self.preview_frame, 1)

        # 2. 실시간 데이터 그래프
        self.chart_frame = QFrame()
        self.chart_frame.setStyleSheet(f"""
            background-color: {Colors.WHITE.value};
            border: 2px solid {Colors.GRAY_MEDIUM.value};
            border-radius: 15px;
        """)
        chart_vbox = QVBoxLayout()
        self.calibration_chart = CalibrationScatterChart(self.theme_manager)
        chart_vbox.addWidget(self.calibration_chart)
        self.chart_frame.setLayout(chart_vbox)
        content_layout.addWidget(self.chart_frame, 1)

        layout.addLayout(content_layout, 1)

        # 메인 상태 안내 (크고 강조됨)
        self.main_status_label = QLabel("준비")
        self.main_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_status_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(28), QFont.Weight.Bold)
        )
        self.main_status_label.setStyleSheet(f"color: {Colors.PRIMARY.value};")
        layout.addWidget(self.main_status_label)

        self.sub_status_label = QLabel("캘리브레이션 시작 버튼을 눌러주세요")
        self.sub_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_status_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(16))
        )
        self.sub_status_label.setStyleSheet(f"color: {Colors.GRAY_DARK.value};")
        layout.addWidget(self.sub_status_label)

        # 진행 바 영역
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(8)

        # 1. 전체 단계 진행 (전체 20단계 중 위치)
        step_header = QHBoxLayout()
        self.step_label = QLabel(f"전체 진행도: 0 / {self.total_steps}")
        self.step_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(12), QFont.Weight.Bold))
        step_header.addWidget(self.step_label)
        step_header.addStretch()
        progress_layout.addLayout(step_header)
        
        self.total_progress_bar = QProgressBar()
        self.total_progress_bar.setMaximum(self.total_steps)
        self.total_progress_bar.setValue(0)
        self.total_progress_bar.setTextVisible(False)
        self.total_progress_bar.setFixedHeight(self.theme_manager.scale_pixel(12))
        progress_layout.addWidget(self.total_progress_bar)

        # 2. 현재 단계 내 진행 (대기 시간 또는 수집 시간)
        self.detail_label = QLabel("준비 중")
        self.detail_label.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(11)))
        progress_layout.addWidget(self.detail_label)
        
        self.step_progress_bar = QProgressBar()
        self.step_progress_bar.setMaximum(100)
        self.step_progress_bar.setValue(0)
        self.step_progress_bar.setTextVisible(False)
        self.step_progress_bar.setFixedHeight(self.theme_manager.scale_pixel(8))
        progress_layout.addWidget(self.step_progress_bar)
        
        layout.addLayout(progress_layout)

        # 인식 안내 레이블
        self.recognition_label = QLabel("")
        self.recognition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recognition_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(12), QFont.Weight.Bold)
        )
        self.recognition_label.setStyleSheet(f"color: {Colors.RED_DANGER.value};")
        set_recognition_message(self.recognition_label, False)
        layout.addWidget(self.recognition_label)

        # 시작 버튼
        self.capture_btn = QPushButton("캘리브레이션 시작")
        self.capture_btn.setFixedHeight(self.theme_manager.scale_pixel(60))
        self.capture_btn.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(18), QFont.Weight.Bold)
        )
        self.capture_btn.clicked.connect(self.start_capture)
        layout.addWidget(self.capture_btn)

        self.setLayout(layout)

        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self._update_progress)

    def start_capture(self):
        """촬영 시작"""
        if self.camera_worker is None:
            logger.warning("카메라 워커 없음")
            self.preview_label.setText("카메라 워커가 없습니다.")
            return

        if self.baseline_manager is None:
            logger.warning("BaselineManager 없음")
            self.preview_label.setText("BaselineManager가 없습니다.")
            return

        self.current_step = 1
        self.step_state = "WAIT"
        self.step_ticks = 0
        self.total_elapsed_ticks = 0
        self.received_frame_count = 0
        self.valid_baseline_frame_count = 0
        self.is_capturing_baseline = True

        self.total_progress_bar.setValue(0)
        self.step_progress_bar.setValue(0)
        self.step_label.setText(f"전체 진행도: 0 / {self.total_steps}")

        self.capture_btn.setEnabled(False)
        self.main_status_label.setText("준비")
        self.sub_status_label.setText("잠시 후 시작합니다...")

        if self.camera_worker.is_paused:
            self.camera_worker.resume()

        if hasattr(self.camera_worker, "set_baseline_mode"):
            self.camera_worker.set_baseline_mode(True)

        self.baseline_manager.start_baseline_collection()

        if not self.camera_worker.isRunning():
            self.camera_worker.start()

        self.capture_timer.start(100)
        logger.info("캘리브레이션 캡처 시작")

    def _update_progress(self):
        """진행 상태 업데이트 (대기 ↔ 수집)"""
        if not self.is_capturing_baseline:
            return

        self.step_ticks += 1
        self.total_elapsed_ticks += 1

        if self.step_state == "WAIT":
            remaining = max(0.0, self.wait_seconds - (self.step_ticks / 10.0))
            progress = int((self.step_ticks / (self.wait_seconds * 10)) * 100)
            
            self.main_status_label.setText("이동 하세요")
            self.main_status_label.setStyleSheet(f"color: {Colors.PRIMARY.value};")
            self.sub_status_label.setText(f"다음 거리로 이동해 주세요... ({remaining:.1f}초)")
            self.detail_label.setText(f"현재 단계({self.current_step}) 이동 대기 중")
            self.step_progress_bar.setValue(min(progress, 100))
            self.step_progress_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {Colors.GRAY_MEDIUM.value}; }}")
            
            if self.step_ticks >= int(self.wait_seconds * 10):
                self.step_state = "COLLECT"
                self.step_ticks = 0
                if self.camera_worker:
                    self.camera_worker.current_step = self.current_step
                if self.sound_manager:
                    self.sound_manager.play_beep(1000, 300) # 수집 시작 알림
                
        elif self.step_state == "COLLECT":
            remaining = max(0.0, self.collect_seconds - (self.step_ticks / 10.0))
            progress = int((self.step_ticks / (self.collect_seconds * 10)) * 100)
            
            self.main_status_label.setText("정지 하세요")
            self.main_status_label.setStyleSheet(f"color: {Colors.RED_DANGER.value};")
            self.sub_status_label.setText(f"가만히 자세를 유지해 주세요... ({remaining:.1f}초)")
            self.detail_label.setText(f"현재 단계({self.current_step}) 데이터 수집 중")
            self.step_progress_bar.setValue(min(progress, 100))
            self.step_progress_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {Colors.SECONDARY.value}; }}")
            
            if self.step_ticks >= int(self.collect_seconds * 10):
                self.total_progress_bar.setValue(self.current_step)
                self.step_label.setText(f"전체 진행도: {self.current_step} / {self.total_steps}")
                
                self.current_step += 1
                if self.camera_worker:
                    self.camera_worker.current_step = 0 # 대기 상태로 초기화
                
                if self.current_step > self.total_steps:
                    if self.sound_manager:
                        self.sound_manager.play_beep(1200, 500) # 전체 완료
                    self._finish_capture()
                else:
                    self.step_state = "WAIT"
                    self.step_ticks = 0
                    if self.sound_manager:
                        self.sound_manager.play_beep(600, 200) # 다음 단계 이동 알림

    def _on_frame_processed(self, frame_data: dict):
        """프레임 처리 완료 시 호출"""
        try:
            annotated_frame = frame_data.get("frame")
            if annotated_frame is not None:
                pixmap = cv2_to_qpixmap(annotated_frame)
                scaled_pixmap = pixmap.scaled(
                    self.preview_frame.width() - 4,
                    self.preview_frame.height() - 4,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled_pixmap)

            if not self.is_capturing_baseline or self.baseline_manager is None or not self.baseline_manager.is_collecting:
                return

            indicators = frame_data.get("indicators")
            
            if self.step_state == "WAIT":
                set_recognition_message(self.recognition_label, indicators is None)
                return

            self.received_frame_count += 1
            if indicators is None:
                set_recognition_message(self.recognition_label, True)
                return

            set_recognition_message(self.recognition_label, False)
            
            # 실시간 차트 업데이트 (이동 중엔 커서만, 수집 중엔 점 추가)
            self.calibration_chart.update_live_point(
                indicators.shoulder_width, 
                indicators.cheek_distance, 
                is_collecting=(self.step_state == "COLLECT"),
                step=self.current_step,
                total_steps=self.total_steps
            )

            if self.step_state == "WAIT":
                return

            self.received_frame_count += 1
            self.baseline_manager.add_frame_to_collection(indicators)
            self.valid_baseline_frame_count += 1
        except Exception as e:
            logger.error(f"프리뷰 업데이트 실패: {e}")

    def _finish_capture(self):
        """캡처 완료 처리"""
        if not self.is_capturing_baseline: return
        self.is_capturing_baseline = False
        self.capture_timer.stop()
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.stop_capture()
        
        actual_elapsed_seconds = max(1.0, self.total_steps * self.collect_seconds)
        actual_fps = max(1, int(self.valid_baseline_frame_count / actual_elapsed_seconds))
        
        success = False
        if self.baseline_manager: 
            success = self.baseline_manager.finish_baseline_collection(fps=actual_fps)
            
        if self.camera_worker and hasattr(self.camera_worker, "set_baseline_mode"):
            self.camera_worker.set_baseline_mode(False)
            
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("캘리브레이션 시작")
        
        if success:
            self.total_progress_bar.setValue(self.total_steps)
            self.main_status_label.setText("분석 완료")
            self.main_status_label.setStyleSheet(f"color: {Colors.SECONDARY.value};")
            self.sub_status_label.setText(f"총 {self.valid_baseline_frame_count}개 유효 데이터 수집됨")
            self.baseline_captured_signal.emit()
        else:
            self.main_status_label.setText("학습 실패")
            self.main_status_label.setStyleSheet(f"color: {Colors.RED_DANGER.value};")
            self.sub_status_label.setText("데이터가 부족합니다.")
            self.preview_label.setText("캘리브레이션에 실패했습니다.\n더 다양한 거리에서 정확한 자세를 유지하며 다시 시도해 주세요.")

    def _fail_capture(self, message: str):
        """캡처 실패 처리"""
        self.is_capturing_baseline = False
        self.capture_timer.stop()
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.stop_capture()
        if self.baseline_manager: self.baseline_manager.reset()
        if self.camera_worker and hasattr(self.camera_worker, "set_baseline_mode"):
            self.camera_worker.set_baseline_mode(False)
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("다시 시작")
        self.total_progress_bar.setValue(0)
        self.step_progress_bar.setValue(0)
        self.main_status_label.setText("오류 발생")
        self.sub_status_label.setText(message)

    def _on_camera_error(self, error_msg: str):
        """카메라 오류 처리"""
        logger.error(f"카메라 오류 신호: {error_msg}")
        self._fail_capture(f"카메라 오류: {error_msg}")
