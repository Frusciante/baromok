import logging
from datetime import datetime
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget
from src.ui.styles.theme import ThemeManager

logger = logging.getLogger(__name__)

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

        subtitle = QLabel("최근 10개 세션 바른자세 유지율")
        subtitle.setFont(
            QFont("Noto Sans KR", self.theme_manager.scale_pixel(16), QFont.Weight.Bold)
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

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
                        sessions_data.append({
                            "good_posture_percentage": session.statistics.get("good_posture_percentage", 0),
                            "good_posture_seconds": session.statistics.get("good_posture_seconds", 0),
                            "total_detection_seconds": session.statistics.get("duration_seconds", session.duration_seconds),
                            "session_label": session_label,
                            "start_time": session.start_time,
                            "duration_seconds": session.duration_seconds,
                        })
                    self.chart_widget.plot_data(sessions_data)
                    self._update_average_label(sessions_data)
                else:
                    self.chart_widget.plot_data([])
                    self._update_average_label([])
            else:
                self.chart_widget.plot_data([])
                self._update_average_label([])
        except Exception as e:
            logger.error(f"차트 데이터 로드 실패: {e}")
            self.chart_widget.plot_data([])
            self._update_average_label([])

    def _update_average_label(self, sessions_data: list):
        """최근 세션 평균 라벨 갱신"""
        if not hasattr(self, "avg_label"): return
        avg_text = "데이터 없음"
        retention_values = [float(s.get("good_posture_percentage", 0)) for s in sessions_data]
        if retention_values:
            avg_text = f"평균 유지율: {(sum(retention_values) / len(retention_values)):.1f}%"
        self.avg_label.setText(avg_text)

    def showEvent(self, event):
        super().showEvent(event)
        self._load_and_plot_data()

    def _format_session_label(self, session) -> str:
        try: return datetime.fromisoformat(session.start_time).strftime("%m/%d")
        except Exception: return str(session.session_id)[-4:]