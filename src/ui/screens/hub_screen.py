from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QHBoxLayout, QSpacerItem, QSizePolicy
)
from src.ui.styles.theme import ThemeManager, Colors
from src.ui.styles.font_loader import app_font
from src.core.session_manager import SessionManager
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import logging

logger = logging.getLogger(__name__)

class HubScreen(QWidget):
    """메인 허브 화면"""

    start_detection_signal = pyqtSignal()
    open_settings_signal = pyqtSignal()
    open_statistics_signal = pyqtSignal()
    open_baseline_signal = pyqtSignal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        session_manager: SessionManager = None,
        baseline_manager=None,
    ):
        super().__init__()
        self.theme_manager = theme_manager
        self.session_manager = session_manager
        self.baseline_manager = baseline_manager
        self._colors = {
            "panel_border": "#e5e5e7",
            "empty_icon": "#c9c4ed",
            "title_text": "#2a2a2a",
            "muted": "#888888",
            "score": "#5B4DE0",
        }
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
                    self.theme_manager.scale_pixel(500),
                    Qt.TransformationMode.SmoothTransformation,
                )
                illust_label.setPixmap(scaled_pixmap)
                break
            except Exception:
                continue
        else:
            illust_label.setText("[일러스트]")

        illust_layout.addWidget(illust_label, alignment=Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(illust_frame, 1, Qt.AlignmentFlag.AlignCenter)
        # 오른쪽 슬롯: score panel
        right_container = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        score_panel = self._create_score_panel()
        # 텍스트 내용과 무관하게 패널을 세로로 늘려 일정한 크기 유지
        score_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        right_layout.addWidget(score_panel)
        right_container.setLayout(right_layout)

        top_layout.addWidget(right_container, 1)
        main_layout.addLayout(top_layout, 1)
        main_layout.addStretch()

        start_btn = QPushButton("바로목 감지 시작")
        start_btn.setFixedHeight(self.theme_manager.scale_pixel(56))
        start_btn.setFont(app_font(self.theme_manager.scale_pixel(23), QFont.Weight.Bold))
        start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PURPLE_PRIMARY.value};
                color: {Colors.WHITE.value};
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: #5343B6;
            }}
        """)
        start_btn.clicked.connect(self.start_detection_signal.emit)
        main_layout.addWidget(start_btn)

        self.setLayout(main_layout)

    # ----------------------------- Score Panel -----------------------------
    def _create_score_panel(self) -> QWidget:
        """우측 점수 패널 생성: 빈 상태 또는 점수 상태로 분기 렌더링"""
        panel = QFrame()
        panel.setObjectName("score_panel")
        panel.setStyleSheet(f"background-color: {Colors.WHITE.value}; border-radius: {self.theme_manager.scale_pixel(10)}px; border: 0.5px solid {self._colors['panel_border']};")
        panel_layout = QVBoxLayout()
        panel_layout.setContentsMargins(self.theme_manager.scale_pixel(16), self.theme_manager.scale_pixel(16), self.theme_manager.scale_pixel(16), self.theme_manager.scale_pixel(16))
        panel_layout.setSpacing(self.theme_manager.scale_pixel(12))

        # 데이터 로드
        sessions = []
        try:
            if self.session_manager:
                sessions = self.session_manager.load_recent_sessions(10)
        except Exception:
            logger.exception("세션 데이터 로드 실패")

        baseline_missing = True
        try:
            if self.baseline_manager:
                baseline_missing = not self.baseline_manager.is_baseline_valid()
            else:
                baseline_missing = True
        except Exception:
            baseline_missing = True

        if baseline_missing:
            content = self._create_baseline_missing_state()
        elif not sessions:
            content = self._create_empty_state()
        else:
            content = self._create_score_state(sessions)

        panel_layout.addWidget(content)
        panel.setLayout(panel_layout)
        return panel

    def _create_empty_state(self) -> QWidget:
        """상태 A: 측정 기록 없음"""
        w = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.theme_manager.scale_pixel(8))
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 아이콘 (간단한 텍스트 아이콘 사용)
        icon_label = QLabel("📈")
        icon_font = app_font(self.theme_manager.scale_pixel(31))
        icon_label.setFont(icon_font)
        icon_label.setStyleSheet(f"color: {self._colors['empty_icon']}; border: none; background-color: transparent;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        title = QLabel("아직 측정 기록이 없어요")
        title.setFont(app_font(self.theme_manager.scale_pixel(15), QFont.Weight.Medium))
        title.setStyleSheet(f"color: {self._colors['title_text']}; border: none; background-color: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("아직 측정 기록이 없어요\n첫 측정을 시작하면\n자세 변화 리포트를 볼 수 있어요")
        desc.setFont(app_font(self.theme_manager.scale_pixel(13)))
        desc.setStyleSheet(f"color: {self._colors['muted']}; border: none; background-color: transparent;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        w.setLayout(layout)
        return w

    def _create_baseline_missing_state(self) -> QWidget:
        """상태 A: Baseline 파일이 없어서 초기 설정 안내"""
        w = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.theme_manager.scale_pixel(8))
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel()
        icon_path = Path("assets/ui/icon_statsvalue.png")
        if icon_path.exists():
            icon_pixmap = QPixmap(str(icon_path))
            if not icon_pixmap.isNull():
                icon_label.setPixmap(
                    icon_pixmap.scaledToHeight(
                        self.theme_manager.scale_pixel(130),
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        icon_label.setStyleSheet("border: none; background-color: transparent;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        title = QLabel("기준자세 데이터가 필요해요")
        title.setFont(
            app_font(self.theme_manager.scale_pixel(17), QFont.Weight.Medium)
        )
        title.setStyleSheet(f"color: {self._colors['title_text']}; border: none; background-color: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "저장된 기준자세가 없거나 유효하지 않습니다.\n바로목 감지를 시작하려면\n기준자세설정 화면으로 이동해주세요."
        )
        desc.setFont(app_font(self.theme_manager.scale_pixel(13)))
        desc.setStyleSheet(f"color: {self._colors['muted']}; border: none; background-color: transparent;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        w.setLayout(layout)
        return w

    def _create_score_state(self, sessions: list) -> QWidget:
        """상태 B: 측정 기록 있음 - 최근 데이터로 요약 표시"""
        w = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.theme_manager.scale_pixel(8))

        # 자세 점수 라벨
        lbl = QLabel("자세 점수")
        lbl.setFont(app_font(self.theme_manager.scale_pixel(13)))
        lbl.setStyleSheet(f"color: {self._colors['muted']}; border: none; background-color: transparent;")
        layout.addWidget(lbl)

        # 점수 계산: statics_screen의 평균 로직과 동일
        try:
            retention_values = [float(s.statistics.get("good_posture_percentage", 0)) for s in sessions if hasattr(s, 'statistics')]
            score = (sum(retention_values) / len(retention_values)) if retention_values else 0.0
        except Exception:
            logger.exception("점수 계산 실패")
            score = 0.0

        score_row = QWidget()
        score_row_layout = QHBoxLayout()
        score_row_layout.setContentsMargins(0, 0, 0, 0)
        score_row_layout.setSpacing(self.theme_manager.scale_pixel(6))

        score_label = QLabel(f"{score:.1f}")
        score_label.setFont(app_font(self.theme_manager.scale_pixel(39), QFont.Weight.Medium))
        score_label.setStyleSheet(f"color: {self._colors['score']}; border: none; background-color: transparent;")
        score_row_layout.addWidget(score_label)

        slash_label = QLabel("/ 100")
        slash_label.setFont(app_font(self.theme_manager.scale_pixel(14)))
        slash_label.setStyleSheet(f"color: {self._colors['muted']}; border: none; background-color: transparent;")
        score_row_layout.addWidget(slash_label, alignment=Qt.AlignmentFlag.AlignBottom)
        score_row_layout.addStretch()
        score_row.setLayout(score_row_layout)
        layout.addWidget(score_row)

        # 구분선
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {self._colors['panel_border']}; margin-top: {self.theme_manager.scale_pixel(8)}px; margin-bottom: {self.theme_manager.scale_pixel(8)}px;")
        layout.addWidget(divider)

        # 최근 기록 라벨
        lbl2 = QLabel("최근 기록")
        lbl2.setFont(app_font(self.theme_manager.scale_pixel(13)))
        lbl2.setStyleSheet(f"color: {self._colors['muted']}; border: none; background-color: transparent;")
        layout.addWidget(lbl2)

        # 최근 3일 표시
        recent = sessions[:3]
        for idx, s in enumerate(recent):
            row = QWidget()
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(self.theme_manager.scale_pixel(8))

            # 날짜 텍스트 (어제, 그제, 3일 전)
            if idx == 0:
                day_text = "어제"
            elif idx == 1:
                day_text = "그제"
            else:
                day_text = f"{idx+1}일 전"

            day_lbl = QLabel(day_text)
            day_lbl.setFont(app_font(self.theme_manager.scale_pixel(14)))
            day_lbl.setStyleSheet(f"color: {self._colors['muted']}; border: none; background-color: transparent;")
            row_layout.addWidget(day_lbl)

            # 스파크라인
            spark_values = []
            try:
                # use statistics if available
                all_sessions = [float(x.statistics.get("good_posture_percentage", 0)) for x in sessions]
                spark_values = all_sessions
            except Exception:
                spark_values = [0]

            spark = self._create_sparkline(spark_values)
            row_layout.addWidget(spark)

            # 점수
            score_val = s.statistics.get("good_posture_percentage", 0) if hasattr(s, 'statistics') else 0
            val_lbl = QLabel(str(int(score_val)))
            val_lbl.setFont(app_font(self.theme_manager.scale_pixel(14), QFont.Weight.Medium))
            val_lbl.setStyleSheet(f"color: {self._colors['title_text']}; border: none; background-color: transparent;")
            row_layout.addWidget(val_lbl, alignment=Qt.AlignmentFlag.AlignRight)

            row.setLayout(row_layout)
            layout.addWidget(row)

        w.setLayout(layout)
        return w

    def _create_sparkline(self, values: list) -> QWidget:
        """간단한 작은 선 그래프를 반환한다."""
        # Create a tiny matplotlib figure and render as FigureCanvas
        fig = Figure(figsize=(2, 0.5), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(values, color=self._colors['score'])
        ax.fill_between(range(len(values)), values, color=self._colors['score'], alpha=0.1)
        ax.axis('off')
        canvas = FigureCanvas(fig)
        canvas.setFixedSize(self.theme_manager.scale_pixel(80), self.theme_manager.scale_pixel(24))
        return canvas