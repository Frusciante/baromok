import logging
from datetime import datetime
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget
from src.ui.styles.theme import ThemeManager
from src.ui.styles.font_loader import app_font

logger = logging.getLogger(__name__)


class DateAggregator:
    """날짜별 세션 집계 전략.

    같은 session_label(날짜)을 가진 세션들을 하나의 항목으로 합산합니다.
    파일 저장 구조와 무관하게 표현 전략만 교체할 수 있도록 분리되어 있습니다.
    다른 집계 전략(주별, 월별 등)이 필요하면 동일 인터페이스로 새 클래스를 작성하세요.
    """

    def aggregate(self, sessions: list) -> list:
        """세션 리스트를 날짜별로 집계하여 반환합니다.

        Args:
            sessions: _load_and_plot_data에서 만든 session dict 리스트
                      (session_label, good_posture_seconds, total_detection_seconds 포함)
        Returns:
            날짜 순서를 유지한 집계 결과 리스트. session_count 키 추가.
        """
        grouped: dict = {}
        order: list = []

        for session in sessions:
            label = session.get("session_label", "")
            if label not in grouped:
                grouped[label] = {
                    "session_label": label,
                    "good_posture_seconds": 0.0,
                    "total_detection_seconds": 0.0,
                    "duration_seconds": 0.0,
                    "session_count": 0,
                    "start_time": session.get("start_time", ""),
                }
                order.append(label)

            g = grouped[label]
            g["good_posture_seconds"] += float(session.get("good_posture_seconds", 0) or 0)
            g["total_detection_seconds"] += float(session.get("total_detection_seconds", 0) or 0)
            g["duration_seconds"] += float(session.get("duration_seconds", 0) or 0)
            g["session_count"] += 1

        result = []
        for label in order:
            g = grouped[label]
            total = g["total_detection_seconds"]
            g["good_posture_percentage"] = (g["good_posture_seconds"] / total * 100) if total > 0 else 0.0
            result.append(g)

        return result


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

        subtitle = QLabel("날짜별 바른자세 유지율")
        subtitle.setFont(
            app_font(self.theme_manager.scale_pixel(19), QFont.Weight.Bold)
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        self.chart_widget = StatisticsLineChart(self.theme_manager)
        layout.addWidget(self.chart_widget, 1)

        self.avg_label = QLabel("데이터 없음")
        self.avg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avg_label.setFont(
            app_font(self.theme_manager.scale_pixel(17), QFont.Weight.Bold)
        )
        layout.addWidget(self.avg_label)

        self._load_and_plot_data()

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
                    grouped_data = DateAggregator().aggregate(sessions_data)
                    self.chart_widget.plot_data(grouped_data)
                    self._update_average_label(grouped_data)
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