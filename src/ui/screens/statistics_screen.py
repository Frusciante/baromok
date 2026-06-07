import logging
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)
from src.ui.styles.theme import ThemeManager
from src.ui.styles.font_loader import app_font

logger = logging.getLogger(__name__)


class DateAggregator:
    """날짜별 세션 집계."""

    def aggregate(self, sessions: list) -> list:
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
                    "posture_distribution": {},
                    "total_frames": 0,
                }
                order.append(label)

            g = grouped[label]
            g["good_posture_seconds"] += float(session.get("good_posture_seconds", 0) or 0)
            g["total_detection_seconds"] += float(session.get("total_detection_seconds", 0) or 0)
            g["duration_seconds"] += float(session.get("duration_seconds", 0) or 0)
            g["session_count"] += 1
            g["total_frames"] += int(session.get("total_frames", 0) or 0)

            for pt, cnt in (session.get("posture_distribution") or {}).items():
                g["posture_distribution"][pt] = g["posture_distribution"].get(pt, 0) + int(cnt or 0)

        result = []
        for label in order:
            g = grouped[label]
            total = g["total_detection_seconds"]
            g["good_posture_percentage"] = (
                g["good_posture_seconds"] / total * 100 if total > 0 else 0.0
            )
            result.append(g)

        return result


def _week_range(offset: int = 0):
    """offset 주 전/후의 월~일 범위 반환 (date 객체)."""
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    sunday = monday + timedelta(days=6)
    return monday, sunday


