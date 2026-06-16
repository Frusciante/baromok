import logging
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QWidget, QSizePolicy, QDialog
)
from src.ui.styles.theme import Colors, ThemeManager
from src.ui.styles.font_loader import app_font
from .helpers import set_recognition_message, cv2_to_qpixmap

logger = logging.getLogger(__name__)


class BaselineFinishWorker(QThread):
    """QThread worker to finish baseline computation off the main thread."""

    started_signal = pyqtSignal()
    finished_signal = pyqtSignal(bool)

    def __init__(self, baseline_manager, fps: int = 30):
        super().__init__()
        self.baseline_manager = baseline_manager
        self.fps = fps

    def run(self):
        self.started_signal.emit()
        success = False
        try:
            if self.baseline_manager:
                success = self.baseline_manager.finish_baseline_collection(fps=self.fps)
        except Exception as e:
            logger.error(f"BaselineFinishWorker 예외: {e}", exc_info=True)
        self.finished_signal.emit(bool(success))



class BaselineScreen(QWidget):
    """초기 바른자세 촬영 화면 (20단계 Move-Burst 모델)"""

    baseline_captured_signal = pyqtSignal()
    baseline_recommended_signal = pyqtSignal(float, float)  # (forward_head, recline)

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
        self.wait_seconds = 3.0
        self.collect_seconds = 1.0

        # 설정에서 자세 맞춤 파라미터 로드
        if self.baseline_manager and self.baseline_manager.config:
            baseline_config = self.baseline_manager.config.get_baseline_config()
            capture_config = baseline_config.get("capture", {})
            self.total_steps = capture_config.get("expected_samples", self.total_steps)
            self.wait_seconds = capture_config.get("wait_seconds", self.wait_seconds)
            self.collect_seconds = capture_config.get(
                "collect_seconds", self.collect_seconds
            )

        self.current_step = 1
        self.step_state = "WAIT"
        self.step_ticks = 0
        self.total_elapsed_ticks = 0
        self.received_frame_count = 0
        self.valid_baseline_frame_count = 0
        self.is_capturing_baseline = False
        self.current_remaining_sec = 0.0
        # UI update watchdog
        self._baseline_ui_updated = False

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

        # 1. 왼쪽: 카메라 프리뷰 (고정 크기)
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
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        self.preview_label.setMinimumSize(1, 1)
        self.preview_label.setStyleSheet("border: none; background-color: transparent;")
        preview_vbox.addWidget(self.preview_label)
        self.preview_frame.setLayout(preview_vbox)
        content_layout.addWidget(self.preview_frame, 3)

        # 2. 오른쪽: 그래프 및 실시간 상태 정보
        self.info_panel = QVBoxLayout()
        self.info_panel.setSpacing(15)

        # 2-1. 초기 자세 설정 가이드
        self.guide_card = self._create_posture_guide_card()
        self.info_panel.addWidget(self.guide_card, 2)

        # 2-2. 상태 안내 및 진행바
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
        self.main_status_label.setFont(app_font(self.theme_manager.scale_pixel(21), QFont.Weight.Bold))
        self.main_status_label.setStyleSheet(f"color: {Colors.PRIMARY.value}; border: none; background-color: transparent;")
        status_vbox.addWidget(self.main_status_label)

        self.sub_status_label = QLabel("시작하면 3초 거리 이동 → 1초 촬영을 5번 반복합니다.")
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

        self.current_pitch_label = QLabel("현재 고개 각도: -°")
        self.current_pitch_label.setFont(app_font(self.theme_manager.scale_pixel(13)))
        self.current_pitch_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.current_pitch_label.setStyleSheet("color: #666666; border: none; background-color: transparent;")
        status_vbox.addWidget(self.current_pitch_label)

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

        self.capture_btn = QPushButton("자세 설정 시작")
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

    def _create_posture_guide_card(self) -> QFrame:
        """초기 자세 설정 화면의 사용자 안내 카드"""
        guide_card = QFrame()
        guide_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        guide_layout = QVBoxLayout()
        guide_layout.setContentsMargins(
            self.theme_manager.scale_pixel(13),
            self.theme_manager.scale_pixel(10),
            self.theme_manager.scale_pixel(13),
            self.theme_manager.scale_pixel(10),
        )
        guide_layout.setSpacing(self.theme_manager.scale_pixel(5))

        def build_label(text: str, font_size: int = 11, bold: bool = False, centered: bool = False, color: str | None = None) -> QLabel:
            label = QLabel(text)
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            label.setFont(app_font(self.theme_manager.scale_pixel(font_size), QFont.Weight.Bold if bold else QFont.Weight.Normal))
            if centered:
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if color is not None:
                label.setStyleSheet(f"color: {color}; border: none; background-color: transparent;")
            else:
                label.setStyleSheet("border: none; background-color: transparent;")
            return label

        title_layout = QHBoxLayout()
        title = build_label("기준 자세 설정 가이드", font_size=18, bold=True, color=Colors.PRIMARY.value)
        title_layout.addWidget(title)
        
        self.what_is_correct_btn = QPushButton("? 바른 자세란?")
        self.what_is_correct_btn.setFixedSize(self.theme_manager.scale_pixel(110), self.theme_manager.scale_pixel(36))
        self.what_is_correct_btn.setFont(app_font(self.theme_manager.scale_pixel(11), QFont.Weight.Bold))
        self.what_is_correct_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.what_is_correct_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFF0F0;
                color: {Colors.RED_DANGER.value};
                border: 1px solid {Colors.RED_DANGER.value};
                border-radius: 14px;
            }}
            QPushButton:hover {{ background-color: #FFE5E5; }}
        """)
        self.what_is_correct_btn.clicked.connect(self._show_correct_posture_popup)
        title_layout.addWidget(self.what_is_correct_btn)
        title_layout.addStretch()
        guide_layout.addLayout(title_layout)

        pill_row = QHBoxLayout()
        pill_row.setSpacing(self.theme_manager.scale_pixel(5))
        for pill_text in ("평소 거리 범위", "3초 안에 이동", "1초 정지 촬영"):
            pill = build_label(pill_text, font_size=11, bold=True, centered=True)
            pill.setStyleSheet(
                f"background-color: {Colors.PURPLE_PRIMARY.value}; color: {Colors.WHITE.value}; border-radius: 11px; padding: 4px 8px;"
            )
            pill.setMinimumHeight(self.theme_manager.scale_pixel(22))
            pill_row.addWidget(pill)
        pill_row.addStretch()
        guide_layout.addLayout(pill_row)

        step1_title = build_label("① 거리 이동", font_size=12, bold=True)
        step1_desc = build_label("바른 자세를 유지한 채, 평소 사용하는 거리 범위 안에서 3초 안에 카메라와의 거리를 조정합니다.", font_size=11)
        guide_layout.addWidget(step1_title)
        guide_layout.addWidget(step1_desc)

        step2_title = build_label("② 자세 촬영", font_size=12, bold=True)
        step2_desc = build_label("1초 자세 촬영 중에는 말하거나 움직이지 말고 가만히 있어야 합니다.", font_size=11)
        guide_layout.addWidget(step2_title)
        guide_layout.addWidget(step2_desc)

        step3_title = build_label("③ 반복", font_size=12, bold=True)
        step3_desc = build_label("총 5단계 동안 카메라와의 거리 이동과 촬영을 반복합니다.", font_size=11)
        guide_layout.addWidget(step3_title)
        guide_layout.addWidget(step3_desc)

        caution = build_label(
            "주의 : 몸 전체의 거리만 조정해 주세요.\n이 자세가 앞으로의 ‘바른 자세 기준’이 됩니다.",
            font_size=11,
            bold=True,
            centered=True,
            color=Colors.TEXT_BLACK.value,
        )
        guide_layout.addWidget(caution)

        guide_card.setLayout(guide_layout)
        return guide_card

    def _show_correct_posture_popup(self):
        """바른 자세 가이드 팝업 표시"""
        dialog = QDialog(self)
        dialog.setWindowTitle("바른 자세 가이드")
        dialog.setFixedSize(self.theme_manager.scale_pixel(650), self.theme_manager.scale_pixel(400))
        dialog_layout = QVBoxLayout(dialog)
        
        from src.ui.widgets.settings_widgets import CorrectPostureGuideWidget
        guide = CorrectPostureGuideWidget(self.theme_manager)
        dialog_layout.addWidget(guide)
        
        close_btn = QPushButton("닫기")
        close_btn.setFixedHeight(self.theme_manager.scale_pixel(40))
        close_btn.clicked.connect(dialog.accept)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PURPLE_PRIMARY.value};
                color: {Colors.WHITE.value};
                border-radius: 8px;
            }}
        """)
        dialog_layout.addWidget(close_btn)
        
        dialog.exec()

    def start_camera_preview(self):
        """화면 진입 시 카메라 프리뷰만 미리 시작 (baseline 모드)"""
        if self.camera_worker is None:
            return

        if hasattr(self.camera_worker, "set_baseline_mode"):
            self.camera_worker.set_baseline_mode(True)

        if not self.camera_worker.isRunning():
            self.camera_worker.start()
        elif self.camera_worker.is_paused:
            self.camera_worker.resume()

        logger.info("카메라 프리뷰 미리 시작 (baseline 모드)")

    def pause_camera_preview(self):
        """화면 이탈 시 카메라 일시정지 (스레드 유지)"""
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.pause()
            logger.info("카메라 프리뷰 일시정지")

    def start_capture(self):
        """촬영 시작 (카메라는 이미 실행 중)"""
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
        self.sub_status_label.setText("시작하면 3초 거리 이동 → 1초 촬영을 5번 반복합니다.")

        if hasattr(self.camera_worker, "set_baseline_mode"):
            self.camera_worker.set_baseline_mode(True)

        self.baseline_manager.start_baseline_collection()

        # 카메라가 아직 안 켜져 있으면 시작
        if self.camera_worker.is_paused:
            self.camera_worker.resume()
        if not self.camera_worker.isRunning():
            self.camera_worker.start()

        self.capture_timer.start(100)
        logger.info("자세 설정 캡처 시작")

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

            self.main_status_label.setText("거리 이동")
            self.main_status_label.setStyleSheet(f"color: {Colors.PRIMARY.value}; border: none; background-color: transparent;")
            self.sub_status_label.setText(
                f"바른 자세를 유지한 채 3초 안에 거리만 조정해 주세요. ({remaining:.1f}초)"
            )
            self.step_progress_bar.setValue(min(progress, 100))
            self.step_progress_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {Colors.PRIMARY.value}; }}"
            )

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

            self.main_status_label.setText("정지 촬영")
            self.main_status_label.setStyleSheet(f"color: {Colors.RED_DANGER.value}; border: none; background-color: transparent;")
            self.sub_status_label.setText(
                f"1초 동안 움직이지 말고 가만히 있어주세요. ({remaining:.1f}초)"
            )
            self.step_progress_bar.setValue(min(progress, 100))
            self.step_progress_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {Colors.RED_DANGER.value}; }}"
            )

            if self.step_ticks >= int(self.collect_seconds * 10):
                self.total_progress_bar.setValue(self.current_step)
                self.step_label.setText(
                    f"전체 진행: {self.current_step} / {self.total_steps}"
                )

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

            indicators = frame_data.get("indicators")
            if indicators is not None:
                set_recognition_message(self.recognition_label, False)
                # 실시간 고개 각도 표시
                self.current_pitch_label.setText(f"현재 고개 각도: {indicators.face_pitch_deg:+.1f}°")
            else:
                set_recognition_message(self.recognition_label, True)
                self.current_pitch_label.setText("현재 고개 각도: -°")
                return

            if (
                not self.is_capturing_baseline
                or self.baseline_manager is None
                or not self.baseline_manager.is_collecting
            ):
                return

            if self.step_state == "WAIT":
                return

            self.received_frame_count += 1
            self.baseline_manager.add_frame_to_collection(indicators)
            self.valid_baseline_frame_count += 1
        except Exception as e:
            logger.error(f"프리뷰 업데이트 실패: {e}")

    def _finish_capture(self):
        """캡처 완료 처리"""
        if not self.is_capturing_baseline:
            return
        self.is_capturing_baseline = False
        self.capture_timer.stop()
        
        actual_fps = max(1, int(self.valid_baseline_frame_count / (self.total_steps * self.collect_seconds)))
        
        success = False
        if self.baseline_manager: 
            success = self.baseline_manager.finish_baseline_collection(fps=actual_fps)
            
        if self.camera_worker:
            self.camera_worker.set_baseline_mode(False)
            
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("자세 설정 시작")
        
        if success:
            self.total_progress_bar.setValue(self.total_steps)
            self.main_status_label.setText("완료")
            self.main_status_label.setStyleSheet(f"color: {Colors.SECONDARY.value}; border: none; background-color: transparent;")
            self.sub_status_label.setText("기준 자세 설정이 완료되었습니다.")
            
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
        """진행 중인 초기 자세 설정을 취소하고 초기 상태로 되돌린다."""
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

        if self.baseline_manager and getattr(
            self.baseline_manager, "is_collecting", False
        ):
            self.baseline_manager.reset()

        if self.camera_worker and hasattr(self.camera_worker, "set_baseline_mode"):
            self.camera_worker.set_baseline_mode(False)

        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("자세 설정 시작")
        self.preview_label.clear()
        self.preview_label.setText("카메라 프리뷰")
        self.total_progress_bar.setValue(0)
        self.step_progress_bar.setValue(0)
        self.step_label.setText(f"전체 진행: 0 / {self.total_steps}")
        self.main_status_label.setText("준비")
        self.main_status_label.setStyleSheet(f"color: {Colors.PRIMARY.value}; border: none; background-color: transparent;")
        self.sub_status_label.setText("시작하면 3초 거리 이동 → 1초 촬영을 5번 반복합니다.")
        set_recognition_message(self.recognition_label, False)

    def _fail_capture(self, message: str):
        self.is_capturing_baseline = False
        self.capture_timer.stop()
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.pause()
        if self.baseline_manager:
            self.baseline_manager.reset()
        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("다시 시작")
        self.main_status_label.setText("오류 발생")
        self.sub_status_label.setText(message)

    def _on_camera_error(self, error_msg: str):
        logger.error(f"카메라 오류 신호: {error_msg}")
        self._fail_capture(f"카메라 오류: {error_msg}")
