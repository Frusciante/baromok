"""UI 화면 모듈"""

import logging
from pathlib import Path

import cv2
import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from datetime import datetime

from src.ui.styles.theme import Colors, ThemeManager

logger = logging.getLogger(__name__)

RECOGNITION_DIFFICULT_MESSAGE = "인식이 어렵습니다"


def _set_recognition_message(label: QLabel, visible: bool):
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


class BaselineScreen(QWidget):
    """초기 바른자세 촬영 화면"""

    baseline_captured_signal = pyqtSignal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        camera_worker=None,
        baseline_manager=None,
    ):
        super().__init__()
        self.theme_manager = theme_manager
        self.camera_worker = camera_worker
        self.baseline_manager = baseline_manager

        # 기존 5초 고정 종료 방식 대신, 실제 유효 indicators 프레임 수를 기준으로 baseline을 종료한다.
        self.target_valid_baseline_frames = 90
        self.minimum_valid_baseline_frames = 60
        self.maximum_capture_seconds = 15
        self.warmup_frames = 5

        self.capture_elapsed_ticks = 0
        self.received_frame_count = 0
        self.valid_baseline_frame_count = 0
        self.is_capturing_baseline = False

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
        title.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(24), QFont.Weight.Bold)
        )
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

        self.recognition_label = QLabel("")
        self.recognition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recognition_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(12), QFont.Weight.Bold)
        )
        self.recognition_label.setStyleSheet(f"color: {Colors.RED_DANGER.value};")
        _set_recognition_message(self.recognition_label, False)
        layout.addWidget(self.recognition_label)

        guide = QLabel(
            "바른 자세로 촬영하세요:\n"
            "• 카메라와 거리는 50-60cm로 유지해주세요\n"
            "• 화면과 눈 사이의 거리를 40-50cm로 유지 해 주세요.\n"
            "• 등을 의자 등받이에 깊숙이 밀착한 후 허리를 펴 주세요.\n"
            "• 무릎은 90도를 유지하고, 발바닥은 바닥에 닿게 해주세요.\n"
            "• 팔꿈치 각도는 90도 내외를 유지해 주세요.\n"
            "• 턱을 가볍게 아래로 당겨주세요."
        )

        guide.setFont(QFont("Noto Sans KR", self.theme_manager.scale_pixel(12)))
        layout.addWidget(guide)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.capture_status_label = QLabel(
            f"유효 프레임 0 / {self.target_valid_baseline_frames}"
        )
        self.capture_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.capture_status_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(11))
        )
        self.capture_status_label.setStyleSheet(f"color: {Colors.GRAY_DARK.value};")
        layout.addWidget(self.capture_status_label)

        self.capture_btn = QPushButton("촬영 시작")
        self.capture_btn.setFixedHeight(self.theme_manager.scale_pixel(50))
        self.capture_btn.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(16), QFont.Weight.Bold)
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

        self.capture_elapsed_ticks = 0
        self.received_frame_count = 0
        self.valid_baseline_frame_count = 0
        self.is_capturing_baseline = True

        self.progress_bar.setValue(0)
        self.capture_status_label.setText(
            f"유효 프레임 0 / {self.target_valid_baseline_frames}"
        )

        self.capture_btn.setEnabled(False)
        self.capture_btn.setText("촬영 중...")

        if self.camera_worker.is_paused:
            self.camera_worker.resume()

        if hasattr(self.camera_worker, "set_baseline_mode"):
            self.camera_worker.set_baseline_mode(True)

        self.baseline_manager.start_baseline_collection()

        if not self.camera_worker.isRunning():
            self.camera_worker.start()

        self.capture_timer.start(100)
        logger.info("초기화 촬영 시작")

    def _update_progress(self):
        """최대 촬영 시간 초과 확인"""
        if not self.is_capturing_baseline:
            return

        self.capture_elapsed_ticks += 1
        elapsed_seconds = self.capture_elapsed_ticks / 10

        self.capture_status_label.setText(
            f"유효 프레임 {self.valid_baseline_frame_count} / "
            f"{self.target_valid_baseline_frames} "
            f"({elapsed_seconds:.1f}s / {self.maximum_capture_seconds}s)"
        )

        if elapsed_seconds >= self.maximum_capture_seconds:
            if self.valid_baseline_frame_count >= self.minimum_valid_baseline_frames:
                self._finish_capture()
            else:
                self._fail_capture(
                    f"Baseline 프레임이 부족합니다.\n"
                    f"수집된 유효 프레임: {self.valid_baseline_frame_count}개\n"
                    f"최소 필요 프레임: {self.minimum_valid_baseline_frames}개\n"
                    "카메라 앞에서 얼굴과 양쪽 어깨가 잘 보이도록 한 뒤 다시 촬영해 주세요."
                )

    def _on_frame_processed(self, frame_data: dict):
        """프레임 처리 완료 시 호출"""
        try:
            annotated_frame = frame_data.get("frame")
            if annotated_frame is not None:
                pixmap = cv2_to_qpixmap(annotated_frame)
                scaled_pixmap = pixmap.scaledToWidth(
                    self.preview_frame.width() - 4,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled_pixmap)

            if (
                not self.is_capturing_baseline
                or self.baseline_manager is None
                or not self.baseline_manager.is_collecting
            ):
                return

            self.received_frame_count += 1
            indicators = frame_data.get("indicators")

            # 초반 카메라/MediaPipe 안정화 프레임은 baseline에서 제외한다.
            if self.received_frame_count <= self.warmup_frames:
                _set_recognition_message(
                    self.recognition_label,
                    indicators is None,
                )
                self.capture_status_label.setText(
                    f"카메라 안정화 중... "
                    f"{self.received_frame_count} / {self.warmup_frames}"
                )
                return

            if indicators is None:
                logger.debug("Baseline 수집 중 indicators가 없는 프레임 제외")
                _set_recognition_message(self.recognition_label, True)
                return

            _set_recognition_message(self.recognition_label, False)

            self.baseline_manager.add_frame_to_collection(indicators)
            self.valid_baseline_frame_count += 1

            progress = int(
                self.valid_baseline_frame_count
                / self.target_valid_baseline_frames
                * 100
            )
            self.progress_bar.setValue(min(progress, 100))

            self.capture_status_label.setText(
                f"유효 프레임 {self.valid_baseline_frame_count} / "
                f"{self.target_valid_baseline_frames}"
            )

            if self.valid_baseline_frame_count >= self.target_valid_baseline_frames:
                self._finish_capture()

        except Exception as e:
            logger.error(f"프리뷰 업데이트 실패: {e}")

    def _finish_capture(self):
        """Baseline 촬영 완료"""
        if not self.is_capturing_baseline:
            return

        self.is_capturing_baseline = False
        self.capture_timer.stop()

        # 중요:
        # baseline mode를 먼저 끄면, QThread가 완전히 종료되기 전 남은 프레임이
        # 일반 감지 모드로 처리되면서 아직 저장되지 않은 baseline을 참조할 수 있다.
        # 따라서 카메라를 먼저 멈추고, baseline 저장을 끝낸 뒤 baseline mode를 해제한다.
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.stop_capture()

        actual_elapsed_seconds = max(1.0, self.capture_elapsed_ticks / 10)
        actual_fps = max(
            1,
            int(self.valid_baseline_frame_count / actual_elapsed_seconds),
        )

        success = False
        if self.baseline_manager:
            success = self.baseline_manager.finish_baseline_collection(fps=actual_fps)

        if self.camera_worker and hasattr(self.camera_worker, "set_baseline_mode"):
            self.camera_worker.set_baseline_mode(False)

        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("촬영 시작")

        if success:
            self.progress_bar.setValue(100)
            self.capture_status_label.setText(
                f"Baseline 저장 완료 "
                f"({self.valid_baseline_frame_count}개 유효 프레임)"
            )
            logger.info("초기화 촬영 완료")
            self.baseline_captured_signal.emit()
        else:
            self.preview_label.setText(
                "Baseline 저장에 실패했습니다.\n"
                "얼굴과 양쪽 어깨가 화면에 잘 보이도록 한 뒤 다시 촬영해 주세요."
            )
            self.capture_status_label.setText(
                f"Baseline 저장 실패 "
                f"({self.valid_baseline_frame_count}개 유효 프레임)"
            )
            logger.warning("초기화 촬영 실패")

    def _fail_capture(self, message: str):
        """Baseline 촬영 실패 처리"""
        self.is_capturing_baseline = False
        self.capture_timer.stop()

        # 실패 시에도 baseline mode 상태에서 먼저 카메라를 멈춘다.
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.stop_capture()

        if self.baseline_manager:
            self.baseline_manager.reset()

        if self.camera_worker and hasattr(self.camera_worker, "set_baseline_mode"):
            self.camera_worker.set_baseline_mode(False)

        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("다시 촬영")
        self.progress_bar.setValue(0)
        self.preview_label.setText(message)
        self.capture_status_label.setText("Baseline 촬영 실패")

        logger.warning(message.replace("\n", " "))

    def _on_camera_error(self, error_msg: str):
        """카메라 오류"""
        logger.error(f"카메라 오류: {error_msg}")

        self.is_capturing_baseline = False
        self.capture_timer.stop()

        if self.baseline_manager:
            self.baseline_manager.reset()

        if self.camera_worker and hasattr(self.camera_worker, "set_baseline_mode"):
            self.camera_worker.set_baseline_mode(False)

        self.capture_btn.setEnabled(True)
        self.capture_btn.setText("촬영 시작")
        self.preview_label.setText(f"오류: {error_msg}")
        self.capture_status_label.setText("카메라 오류")