class StatisticsScreen(QWidget):
    """통계 화면"""

    back_to_hub_signal = pyqtSignal()

    def __init__(self, theme_manager: ThemeManager, session_manager=None):
        super().__init__()
        self.theme_manager = theme_manager
        self.session_manager = session_manager
        self._week_offset = 0
        self.setup_ui()

    def setup_ui(self):
        from src.ui.widgets.chart_widgets import StatisticsLineChart, PostureBreakdownChart

        outer = QVBoxLayout()
        outer.setContentsMargins(20, 12, 20, 8)
        outer.setSpacing(6)

        # ── 주차 네비게이션 ──────────────────────────────────────────
        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)

        btn_style = (
            "QPushButton { background:#EDE9FE; color:#7C3AED; border:none;"
            " border-radius:6px; padding:2px 12px; font-weight:bold; }"
            "QPushButton:hover { background:#DDD6FE; }"
            "QPushButton:disabled { background:#F3F4F6; color:#D1D5DB; }"
        )

        self.prev_btn = QPushButton("◀ 이전 주")
        self.prev_btn.setFont(app_font(self.theme_manager.scale_pixel(12)))
        self.prev_btn.setFixedHeight(self.theme_manager.scale_pixel(36))
        self.prev_btn.setStyleSheet(btn_style)
        self.prev_btn.clicked.connect(self._go_prev_week)

        self.week_label = QLabel()
        self.week_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.week_label.setFont(
            app_font(self.theme_manager.scale_pixel(16), QFont.Weight.Bold)
        )

        self.next_btn = QPushButton("다음 주 ▶")
        self.next_btn.setFont(app_font(self.theme_manager.scale_pixel(12)))
        self.next_btn.setFixedHeight(self.theme_manager.scale_pixel(36))
        self.next_btn.setStyleSheet(btn_style)
        self.next_btn.clicked.connect(self._go_next_week)

        nav_row.addWidget(self.prev_btn)
        nav_row.addWidget(self.week_label, 1)
        nav_row.addWidget(self.next_btn)
        outer.addLayout(nav_row)

        # ── 바른자세 유지율 차트 ─────────────────────────────────────
        self.chart_widget = StatisticsLineChart(self.theme_manager)
        outer.addWidget(self.chart_widget, 4)

        self.avg_label = QLabel("데이터 없음")
        self.avg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avg_label.setFont(
            app_font(self.theme_manager.scale_pixel(14), QFont.Weight.Bold)
        )
        self.avg_label.setStyleSheet("color: #7C3AED;")
        outer.addWidget(self.avg_label)

        # ── 구분선 ──────────────────────────────────────────────────
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.NoFrame)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #D1D5DB;")
        outer.addWidget(separator)

        # ── 자세 유형별 분석 ─────────────────────────────────────────
        breakdown_title = QLabel("자세 유형별 비율 (주간 합산)")
        breakdown_title.setFont(
            app_font(self.theme_manager.scale_pixel(13), QFont.Weight.Bold)
        )
        breakdown_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        breakdown_title.setStyleSheet("color: #6B7280;")
        outer.addWidget(breakdown_title)

        self.breakdown_chart = PostureBreakdownChart(self.theme_manager)
        self.breakdown_chart.setMaximumHeight(self.theme_manager.scale_pixel(100))
        outer.addWidget(self.breakdown_chart)

        self.setLayout(outer)
        self._refresh()

    # ------------------------------------------------------------------
    # 주차 네비게이션
    # ------------------------------------------------------------------
    def _go_prev_week(self):
        self._week_offset -= 1
        self._refresh()

    def _go_next_week(self):
        if self._week_offset < 0:
            self._week_offset += 1
        self._refresh()

    def _refresh(self):
        monday, sunday = _week_range(self._week_offset)
        self.week_label.setText(
            f"< {monday.strftime('%Y.%m.%d')} ~ {sunday.strftime('%m.%d')} >"
        )
        self.next_btn.setEnabled(self._week_offset < 0)
        self._load_and_plot_data(monday, sunday)

    # ------------------------------------------------------------------
    # 데이터 로드 & 차트 업데이트
    # ------------------------------------------------------------------
    def _load_and_plot_data(self, monday=None, sunday=None):
        try:
            if monday is None or sunday is None:
                monday, sunday = _week_range(self._week_offset)

            if not self.session_manager:
                self._plot_empty()
                return

            start_iso = monday.isoformat()
            end_iso = (sunday + timedelta(days=1)).isoformat()

            sessions = self.session_manager.load_sessions_by_date_range(start_iso, end_iso)

            if not sessions:
                self._plot_empty()
                return

            sessions_data = []
            for s in sessions:
                sessions_data.append({
                    "good_posture_percentage": s.statistics.get("good_posture_percentage", 0),
                    "good_posture_seconds":    s.statistics.get("good_posture_seconds", 0),
                    "total_detection_seconds": s.statistics.get("duration_seconds", s.duration_seconds),
                    "session_label":           self._format_date_label(s.start_time),
                    "start_time":              s.start_time,
                    "duration_seconds":        s.duration_seconds,
                    "posture_distribution":    s.statistics.get("posture_distribution", {}),
                    "total_frames":            s.total_frames,
                })

            grouped_map = {g["session_label"]: g
                           for g in DateAggregator().aggregate(sessions_data)}

            # 7일 전체 고정 (데이터 없는 날 = 0)
            full_week = []
            for offset in range(7):
                day = monday + timedelta(days=offset)
                label = day.strftime("%m/%d")
                if label in grouped_map:
                    full_week.append(grouped_map[label])
                else:
                    full_week.append({
                        "session_label": label,
                        "good_posture_percentage": 0.0,
                        "good_posture_seconds": 0.0,
                        "total_detection_seconds": 0.0,
                        "duration_seconds": 0.0,
                        "session_count": 0,
                        "start_time": day.isoformat(),
                        "posture_distribution": {},
                        "total_frames": 0,
                    })

            self.chart_widget.plot_data(full_week)
            self._update_average_label(full_week)
            self._update_breakdown_chart(full_week)

        except Exception as e:
            logger.error(f"차트 데이터 로드 실패: {e}", exc_info=True)
            self._plot_empty()

    def _plot_empty(self):
        self.chart_widget.plot_data([])
        self.avg_label.setText("데이터 없음")
        self.breakdown_chart.plot_data({}, 0)

    def _update_average_label(self, grouped: list):
        vals = [float(s.get("good_posture_percentage", 0))
                for s in grouped if s.get("session_count", 0) > 0]
        if not vals:
            self.avg_label.setText("데이터 없음")
            return
        avg = sum(vals) / len(vals)
        self.avg_label.setText(f"주간 평균 유지율: {avg:.1f}%")

    def _update_breakdown_chart(self, grouped: list):
        merged_dist: dict = {}
        total_frames = 0
        for g in grouped:
            for pt, cnt in (g.get("posture_distribution") or {}).items():
                merged_dist[pt] = merged_dist.get(pt, 0) + int(cnt or 0)
            total_frames += int(g.get("total_frames", 0) or 0)
        self.breakdown_chart.plot_data(merged_dist, total_frames)

    # ------------------------------------------------------------------
    # showEvent
    # ------------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()

    def _format_date_label(self, start_time: str) -> str:
        try:
            return datetime.fromisoformat(start_time).strftime("%m/%d")
        except Exception:
            return "?"
