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
        sessions = []
        try:
            if self.session_manager:
                sessions = self.session_manager.load_recent_sessions(30)
        except Exception:
            logger.exception("세션 데이터 로드 실패")

        valid_sessions = [
            s for s in sessions
            if isinstance(getattr(s, "statistics", {}), dict)
            and s.statistics.get("good_posture_percentage") is not None
        ]

        user_name = "사용자"

        if not valid_sessions:
            title_caption.setText("바로목에 오신 걸 환영합니다")
            sub_caption.setText("첫 측정을 마치면\n여기에 점수가 표시됩니다")
        else:
            recent = valid_sessions[:3]
            recent_values = [
                float(s.statistics.get("good_posture_percentage", 0))
                for s in recent
                if isinstance(getattr(s, "statistics", {}), dict)
            ]
            average_score = int(round(sum(recent_values) / len(recent_values))) if recent_values else 0

            if average_score >= 90:
                title_caption.setText("최고의 자세 유지율")
                sub_caption.setText("바른 자세의 정석입니다. 좋은 습관을 잘 유지하고 계시네요.")
            elif average_score >= 75:
                title_caption.setText("안정적인 자세 수준")
                sub_caption.setText("전반적으로 양호한 상태입니다. 흐트러짐 없는 자세를 유지 중입니다.")
            elif average_score >= 50:
                title_caption.setText("주의가 필요한 단계")
                sub_caption.setText("거북목 경계 단계입니다. 의식적으로 고개를 뒤로 당겨주세요.")
            elif average_score >= 25:
                title_caption.setText("위험! 거북목 주의보")
                sub_caption.setText("자세 유지율이 많이 떨어졌습니다. 즉시 정자세로 교정이 필요합니다.")
            else:
                title_caption.setText("경고!!! 척추가 위험합니다!")
                sub_caption.setText("지속적인 불량 자세가 감지되었습니다. 스트레칭 후 재측정을 권장합니다.")

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

        start_btn = QPushButton("모니터링 시작")
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
        panel_layout.setContentsMargins(self.theme_manager.scale_pixel(18), self.theme_manager.scale_pixel(18), self.theme_manager.scale_pixel(18), self.theme_manager.scale_pixel(18))
        panel_layout.setSpacing(self.theme_manager.scale_pixel(14))

        # 데이터 로드 데이터베이스 예외 처리 유지
        sessions = []
        try:
            if self.session_manager:
                sessions = self.session_manager.load_recent_sessions(30)
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
        """상태 B: 측정 기록 있음 - 최근 통계 데이터를 요약하는 대시보드 (글자 크기 확장 버전)"""
        w = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        # 글자들이 커진 만큼 패널 내부 간격도 살짝 넓힙니다.
        layout.setSpacing(self.theme_manager.scale_pixel(16))

        # 1. 메인 타이틀 ("평균 점수")
        main_title = QLabel("평균 점수")
        main_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        main_title.setStyleSheet(f"""
            color: {self._colors['title_text']};
            font-size: {self.theme_manager.scale_pixel(22)}px !important; /* 💡 16px -> 22px 확장 */
            font-weight: bold !important;
            border: none;
            background-color: transparent;
        """)
        layout.addWidget(main_title)

        # 2. 서브 타이틀 설명 문구
        sub_title = QLabel("최근 세션의 자세 유지율을 한눈에 확인해 보세요")
        sub_title.setWordWrap(True)
        sub_title.setStyleSheet(f"""
            color: #888888;
            font-size: {self.theme_manager.scale_pixel(15)}px !important; /* 💡 12px -> 15px 확장 */
            border: none;
            background-color: transparent;
        """)
        layout.addWidget(sub_title)

        # 데이터 계산부
        recent = sessions[:3]
        recent_values = [
            float(s.statistics.get("good_posture_percentage", 0))
            for s in recent
            if isinstance(getattr(s, "statistics", {}), dict)
        ]
        average_score = int(round(sum(recent_values) / len(recent_values))) if recent_values else 0
        latest_score = int(recent_values[0]) if recent_values else 0

        # 3. 점수 영역 (거대한 숫자)
        score_row = QWidget()
        score_row_layout = QHBoxLayout()
        score_row_layout.setContentsMargins(0, 0, 0, 0)
        score_row_layout.setSpacing(self.theme_manager.scale_pixel(12))
        score_row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        # 메인 점수 숫자 (예: 85)
        score_label = QLabel(f"{average_score}")
        score_label.setStyleSheet(f"""
            color: {self._colors['score']};
            font-size: {self.theme_manager.scale_pixel(110)}px !important; /* 💡 90px -> 110px 대폭 확장 */
            font-weight: bold !important;
            border: none;
            background-color: transparent;
        """)
        # 글자가 커진 만큼 라벨의 최소 크기도 안전하게 확보합니다.
        score_label.setMinimumHeight(self.theme_manager.scale_pixel(100))
        score_label.setMinimumWidth(self.theme_manager.scale_pixel(130))
        score_row_layout.addWidget(score_label)

        # 뒤에 붙는 "/ 100"
        slash_label = QLabel("/ 100")
        slash_label.setStyleSheet(f"""
            color: #888888;
            font-size: {self.theme_manager.scale_pixel(28)}px !important; /* 💡 22px -> 28px 확장 */
            font-weight: medium !important;
            border: none;
            background-color: transparent;
        """)
        score_row_layout.addWidget(slash_label, alignment=Qt.AlignmentFlag.AlignBottom)

        score_row.setLayout(score_row_layout)
        layout.addWidget(score_row)

        # 4. 점수 하단 요약 노트 ("최근 3회 평균")
        score_note = QLabel(f"\n최근 {len(recent_values)}회 평균")
        score_note.setStyleSheet(f"""
            color: #000000;
            font-size: {self.theme_manager.scale_pixel(22)}px !important; /* 💡 12px -> 15px 확장 */
            font-weight: bold !important;
            border: none;
            background-color: transparent;
        """)
        layout.addWidget(score_note)

        # 5. 하단 상세 리스트 + 그래프 레이아웃
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(self.theme_manager.scale_pixel(20))
        bottom_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        # 왼쪽: 최근 3회 기록 텍스트 리스트
        left_summary = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(self.theme_manager.scale_pixel(10)) # 글자가 커져서 간격도 넓힘
        left_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        for session in reversed(recent):
            label = self._format_session_date(session.start_time)
            value = int(float(session.statistics.get("good_posture_percentage", 0)))

            item = QWidget()
            item_layout = QHBoxLayout()
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(self.theme_manager.scale_pixel(10))

            # 날짜 (예: 05/20)
            date_label = QLabel(label)
            date_label.setStyleSheet(f"""
                color: #888888;
                font-size: {self.theme_manager.scale_pixel(18)}px !important; /* 
                border: none;
                background-color: transparent;
            """)
            item_layout.addWidget(date_label)

            # 해당 날짜 점수 (예: 80점)
            value_label = QLabel(f"{value}점")
            value_label.setStyleSheet(f"""
                color: {self._colors['title_text']};
                font-size: {self.theme_manager.scale_pixel(20)}px !important; /* 
                border: none;
                background-color: transparent;
            """)
            item_layout.addWidget(value_label)

            item.setLayout(item_layout)
            left_layout.addWidget(item)

        left_layout.addStretch()
        left_summary.setLayout(left_layout)
        left_summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bottom_layout.addWidget(left_summary, 1)

        # 오른쪽: 추세 차트 (날짜/점수 리스트 오른쪽에 배치)
        right_chart_wrapper = QWidget()
        right_chart_layout = QVBoxLayout()
        right_chart_layout.setContentsMargins(0, 0, 0, 0)
        right_chart_layout.setSpacing(0)
        right_chart_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        trend_chart = self._create_trend_chart(list(reversed(recent_values)))
        right_chart_layout.addWidget(trend_chart, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        right_chart_wrapper.setLayout(right_chart_layout)
        right_chart_wrapper.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        right_chart_wrapper.setMinimumWidth(self.theme_manager.scale_pixel(240))
        bottom_layout.addWidget(right_chart_wrapper, 0)

        bottom_container.setLayout(bottom_layout)
        layout.addWidget(bottom_container)

        w.setLayout(layout)
        return w

    def _create_trend_chart(self, values: list) -> QWidget:
        """우측 하단 추세 차트 사이즈 확장"""
        fig = Figure(figsize=(4.8, 2.6), dpi=150)
        fig.subplots_adjust(top=0.96, bottom=0.08, left=0.08, right=0.98)
        ax = fig.add_subplot(111)
        ax.plot(values, color=self._colors['score'], linewidth=2.5, marker='o', markersize=6)
        ax.fill_between(range(len(values)), values, color=self._colors['score'], alpha=0.12)
        ax.set_xlim(-0.3, max(2, len(values) - 1) + 0.3)
        ax.set_ylim(-8, 108)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.set_facecolor(Colors.WHITE.value)

        canvas = FigureCanvas(fig)
        
        # 💡 이 줄의 오타를 수정했습니다! 가로, 세로 크기를 콤마(,)로 정직하게 넘겨줍니다.
        canvas.setFixedSize(
            self.theme_manager.scale_pixel(300),
            self.theme_manager.scale_pixel(170)
        )
        
        canvas.setStyleSheet('background-color: transparent; border: none;')
        return canvas
    
    def _format_session_date(self, start_time: str) -> str:
        try:
            return datetime.fromisoformat(start_time).strftime('%m/%d')
        except Exception:
            return '-'