class HubScreen(QWidget):
    """메인 허브 화면"""

    start_detection_signal = pyqtSignal()
    open_settings_signal = pyqtSignal()
    open_statistics_signal = pyqtSignal()
    open_baseline_signal = pyqtSignal()

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.theme_manager = theme_manager
        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # 상단 영역: 가로 레이아웃 (일러스트 + 버튼)
        top_layout = QHBoxLayout()
        top_layout.setSpacing(30)

        # 왼쪽: 일러스트 영역
        illust_frame = QFrame()
        illust_frame.setStyleSheet(f"background-color: transparent; border: none;")
        illust_frame.setMaximumWidth(self.theme_manager.scale_pixel(520))
        illust_layout = QVBoxLayout(illust_frame)
        illust_layout.setContentsMargins(0, 0, 0, 0)
        illust_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        illust_label = QLabel()
        illust_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 홈 일러스트 로드
        image_path_candidates = [
            Path("assets/ui/바로목로고.png"),
            Path("assets/ui/home_illustration.svg"),
        ]
        for image_path in image_path_candidates:
            if not image_path.exists():
                continue

            try:
                pixmap = QPixmap(str(image_path))
                if pixmap.isNull():
                    continue

                scaled_pixmap = pixmap.scaledToHeight(
                    self.theme_manager.scale_pixel(380),
                    Qt.TransformationMode.SmoothTransformation,
                )
                illust_label.setPixmap(scaled_pixmap)
                break
            except Exception:
                continue
        else:
            illust_label.setText("[일러스트]")

        illust_layout.addWidget(illust_label, alignment=Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(illust_frame, 0, Qt.AlignmentFlag.AlignCenter)

        # 오른쪽: 버튼 영역 (세로 배치)
        button_layout = QVBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(12)

        baseline_btn = QPushButton("초기 자세 촬영")
        baseline_btn.setFixedHeight(self.theme_manager.scale_pixel(48))
        baseline_btn.setFixedWidth(self.theme_manager.scale_pixel(360))
        baseline_btn.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(14), QFont.Weight.Bold)
        )
        baseline_btn.clicked.connect(self.open_baseline_signal.emit)
        button_layout.addWidget(baseline_btn)

        settings_btn = QPushButton("환경 설정")
        settings_btn.setFixedHeight(self.theme_manager.scale_pixel(48))
        settings_btn.setFixedWidth(self.theme_manager.scale_pixel(360))
        settings_btn.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(14), QFont.Weight.Bold)
        )
        settings_btn.clicked.connect(self.open_settings_signal.emit)
        button_layout.addWidget(settings_btn)

        stats_btn = QPushButton("나의 통계")
        stats_btn.setFixedHeight(self.theme_manager.scale_pixel(48))
        stats_btn.setFixedWidth(self.theme_manager.scale_pixel(360))
        stats_btn.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(14), QFont.Weight.Bold)
        )
        stats_btn.clicked.connect(self.open_statistics_signal.emit)
        button_layout.addWidget(stats_btn)

        top_layout.addLayout(button_layout, 1)
        main_layout.addLayout(top_layout, 1)

        main_layout.addStretch()

        start_btn = QPushButton("바로목 감지 시작")
        start_btn.setFixedHeight(self.theme_manager.scale_pixel(56))
        start_btn.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(20), QFont.Weight.Bold)
        )
        start_btn.clicked.connect(self.start_detection_signal.emit)
        main_layout.addWidget(start_btn)

        self.setLayout(main_layout)


