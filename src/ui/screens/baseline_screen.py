import logging
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QWidget, QSizePolicy
)
from src.ui.styles.theme import Colors, ThemeManager
from src.ui.styles.font_loader import app_font
from src.ui.widgets.chart_widgets import CalibrationScatterChart
from .helpers import set_recognition_message, cv2_to_qpixmap

logger = logging.getLogger(__name__)

class BaselineScreen(QWidget):
    """초기 바른자세 촬영 화면 (20단계 Move-Burst 모델)"""

    baseline_captured_signal = pyqtSignal()
    baseline_recommended_signal = pyqtSignal(float, float) # (forward_head, recline)

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
        
        # 설정에서 자세 맞춤 파라미터 로드
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
        self.current_remaining_sec = 0.0

        self.setup_ui()

        if self.camera_worker:
            self.camera_worker.frame_processed_signal.connect(self._on_frame_processed)
            self.camera_worker.error_signal.connect(self._on_camera_error)

    def setup_ui(self):
        """UI 구성 (가독성 개선 및 이중 진행 바 추가)"""
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)

        # 메인 콘텐츠 영역 (카메라 | 차트+정보)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # 1. 왼쪽: 카메라 프리뷰 (고정 크기 — 영상 크기에 따라 흔들리지 않도록)
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet(f"""
            background-color: {Colors.WHITE.value};
            border: 2px solid {Colors.GRAY_MEDIUM.value};
            border-radius: 15px;
        """)
        self.preview_frame.setFixedHeight(self.theme_manager.scale_pixel(420))
        preview_vbox = QVBoxLayout()
        preview_vbox.setContentsMargins(8, 8, 8, 8)
        self.preview_label = QLabel("카메라 프리뷰")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 픽스맵 크기가 레이아웃에 영향을 주지 않도록 — 박스 위치 고정
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        self.preview_label.setMinimumSize(1, 1)
        self.preview_label.setStyleSheet("border: none; background-color: transparent;")
        preview_vbox.addWidget(self.preview_label)
        self.preview_frame.setLayout(preview_vbox)
        content_layout.addWidget(self.preview_frame, 3) # 비율 조절

        # 2. 오른쪽: 그래프 및 실시간 상태 정보
        self.info_panel = QVBoxLayout()
        self.info_panel.setSpacing(15)

        # 2-1. 실시간 데이터 그래프
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
        self.info_panel.addWidget(self.chart_frame, 1)

        # 2-2. 상태 안내 및 진행바 (그래프 바로 아래 공간 활용)
        self.status_card = QFrame()
        self.status_card.setStyleSheet(f"""
            background-color: #F8F9FF;
            border-radius: 12px;
            border: 1px solid #E3E0F2;
        """)
        status_vbox = QVBoxLayout()
        status_vbox.setContentsMargins(15, 15, 15, 15)
        status_vbox.setSpacing(10)

        self.main_status_label = QLabel("준비")
        self.main_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_status_label.setFont(app_font(self.theme_manager.scale_pixel(25), QFont.Weight.Bold))
        self.main_status_label.setStyleSheet(f"color: {Colors.PRIMARY.value}; border: none; background-color: transparent;")
        status_vbox.addWidget(self.main_status_label)

        self.sub_status_label = QLabel("자세 맞춤 시작을 눌러주세요")
        self.sub_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_status_label.setFont(app_font(self.theme_manager.scale_pixel(16)))
        self.sub_status_label.setStyleSheet("border: none; background-color: transparent;")
        status_vbox.addWidget(self.sub_status_label)

        # 진행 바
        self.step_progress_bar = QProgressBar()
        self.step_progress_bar.setMaximum(100)
        self.step_progress_bar.setValue(0)
        self.step_progress_bar.setTextVisible(False)
        self.step_progress_bar.setFixedHeight(self.theme_manager.scale_pixel(10))
        status_vbox.addWidget(self.step_progress_bar)

        self.step_label = QLabel(f"전체 진행: 0 / {self.total_steps}")
        self.step_label.setFont(app_font(self.theme_manager.scale_pixel(14), QFont.Weight.Bold))
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.step_label.setStyleSheet("border: none; background-color: transparent;")
        status_vbox.addWidget(self.step_label)

        self.total_progress_bar = QProgressBar()
        self.total_progress_bar.setMaximum(self.total_steps)
        self.total_progress_bar.setValue(0)
        self.total_progress_bar.setTextVisible(False)
        self.total_progress_bar.setFixedHeight(self.theme_manager.scale_pixel(6))
        status_vbox.addWidget(self.total_progress_bar)

        self.status_card.setLayout(status_vbox)
        self.info_panel.addWidget(self.status_card)

        content_layout.addLayout(self.info_panel, 2)
        layout.addLayout(content_layout, 1)

        # 하단 안내 및 버튼
        self.recognition_label = QLabel("")
        self.recognition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recognition_label.setFont(app_font(self.theme_manager.scale_pixel(15), QFont.Weight.Bold))
        self.recognition_label.setStyleSheet(f"color: {Colors.RED_DANGER.value}; border: none; background-color: transparent;")
        set_recognition_message(self.recognition_label, False)
        layout.addWidget(self.recognition_label)

        self.capture_btn = QPushButton("자세 맞춤 시작")
        self.capture_btn.setFixedHeight(self.theme_manager.scale_pixel(56))
        self.capture_btn.setFont(app_font(self.theme_manager.scale_pixel(21), QFont.Weight.Bold))
        self.capture_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PURPLE_PRIMARY.value};
                color: {Colors.WHITE.value};
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: #5343B6;
            }}
        """)
        self.capture_btn.clicked.connect(self.start_capture)
        layout.addWidget(self.capture_btn)

        self.setLayout(layout)

        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self._update_progress)

    def start_capture(self):
        """촬영 시작"""
        if self.camera_worker is None or self.baseline_manager is None:
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
        self.step_label.setText(f"전체 진행: 0 / {self.total_steps}")

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
        logger.info("자세 맞춤 캡처 시작")

    def _update_progress(self):
        """진행 상태 업데이트 (대기 ↔ 수집)"""
        if not self.is_capturing_baseline:
            return

        self.step_ticks += 1
        self.total_elapsed_ticks += 1

        if self.step_state == "WAIT":
            remaining = max(0.0, self.wait_seconds - (self.step_ticks / 10.0))
            self.current_remaining_sec = remaining
            progress = int((self.step_ticks / (self.wait_seconds * 10)) * 100)
            
            self.main_status_label.setText("이동 하세요")
            self.main_status_label.setStyleSheet(f"color: {Colors.PRIMARY.value}; border: none; background-color: transparent;")
            self.sub_status_label.setText(f"다음 거리로 이동해 주세요... ({remaining:.1f}초)")
            self.step_progress_bar.setValue(min(progress, 100))
            self.step_progress_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {Colors.PRIMARY.value}; }}")
            
            if self.step_ticks >= int(self.wait_seconds * 10):
                self.step_state = "COLLECT"
                self.step_ticks = 0
                if self.camera_worker:
                    self.camera_worker.current_step = self.current_step
                # Baseline 촬영 중 단계별 알림음은 제거 (UI 상태 업데이트만)
                
        elif self.step_state == "COLLECT":
            remaining = max(0.0, self.collect_seconds - (self.step_ticks / 10.0))
            self.current_remaining_sec = remaining
            progress = int((self.step_ticks / (self.collect_seconds * 10)) * 100)
            
            self.main_status_label.setText("정지 하세요")
            self.main_status_label.setStyleSheet(f"color: {Colors.RED_DANGER.value}; border: none; background-color: transparent;")
            self.sub_status_label.setText(f"가만히 자세를 유지해 주세요... ({remaining:.1f}초)")
            self.step_progress_bar.setValue(min(progress, 100))
            self.step_progress_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {Colors.RED_DANGER.value}; }}")
            
            if self.step_ticks >= int(self.collect_seconds * 10):
                self.total_progress_bar.setValue(self.current_step)
                self.step_label.setText(f"전체 진행: {self.current_step} / {self.total_steps}")
                
                self.current_step += 1
                if self.camera_worker:
                    self.camera_worker.current_step = 0
                
                if self.current_step > self.total_steps:
                    # Baseline 수집 완료 (소리 제거 - 사용자가 직관적으로 알 수 있도록 UI로만 표시)
                    self._finish_capture()
                else:
                    self.step_state = "WAIT"
                    self.step_ticks = 0
                    # Baseline 촬영 중 단계별 알림음은 제거

    def _on_frame_processed(self, frame_data: dict):
        """프레임 처리 완료 시 호출"""
        try:
            annotated_frame = frame_data.get("frame")
            if annotated_frame is not None:
                pixmap = cv2_to_qpixmap(annotated_frame)
                # 박스를 가득 채우도록 확대 후 좌우를 잘라 인물이 중앙에 보이게 함
                target = self.preview_label.size()
                scaled_pixmap = pixmap.scaled(
                    target,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.FastTransformation,
                )
                # 넘치는 영역을 중앙 기준으로 잘라 박스 크기에 맞춤
                x = max(0, (scaled_pixmap.width() - target.width()) // 2)
                y = max(0, (scaled_pixmap.height() - target.height()) // 2)
                scaled_pixmap = scaled_pixmap.copy(
                    x, y, target.width(), target.height()
                )
                self.preview_label.setPixmap(scaled_pixmap)

            if not self.is_capturing_baseline or self.baseline_manager is None or not self.baseline_manager.is_collecting:
                return

            indicators = frame_data.get("indicators")
            if indicators is None:
                set_recognition_message(self.recognition_label, True)
                return

            set_recognition_message(self.recognition_label, False)
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
        
        actual_fps = max(1, int(self.valid_baseline_frame_count / (self.total_steps * self.collect_seconds)))
        
        success = False
        if self.baseline_manager: 
            success = self.baseline_manager.finish_baseline_collection(fps=actual_fps)
            
        if self.camera_worker:
            self.camera_worker.set_baseline_mode(False)
            
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("자세 맞춤 시작")
        
        if success:
            self.total_progress_bar.setValue(self.total_steps)
            self.main_status_label.setText("분석 완료")
            self.main_status_label.setStyleSheet(f"color: {Colors.SECONDARY.value}; border: none; background-color: transparent;")
            self.sub_status_label.setText(f"총 {self.valid_baseline_frame_count}개 유효 데이터 수집됨")
            
            if self.baseline_manager:
                noise = self.baseline_manager.max_inlier_deviation
                rec_fwd = max(0.05, min(0.20, noise * 3.0))
                rec_rec = max(0.02, min(0.10, noise * 1.5))
                self.baseline_recommended_signal.emit(rec_fwd, rec_rec)

            self.baseline_captured_signal.emit()
        else:
            self.main_status_label.setText("학습 실패")
            self.main_status_label.setStyleSheet(f"color: {Colors.RED_DANGER.value}; border: none; background-color: transparent;")
            self.sub_status_label.setText("데이터가 부족합니다.")

    def cancel_capture(self):
        """진행 중인 자세 맞춤을 취소하고 초기 상태로 되돌린다."""
        if self.capture_timer.isActive():
            self.capture_timer.stop()

        self.is_capturing_baseline = False
        self.current_step = 1
        self.step_state = "WAIT"
        self.step_ticks = 0
        self.total_elapsed_ticks = 0
        self.received_frame_count = 0
        self.valid_baseline_frame_count = 0
        self.current_remaining_sec = 0.0

        if self.baseline_manager and getattr(self.baseline_manager, "is_collecting", False):
            self.baseline_manager.reset()

        if self.camera_worker and hasattr(self.camera_worker, "set_baseline_mode"):
            self.camera_worker.set_baseline_mode(False)

        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("자세 맞춤 시작")
        self.total_progress_bar.setValue(0)
        self.step_progress_bar.setValue(0)
        self.step_label.setText(f"전체 진행: 0 / {self.total_steps}")
        self.main_status_label.setText("준비")
        self.main_status_label.setStyleSheet(f"color: {Colors.PRIMARY.value}; border: none; background-color: transparent;")
        self.sub_status_label.setText("자세 맞춤 시작을 눌러주세요")
        set_recognition_message(self.recognition_label, False)

    def _fail_capture(self, message: str):
        self.is_capturing_baseline = False
        self.capture_timer.stop()
        if self.camera_worker: self.camera_worker.stop_capture()
        if self.baseline_manager: self.baseline_manager.reset()
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("다시 시작")
        self.main_status_label.setText("오류 발생")
        self.sub_status_label.setText(message)

    def _on_camera_error(self, error_msg: str):
        logger.error(f"카메라 오류 신호: {error_msg}")
        self._fail_capture(f"카메라 오류: {error_msg}")
