from pathlib import Path
from datetime import datetime
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
        illust_frame.setStyleSheet("background-color: transparent; border: none;")
        illust_frame.setMaximumWidth(self.theme_manager.scale_pixel(520))
        
        # 전체를 감싸는 메인 레이아웃
        illust_layout = QVBoxLayout(illust_frame)
        illust_layout.setContentsMargins(0, 0, 0, 0)
        illust_layout.setSpacing(self.theme_manager.scale_pixel(15)) # 로고 세트와 서브 캡션 사이의 간격
        illust_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ----------------------------------------------------------
        # 1. 로고 이미지와 타이틀 글자를 하나의 컨테이너로 묶기
        # ----------------------------------------------------------
        logo_container = QWidget()
        logo_container.setStyleSheet("background-color: transparent;")
        logo_container_layout = QVBoxLayout(logo_container)
        logo_container_layout.setContentsMargins(0, 0, 0, 0)
        logo_container_layout.setSpacing(0) # 💡 내부 스페이싱을 0으로 만들어 바짝 붙임
        logo_container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 로고 이미지 라벨
        illust_label = QLabel()
        illust_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        illust_label.setStyleSheet("background-color: transparent; margin: 0px; padding: 0px;")

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
                # 💡 이미지 크기를 340정도로 조절
                scaled_pixmap = pixmap.scaledToHeight(
                    self.theme_manager.scale_pixel(340),
                    Qt.TransformationMode.SmoothTransformation,
                )
                illust_label.setPixmap(scaled_pixmap)
                break
            except Exception:
                continue
        else:
            illust_label.setText("[일러스트]")

        # 타이틀 캡션 라벨 (로고 컨테이너 내부용)
        title_caption = QLabel()
        title_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_caption.setStyleSheet(f"""
            color: #000000;
            font-size: {self.theme_manager.scale_pixel(36)}px;
            font-weight: bold;
            margin: 0px;
            padding: 0px;
        """)

        # 로고 세트 조립
        logo_container_layout.addWidget(illust_label)
        logo_container_layout.addWidget(title_caption)

        # ----------------------------------------------------------
        # 2. 서브 캡션 라벨 (따로 분리하여 하단 배치)
        # ----------------------------------------------------------
        sub_caption = QLabel()
        sub_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_caption.setStyleSheet(f"""
            color: #1A1A1A;
            font-size: {self.theme_manager.scale_pixel(22)}px;
            margin: 0px;
            padding: 0px;
        """)

        # 데이터 유무 분기 처리
        has_records = False  
        user_name = "사용자"

        if not has_records:
            title_caption.setText("바로목에 오신 걸 환영합니다")
            sub_caption.setText("아래 버튼으로 첫 측정을 시작해보세요")
        else:
            title_caption.setText(f"안녕하세요, {user_name}님")
            sub_caption.setText("오늘도 바른 자세로 시작해볼까요?")

        # ----------------------------------------------------------
        # 3. 메인 일러스트 레이아웃에 최종 조립
        # ----------------------------------------------------------
        illust_layout.addWidget(logo_container, 0, Qt.AlignmentFlag.AlignCenter)
        illust_layout.addWidget(sub_caption, 0, Qt.AlignmentFlag.AlignCenter)

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
        """우측 점수 패널 생성: 최근 통계자료(sessions) 유무로만 분기 렌더링"""
        panel = QFrame()
        panel.setObjectName("score_panel")
        panel.setStyleSheet(f"background-color: {Colors.WHITE.value}; border-radius: {self.theme_manager.scale_pixel(10)}px; border: none;")
        panel_layout = QVBoxLayout()
        panel_layout.setContentsMargins(self.theme_manager.scale_pixel(16), self.theme_manager.scale_pixel(16), self.theme_manager.scale_pixel(16), self.theme_manager.scale_pixel(16))
        panel_layout.setSpacing(self.theme_manager.scale_pixel(12))

        # 데이터 로드 데이터베이스 예외 처리 유지
        sessions = []
        try:
            if self.session_manager:
                sessions = self.session_manager.load_recent_sessions(10)
        except Exception:
            logger.exception("세션 데이터 로드 실패")

        # 통계 레코드의 유무로 분기
        valid_sessions = [
            s for s in sessions
            if isinstance(getattr(s, "statistics", {}), dict)
            and s.statistics.get("good_posture_percentage") is not None
        ]

        if not valid_sessions:
            content = self._create_empty_state()
        else:
            content = self._create_score_state(valid_sessions)

        panel_layout.addWidget(content)
        panel.setLayout(panel_layout)
        return panel

    def _create_empty_state(self) -> QWidget:
        """상태 A: 측정 기록 및 통계 자료 없음 (통합형 안내 가이드)"""
        w = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.theme_manager.scale_pixel(8))
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 이미지 에셋 로드 및 예외 백업 로직 결합
        icon_label = QLabel()
        icon_path = Path("assets/ui/icon_statsvalue.png")
        
        if icon_path.exists():
            try:
                icon_pixmap = QPixmap(str(icon_path))
                if not icon_pixmap.isNull():
                    icon_label.setPixmap(
                        icon_pixmap.scaledToHeight(
                            self.theme_manager.scale_pixel(130),
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:
                    icon_label.setText("📈")
                    icon_label.setFont(app_font(self.theme_manager.scale_pixel(31)))
                    icon_label.setStyleSheet(f"color: {self._colors['empty_icon']};")
            except Exception:
                icon_label.setText("📈")
                icon_label.setFont(app_font(self.theme_manager.scale_pixel(31)))
                icon_label.setStyleSheet(f"color: {self._colors['empty_icon']};")
        else:
            icon_label.setText("📈")
            icon_label.setFont(app_font(self.theme_manager.scale_pixel(31)))
            icon_label.setStyleSheet(f"color: {self._colors['empty_icon']};")
            
        icon_label.setStyleSheet("border: none; background-color: transparent;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        title = QLabel("아직 측정 기록이 없어요")
        title.setFont(app_font(self.theme_manager.scale_pixel(17), QFont.Weight.Medium))
        title.setStyleSheet(f"color: {self._colors['title_text']}; border: none; background-color: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("첫 측정을 마치면\n여기에 점수가 표시됩니다")
        desc.setFont(app_font(self.theme_manager.scale_pixel(13)))
        desc.setStyleSheet(f"color: {self._colors['muted']}; border: none; background-color: transparent;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        w.setLayout(layout)
        return w

    def _create_score_state(self, sessions: list) -> QWidget:
        """상태 B: 측정 기록 있음 - 최근 통계 데이터를 요약하는 대시보드"""
        w = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.theme_manager.scale_pixel(12))

        main_title = QLabel("나의 통계")
        main_title.setFont(app_font(self.theme_manager.scale_pixel(16), QFont.Weight.Bold))
        main_title.setStyleSheet(f"color: {self._colors['title_text']}; border: none; background-color: transparent;")
        layout.addWidget(main_title)

        sub_title = QLabel("최근 세션의 자세 유지율을 한눈에 확인해 보세요")
        sub_title.setFont(app_font(self.theme_manager.scale_pixel(12)))
        sub_title.setStyleSheet("color: #888888; border: none; background-color: transparent;")
        sub_title.setWordWrap(True)
        layout.addWidget(sub_title)

        recent = sessions[:3]
        recent_values = [
            float(s.statistics.get("good_posture_percentage", 0))
            for s in recent
            if isinstance(getattr(s, "statistics", {}), dict)
        ]

        average_score = int(round(sum(recent_values) / len(recent_values))) if recent_values else 0
        latest_score = int(recent_values[0]) if recent_values else 0

        score_row = QWidget()
        score_row_layout = QHBoxLayout()
        score_row_layout.setContentsMargins(0, 0, 0, 0)
        score_row_layout.setSpacing(self.theme_manager.scale_pixel(10))
        score_row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        score_label = QLabel(f"{average_score}")
        score_label.setFont(app_font(self.theme_manager.scale_pixel(70), QFont.Weight.Bold))
        score_label.setStyleSheet(f"color: {self._colors['score']}; border: none; background-color: transparent;")
        score_row_layout.addWidget(score_label)

        slash_label = QLabel("/ 100")
        slash_label.setFont(app_font(self.theme_manager.scale_pixel(18), QFont.Weight.Medium))
        slash_label.setStyleSheet("color: #888888; border: none; background-color: transparent;")
        score_row_layout.addWidget(slash_label, alignment=Qt.AlignmentFlag.AlignBottom)

        score_row.setLayout(score_row_layout)
        layout.addWidget(score_row)

        score_note = QLabel(f"최근 {len(recent_values)}회 평균 · 최신 {latest_score}점")
        score_note.setFont(app_font(self.theme_manager.scale_pixel(12)))
        score_note.setStyleSheet("color: #888888; border: none; background-color: transparent;")
        layout.addWidget(score_note)

        bottom_container = QWidget()
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(self.theme_manager.scale_pixel(16))
        bottom_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        left_summary = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(self.theme_manager.scale_pixel(8))
        left_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        for session in reversed(recent):
            label = self._format_session_date(session.start_time)
            value = int(float(session.statistics.get("good_posture_percentage", 0)))

            item = QWidget()
            item_layout = QHBoxLayout()
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(self.theme_manager.scale_pixel(6))

            date_label = QLabel(label)
            date_label.setFont(app_font(self.theme_manager.scale_pixel(11)))
            date_label.setStyleSheet("color: #888888; border: none; background-color: transparent;")
            item_layout.addWidget(date_label)

            value_label = QLabel(f"{value}점")
            value_label.setFont(app_font(self.theme_manager.scale_pixel(13), QFont.Weight.Medium))
            value_label.setStyleSheet(f"color: {self._colors['title_text']}; border: none; background-color: transparent;")
            item_layout.addWidget(value_label)

            item.setLayout(item_layout)
            left_layout.addWidget(item)

        left_layout.addStretch()
        left_summary.setLayout(left_layout)
        bottom_layout.addWidget(left_summary, 1)

        right_chart_wrapper = QWidget()
        right_chart_layout = QVBoxLayout()
        right_chart_layout.setContentsMargins(0, 0, 0, 0)
        right_chart_layout.setSpacing(0)
        right_chart_layout.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        trend_chart = self._create_trend_chart(list(reversed(recent_values)))
        right_chart_layout.addWidget(trend_chart, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        right_chart_wrapper.setLayout(right_chart_layout)
        bottom_layout.addWidget(right_chart_wrapper, 0)

        bottom_container.setLayout(bottom_layout)
        layout.addWidget(bottom_container)

        w.setLayout(layout)
        return w

    def _create_trend_chart(self, values: list) -> QWidget:
        """세 개 날짜 순서대로 점 세 개를 찍는 간단한 추세 차트"""
        fig = Figure(figsize=(2.2, 1.1), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(values, color=self._colors['score'], linewidth=2, marker='o', markersize=5)
        ax.fill_between(range(len(values)), values, color=self._colors['score'], alpha=0.12)
        ax.set_xlim(-0.3, max(2, len(values) - 1) + 0.3)
        ax.set_ylim(0, 100)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.set_facecolor(Colors.WHITE.value)

        canvas = FigureCanvas(fig)
        canvas.setFixedSize(self.theme_manager.scale_pixel(180), self.theme_manager.scale_pixel(90))
        canvas.setStyleSheet('background-color: transparent; border: none;')
        return canvas

    def _format_session_date(self, start_time: str) -> str:
        try:
            return datetime.fromisoformat(start_time).strftime('%m/%d')
        except Exception:
            return '-'