class SettingsScreen(QWidget):
    """환경 설정 화면"""

    settings_saved_signal = pyqtSignal(dict)
    back_to_hub_signal = pyqtSignal()

    def __init__(self, theme_manager: ThemeManager, settings_config: dict = None):
        super().__init__()
        self.theme_manager = theme_manager
        self.settings_config = settings_config or {}
        self.category_widgets = []
        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        from src.ui.widgets.settings_widgets import (
            AutoStartSettingsWidget,
            NotificationSettingsWidget,
            PopupSettingsWidget,
            SoundSettingsWidget,
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("환경 설정")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(30), QFont.Weight.Bold)
        )
        title.setStyleSheet(
            f"color: {Colors.WHITE.value}; background-color: {Colors.PURPLE_PRIMARY.value}; "
            f"padding: {self.theme_manager.scale_pixel(10)}px; border-radius: 14px;"
        )
        layout.addWidget(title)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)
        scroll_content.setLayout(scroll_layout)

        categories = [
            "알림 설정",
            "소리 설정",
            "팝업 설정",
            "컴퓨터 부팅 시\n프로그램 자동 시작",
        ]
        category_widget_classes = [
            NotificationSettingsWidget,
            SoundSettingsWidget,
            PopupSettingsWidget,
            AutoStartSettingsWidget,
        ]

        for cat, widget_class in zip(categories, category_widget_classes):
            row_frame = QFrame()
            row_frame.setStyleSheet(
                f"background-color: {Colors.WHITE.value}; border: 1px solid #E3E0F2; border-radius: {self.theme_manager.scale_pixel(8)}px;"
            )
            # 기본 높이
            row_frame.setMinimumHeight(self.theme_manager.scale_pixel(220))
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(16, 16, 16, 16)
            row_layout.setSpacing(16)
            row_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            category_label = QLabel(cat)
            category_label.setFixedWidth(self.theme_manager.scale_pixel(210))
            category_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            category_label.setFont(
                QFont(
                    "Noto Sans KR",
                    self.theme_manager.scale_pixel(16),
                    QFont.Weight.Bold,
                )
            )
            category_label.setStyleSheet(
                f"background-color: {Colors.PURPLE_PRIMARY.value}; color: {Colors.WHITE.value}; "
                f"border-radius: {self.theme_manager.scale_pixel(10)}px; padding: {self.theme_manager.scale_pixel(10)}px;"
            )

            widget = widget_class(self.theme_manager, self.settings_config)
            # 팝업 설정은 내부 컨트롤이 많아 더 큰 높이를 사용
            if cat == "팝업 설정":
                # 팝업 내부 텍스트가 잘리는 문제 해결을 위해 충분히 큰 높이로 설정
                row_frame.setMinimumHeight(self.theme_manager.scale_pixel(360))
                widget.setMinimumHeight(self.theme_manager.scale_pixel(320))
            else:
                widget.setMinimumHeight(self.theme_manager.scale_pixel(188))
            widget.value_changed_signal.connect(self._on_widget_value_changed)
            self.category_widgets.append(widget)

            row_layout.addWidget(category_label)
            row_layout.addWidget(widget, 1)
            row_frame.setLayout(row_layout)
            scroll_layout.addWidget(row_frame)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1)

        confirm_btn = QPushButton("확인")
        confirm_btn.setFixedHeight(self.theme_manager.scale_pixel(56))
        confirm_btn.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(20), QFont.Weight.Bold)
        )
        confirm_btn.clicked.connect(self._save_settings)
        layout.addWidget(confirm_btn, 0, Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

    def _on_widget_value_changed(self, value_dict: dict):
        """위젯 값 변경 시 현재 설정 딕셔너리 갱신"""
        self.settings_config.update(value_dict)

    def _save_settings(self):
        """설정 저장"""
        all_settings = {}
        for widget in self.category_widgets:
            all_settings.update(widget.get_value())

        self.settings_saved_signal.emit(all_settings)
        self.back_to_hub_signal.emit()


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
        from src.ui.widgets.chart_widgets import StatisticsLineChart

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        title = QLabel("최근 10개 세션 바른자세 유지율")
        title.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(18), QFont.Weight.Bold)
        )
        layout.addWidget(title)

        self.chart_widget = StatisticsLineChart(self.theme_manager)
        layout.addWidget(self.chart_widget, 1)

        self.avg_label = QLabel("데이터 없음")
        self.avg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avg_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(14), QFont.Weight.Bold)
        )
        layout.addWidget(self.avg_label)

        self._load_and_plot_data()

        back_btn = QPushButton("돌아가기")
        back_btn.setFixedHeight(self.theme_manager.scale_pixel(40))
        back_btn.clicked.connect(self.back_to_hub_signal.emit)
        layout.addWidget(back_btn)

        self.setLayout(layout)

    def _load_and_plot_data(self):
        """세션 데이터 로드 및 차트 플로팅"""
        try:
            if self.session_manager:
                recent_sessions = self.session_manager.load_recent_sessions(10)
                if recent_sessions:
                    recent_sessions.reverse()
                    sessions_data = []
                    for session in recent_sessions:
                        session_label = self._format_session_label(session)
                        sessions_data.append(
                            {
                                "good_posture_percentage": session.statistics.get(
                                    "good_posture_percentage", 0
                                ),
                                "good_posture_seconds": session.statistics.get(
                                    "good_posture_seconds", 0
                                ),
                                "total_detection_seconds": session.statistics.get(
                                    "duration_seconds", session.duration_seconds
                                ),
                                "session_label": session_label,
                                "start_time": session.start_time,
                                "duration_seconds": session.duration_seconds,
                            }
                        )

                    self.chart_widget.plot_data(sessions_data)
                    self._update_average_label(sessions_data)
                    logger.info(f"차트 데이터 로드: {len(sessions_data)}개 세션")
                else:
                    self.chart_widget.plot_data([])
                    self._update_average_label([])
                    logger.info("로드할 세션 데이터 없음")
            else:
                logger.warning("SessionManager 없음")
                self.chart_widget.plot_data([])
                self._update_average_label([])
        except Exception as e:
            logger.error(f"차트 데이터 로드 실패: {e}")
            self.chart_widget.plot_data([])
            self._update_average_label([])

    def _update_average_label(self, sessions_data: list):
        """최근 세션 평균 라벨 갱신"""
        if not hasattr(self, "avg_label"):
            return

        avg_text = "데이터 없음"
        retention_values = []
        for session in sessions_data:
            try:
                retention_values.append(
                    float(session.get("good_posture_percentage", 0))
                )
            except (TypeError, ValueError):
                continue

        if retention_values:
            avg_pct = sum(retention_values) / len(retention_values)
            avg_text = f"평균 유지율: {avg_pct:.1f}%"

        self.avg_label.setText(avg_text)

    def showEvent(self, event):
        """화면 진입 시 최신 세션 데이터로 차트/라벨 갱신"""
        super().showEvent(event)
        self._load_and_plot_data()

    def _format_session_label(self, session) -> str:
        """세션 표시용 날짜 라벨 생성"""
        try:
            return datetime.fromisoformat(session.start_time).strftime("%m/%d")
        except Exception:
            return str(session.session_id)[-4:]


class DetectionScreen(QWidget):
    """감지 진행 화면"""

    detection_paused_signal = pyqtSignal()
    detection_stopped_signal = pyqtSignal()
    open_settings_signal = pyqtSignal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        camera_worker=None,
        session_manager=None,
    ):
        super().__init__()
        self.theme_manager = theme_manager
        self.camera_worker = camera_worker
        self.session_manager = session_manager
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
        self.status_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(14), QFont.Weight.Bold)
        )
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
        self.time_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(48), QFont.Weight.Bold)
        )
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

        self.recognition_label = QLabel("")
        self.recognition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recognition_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(12), QFont.Weight.Bold)
        )
        self.recognition_label.setStyleSheet(f"color: {Colors.RED_DANGER.value};")
        _set_recognition_message(self.recognition_label, False)
        layout.addWidget(self.recognition_label)

        self.posture_label = QLabel("감지 중")
        self.posture_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.posture_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(16), QFont.Weight.Bold)
        )
        layout.addWidget(self.posture_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

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
        """프레임 처리 완료 시 호출"""
        try:
            if frame_data.get("posture_type") == "baseline":
                return

            annotated_frame = frame_data.get("frame")
            if annotated_frame is not None:
                pixmap = cv2_to_qpixmap(annotated_frame)
                scaled_pixmap = pixmap.scaledToWidth(
                    self.preview_frame.width() - 4,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled_pixmap)

            indicators = frame_data.get("indicators")
            if indicators is None:
                _set_recognition_message(self.recognition_label, True)
                self.status_label.setText(RECOGNITION_DIFFICULT_MESSAGE)
                self.status_label.setObjectName("status_normal")
                self.status_label.style().polish(self.status_label)
                self.posture_label.setText(RECOGNITION_DIFFICULT_MESSAGE)
                return

            _set_recognition_message(self.recognition_label, False)

            state = frame_data.get("state", "NORMAL")
            posture_type = frame_data.get("posture_type", "normal")
            probability = frame_data.get("probability", 0.0)
            self._update_posture_status(state, posture_type, probability)

            if (
                self.session_manager
                and getattr(self.session_manager, "current_session", None) is not None
            ):
                self.session_manager.add_frame_data(frame_data)

        except Exception as e:
            logger.error(f"프레임 처리 오류: {e}")

    def _update_posture_status(self, state: str, posture_type: str, probability: float):
        """자세 상태 업데이트"""
        posture_map = {
            "normal": "바른 자세",
            "forward_head": "거북목",
            "recline": "기댄 자세",
            "crossed_leg_estimated": "다리 꼬기",
            "chin_rest_estimated": "턱 받침",
            "baseline": "기준 자세 촬영",
        }

        posture_text = posture_map.get(posture_type, "알 수 없음")
        self.posture_label.setText(f"{posture_text} ({probability:.1%})")

        state_text = {
            "normal": "바른 자세",
            "warning": "경고",
            "bad_posture": "나쁜 자세",
            "NORMAL": "바른 자세",
            "WARNING": "경고",
            "BAD_POSTURE": "나쁜 자세",
        }
        self.status_label.setText(state_text.get(state, "상태 알 수 없음"))

        state_colors = {
            "normal": "status_normal",
            "warning": "status_warning",
            "bad_posture": "status_bad",
            "NORMAL": "status_normal",
            "WARNING": "status_warning",
            "BAD_POSTURE": "status_bad",
        }
        self.status_label.setObjectName(state_colors.get(state, "status_normal"))
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

    def _stop_detection(self):
        """감지 중지"""
        if self.camera_worker:
            self.camera_worker.stop_capture()
            self.time_timer.stop()
            self.pause_btn.setText("일시정지")
            self.is_detection_paused = False
            self.detection_stopped_signal.emit()

    def on_detection_started(self):
        """감지 시작 직후 타이머/버튼 상태 동기화"""
        self.is_detection_paused = False
        self.pause_btn.setText("일시정지")
        self._update_elapsed_time()
        self.time_timer.start(1000)

    def showEvent(self, event):
        """화면 표시 시"""
        super().showEvent(event)
        if (
            self.camera_worker
            and self.camera_worker.is_running
            and not self.is_detection_paused
        ):
            self.time_timer.start(1000)

    def hideEvent(self, event):
        """화면 숨김 시"""
        super().hideEvent(event)
        self.time_timer.stop()

    def _on_camera_error(self, error_msg: str):
        """카메라 오류"""
        logger.error(f"카메라 오류: {error_msg}")
        self.preview_label.setText(f"오류: {error_msg}")
        self.status_label.setText("카메라 오류")
        self.time_timer.stop()
        self.pause_btn.setText("일시정지")
        self.is_detection_paused = False


class AlertPopup(QWidget):
    """알림 팝업 (배너 & 토스트)"""

    close_signal = pyqtSignal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        alert_type: str = "warning",
        message_text: str = "알림 메시지",
    ):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.theme_manager = theme_manager
        self.alert_type = alert_type
        self.message_text = message_text
        self.setup_ui()

    def setup_ui(self):
        """UI 구성"""
        layout = QHBoxLayout()
        layout.setContentsMargins(
            self.theme_manager.scale_pixel(12),
            self.theme_manager.scale_pixel(8),
            self.theme_manager.scale_pixel(12),
            self.theme_manager.scale_pixel(8),
        )
        layout.setSpacing(10)

        color_map = {
            "warning": Colors.YELLOW_WARNING.value,
            "danger": Colors.RED_DANGER.value,
            "info": Colors.PURPLE_PRIMARY.value,
        }
        bg_color = color_map.get(self.alert_type, Colors.YELLOW_WARNING.value)

        self.setStyleSheet(f"""
            background-color: {bg_color};
            border-radius: 5px;
        """)

        self.message_label = QLabel(self.message_text)
        self.message_label.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(12), QFont.Weight.Bold)
        )
        self.message_label.setStyleSheet(f"color: {Colors.WHITE.value};")
        layout.addWidget(self.message_label, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(
            self.theme_manager.scale_pixel(24),
            self.theme_manager.scale_pixel(24),
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

    def set_alert_content(self, alert_type: str, message_text: str):
        """팝업 종류와 메시지 갱신"""
        self.alert_type = alert_type
        self.message_text = message_text

        color_map = {
            "warning": Colors.YELLOW_WARNING.value,
            "danger": Colors.RED_DANGER.value,
            "info": Colors.PURPLE_PRIMARY.value,
        }
        bg_color = color_map.get(self.alert_type, Colors.YELLOW_WARNING.value)
        self.setStyleSheet(f"""
            background-color: {bg_color};
            border-radius: 5px;
        """)
        self.message_label.setText(self.message_text)
