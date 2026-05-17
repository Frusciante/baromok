"""차트 위젯 모듈

통계 데이터 시각화 차트
"""

import matplotlib
import matplotlib.cm as cm
from datetime import datetime
from typing import Any

matplotlib.use("QtAgg")  # PyQt6 환경에서 안정적으로 동작하는 Qt 백엔드

# 한글 폰트 설정 (Windows 환경)
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import logging

from src.ui.styles.theme import ThemeManager, Colors

logger = logging.getLogger(__name__)


class CalibrationScatterChart(QWidget):
    """자세 맞춤 실시간 산점도 차트"""

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.theme_manager = theme_manager

        # Figure 생성
        dpi_scale = theme_manager.dpi_scale
        figsize = (6 * dpi_scale, 4 * dpi_scale)
        self.figure = Figure(figsize=figsize, dpi=100)
        self.figure.patch.set_facecolor(Colors.WHITE.value)

        self.canvas = FigureCanvas(self.figure)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.ax = self.figure.add_subplot(111)
        
        self.points_x = []
        self.points_y = []
        self.points_colors = []
        self._draw_cnt = 0 # 성능 최적화용 카운터
        
        self._init_axes()
        logger.info("자세 맞춤 차트 초기화 완료")

    def _init_axes(self):
        # 축 초기화 시 라벨과 범위를 '고정'하여 떨림 방지
        self.ax.set_title("어깨 너비 vs 광대 거리 분포", fontsize=11, fontweight="bold")
        self.ax.set_xlabel("어깨 너비", fontsize=9)
        self.ax.set_ylabel("광대 거리", fontsize=9)
        
        # 범위를 고정하여 축 숫자가 생겼다 없어졌다 하는 현상 방지
        self.ax.set_xlim(0.1, 0.7) 
        self.ax.set_ylim(0.0, 0.4)
        
        # 눈금 고정 (축 숫자가 변하지 않게 함)
        self.ax.set_xticks([0.1, 0.25, 0.4, 0.55, 0.7])
        self.ax.set_yticks([0.0, 0.1, 0.2, 0.3, 0.4])
        
        self.ax.grid(True, linestyle="--", alpha=0.2)
        self.figure.tight_layout()

    def update_live_point(self, x: float, y: float, is_collecting: bool = False, step: int = 0, total_steps: int = 20):
        """실시간 포인트 및 수집된 포인트 업데이트 (안정화 버전)"""
        if x <= 0 or y <= 0:
            return

        # 1. 수집 중인 경우 포인트 저장
        if is_collecting and step > 0:
            self.points_x.append(x)
            self.points_y.append(y)
            color = cm.rainbow((step - 1) / max(1, total_steps - 1) * 0.8)
            self.points_colors.append(color)

        # 2. 성능 최적화: 3프레임마다 한 번씩만 렌더링
        self._draw_cnt += 1
        if self._draw_cnt % 3 != 0:
            return

        # 3. 화면 갱신 (clear 대신 데이터만 업데이트하는 것이 좋으나, 
        # 여러 점의 색상이 달라 scatter를 다시 그리는 것이 간편함. 
        # 대신 축 설정은 유지하여 떨림 방지)
        self.ax.clear()
        self._init_axes()
        
        # 기존 포인트들 그리기
        if self.points_x:
            self.ax.scatter(self.points_x, self.points_y, c=self.points_colors, s=25, alpha=0.6, edgecolors='none')

        # 현재 커서 (X 표시)
        cursor_color = Colors.RED_DANGER.value if is_collecting else Colors.PRIMARY.value
        self.ax.scatter([x], [y], color=cursor_color, s=100, marker='x', linewidths=2)

        self.canvas.draw_idle()

    def clear(self):
        """데이터 초기화"""
        self.points_x = []
        self.points_y = []
        self.points_colors = []
        self.ax.clear()
        self._init_axes()
        self.canvas.draw()


class StatisticsLineChart(QWidget):
    """바른자세 유지율 추이 차트"""

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.theme_manager = theme_manager

        # Figure 생성 (10인치 x 4인치, DPI 100)
        # DPI 스케일링 고려
        dpi_scale = theme_manager.dpi_scale
        figsize = (10 * dpi_scale, 4 * dpi_scale)

        self.figure = Figure(figsize=figsize, dpi=100)
        self.figure.patch.set_facecolor(Colors.GRAY_LIGHT.value)

        # Canvas 생성
        self.canvas = FigureCanvas(self.figure)

        # Hover 상태
        self._bar_patches = []
        self._hover_payloads = []
        self._hover_annotation = None
        self._last_hovered_index = None
        self._motion_connection_id = self.canvas.mpl_connect(
            "motion_notify_event", self._on_canvas_hover
        )
        self._leave_connection_id = self.canvas.mpl_connect(
            "figure_leave_event", self._on_canvas_leave
        )

        # 레이아웃
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        logger.info("StatisticsLineChart 초기화 완료")

    def plot_data(self, sessions_data: list):
        """데이터 플로팅

        Args:
            sessions_data: [{"good_posture_percentage": float, "session_label": str, ...}, ...] 형식의 리스트
        """
        try:
            if not sessions_data:
                self._show_empty_message()
                return

            prepared_sessions = self._prepare_sessions_data(sessions_data)
            if not prepared_sessions:
                self._show_empty_message()
                return

            session_nums = list(range(1, len(prepared_sessions) + 1))
            retention_rates = [
                item["good_posture_percentage"] for item in prepared_sessions
            ]
            session_labels = [item["session_label"] for item in prepared_sessions]
            avg_retention = sum(retention_rates) / len(retention_rates)
            latest_index = len(prepared_sessions) - 1

            # Figure 초기화
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            self.figure.patch.set_facecolor("#F7CBD7")
            ax.set_facecolor("#F7CBD7")

            self._hover_annotation = ax.annotate(
                "",
                xy=(0, 0),
                xytext=(10, 14),
                textcoords="offset points",
                ha="left",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                color=Colors.WHITE.value,
                bbox=dict(
                    boxstyle="round,pad=0.45,rounding_size=0.4",
                    fc="#5D3C6B",
                    ec="#5D3C6B",
                    alpha=0.95,
                ),
                zorder=7,
            )
            self._hover_annotation.set_visible(False)

            bar_colors = ["#FFFFFF"] * len(session_nums)
            bar_edge_colors = [Colors.WHITE.value] * len(session_nums)
            bar_colors[latest_index] = Colors.PINK_PRIMARY.value
            bar_edge_colors[latest_index] = Colors.PINK_PRIMARY.value

            bars = ax.bar(
                session_nums,
                retention_rates,
                width=0.52,
                color=bar_colors,
                edgecolor=bar_edge_colors,
                linewidth=2,
                zorder=3,
            )

            self._bar_patches = list(bars)
            self._hover_payloads = []
            for idx, session in enumerate(prepared_sessions):
                self._hover_payloads.append(
                    {
                        "session_label": session.get("session_label", str(idx + 1)),
                        "good_posture_percentage": session.get(
                            "good_posture_percentage", 0
                        ),
                        "time_ratio_text": session.get("good_posture_time_text", ""),
                    }
                )
            self._last_hovered_index = None

            # 평균선
            avg_line = ax.axhline(
                avg_retention,
                color=Colors.PINK_PRIMARY.value,
                linewidth=2.5,
                zorder=2,
            )

            # 축 레이블
            ax.set_xlabel("세션 번호", fontsize=11, fontweight="bold")
            ax.set_ylabel("유지율 (%)", fontsize=11, fontweight="bold")
            ax.set_ylim(0, 105)

            # X축/ Y축 스타일
            ax.set_xlim(0.4, len(session_nums) + 1.18)
            ax.set_xticks(session_nums)
            ax.set_xticklabels(session_labels, fontsize=10)
            ax.set_yticks([0, 25, 50, 75, 100])

            # 그리드 및 스파인
            ax.grid(True, axis="y", linestyle="--", alpha=0.28, color="#8A6BA8")
            ax.set_axisbelow(True)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color("#3B2F4A")
            ax.spines["bottom"].set_color("#3B2F4A")
            ax.spines["left"].set_linewidth(1.2)
            ax.spines["bottom"].set_linewidth(1.6)

            # 범례
            ax.legend(
                [bars[0], avg_line],
                ["바른자세 유지율", "평균 유지율"],
                loc="upper left",
                fontsize=10,
                frameon=True,
                facecolor="#FFFFFF",
                edgecolor="#D7B0C0",
            )

            # 각 세션 값 표기
            for idx, bar in enumerate(bars):
                value = retention_rates[idx]
                bar_x = bar.get_x() + bar.get_width() / 2
                bar_height = bar.get_height()

                if idx == latest_index:
                    continue

                ax.text(
                    bar_x,
                    bar_height + 2.2,
                    f"{value:.1f}%",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    fontweight="bold",
                    color="#5D3C6B",
                    zorder=5,
                )

            latest_bar = bars[latest_index]
            latest_value = retention_rates[latest_index]
            latest_label = session_labels[latest_index]
            latest_meta = self._extract_session_meta(prepared_sessions[latest_index])
            latest_annotation = f"{latest_label} 유지율 {latest_value:.2f}%"
            if latest_meta:
                latest_annotation = f"{latest_annotation}\n{latest_meta}"

            ax.annotate(
                latest_annotation,
                xy=(
                    latest_bar.get_x() + latest_bar.get_width() / 2,
                    latest_bar.get_height(),
                ),
                xytext=(0, 28),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
                color=Colors.WHITE.value,
                bbox=dict(
                    boxstyle="round,pad=0.55,rounding_size=0.8",
                    fc=Colors.PINK_PRIMARY.value,
                    ec=Colors.PINK_PRIMARY.value,
                    alpha=0.98,
                ),
                arrowprops=dict(
                    arrowstyle="-|>",
                    color=Colors.PINK_PRIMARY.value,
                    lw=1.2,
                    shrinkA=0,
                    shrinkB=4,
                ),
                zorder=6,
            )

            # 평균 라인 우측 표시
            ax.text(
                len(session_nums) + 0.63,
                avg_retention,
                f"평균\n{avg_retention:.1f}%",
                ha="left",
                va="center",
                fontsize=13,
                fontweight="bold",
                color=Colors.PINK_PRIMARY.value,
                clip_on=False,
                zorder=6,
            )

            # 레이아웃 조정
            self.figure.tight_layout()

            # 렌더링
            self.canvas.draw()

            logger.info(f"차트 플로팅 완료: {len(session_nums)}개 세션")

        except Exception as e:
            logger.error(f"차트 플로팅 중 오류: {e}")
            self._show_empty_message()

    def update_data(self, sessions_data: list):
        """데이터 업데이트 (새로고침)"""
        self.plot_data(sessions_data)

    def _show_empty_message(self):
        """데이터 없음 메시지 표시"""
        try:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.text(
                0.5,
                0.5,
                "데이터 없음",
                ha="center",
                va="center",
                fontsize=14,
                color=Colors.GRAY_DARK.value,
            )
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
            ax.set_facecolor(Colors.WHITE.value)
            self._bar_patches = []
            self._hover_payloads = []
            self._hover_annotation = None
            self._last_hovered_index = None
            self.canvas.draw()
        except Exception as e:
            logger.error(f"빈 메시지 표시 중 오류: {e}")

    def _on_canvas_hover(self, event):
        """막대 그래프 hover 시 세션 상세 툴팁 표시"""
        if (
            event is None
            or event.inaxes is None
            or not self._bar_patches
            or self._hover_annotation is None
        ):
            self._hide_hover_annotation()
            return

        hovered_index = None
        for idx, bar in enumerate(self._bar_patches):
            contains, _ = bar.contains(event)
            if contains:
                hovered_index = idx
                break

        if hovered_index is None:
            self._hide_hover_annotation()
            return

        if (
            hovered_index == self._last_hovered_index
            and self._hover_annotation.get_visible()
        ):
            return

        payload = self._hover_payloads[hovered_index]
        tooltip_text = self._build_hover_text(payload)
        bar = self._bar_patches[hovered_index]
        bar_center_x = bar.get_x() + bar.get_width() / 2
        bar_top_y = bar.get_height()

        self._hover_annotation.xy = (bar_center_x, bar_top_y)
        self._hover_annotation.set_text(tooltip_text)
        self._hover_annotation.set_visible(True)
        self._last_hovered_index = hovered_index
        self.canvas.draw_idle()

    def _on_canvas_leave(self, _event):
        """차트 영역을 벗어나면 툴팁 숨김"""
        self._hide_hover_annotation()

    def _hide_hover_annotation(self):
        if self._hover_annotation is None:
            return

        if self._hover_annotation.get_visible():
            self._hover_annotation.set_visible(False)
            self._last_hovered_index = None
            self.canvas.draw_idle()

    def _build_hover_text(self, payload: dict) -> str:
        session_label = payload.get("session_label", "-")
        percentage = self._coerce_float(payload.get("good_posture_percentage", 0))
        ratio_text = payload.get("time_ratio_text", "")

        lines = [
            f"세션: {session_label}",
            f"유지율: {percentage:.1f}%",
        ]

        if ratio_text:
            lines.append(f"유지시간/총시간: {ratio_text}")

        return "\n".join(lines)

    def _prepare_sessions_data(self, sessions_data: list) -> list:
        """차트 표시용 세션 데이터를 정리한다."""
        prepared = []
        for index, session in enumerate(sessions_data, start=1):
            if not isinstance(session, dict):
                continue

            retention_value = self._coerce_float(
                session.get("good_posture_percentage", 0)
            )
            session_label = self._format_session_label(session, index)
            prepared.append(
                {
                    "good_posture_percentage": retention_value,
                    "session_label": session_label,
                    "duration_text": self._format_duration_text(session),
                    "good_posture_time_text": self._format_time_ratio_text(session),
                }
            )

        return prepared

    def _coerce_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _format_session_label(self, session: dict, fallback_index: int) -> str:
        label = session.get("session_label")
        if label:
            return str(label)

        start_time = session.get("start_time")
        if start_time:
            try:
                return datetime.fromisoformat(str(start_time)).strftime("%m/%d")
            except ValueError:
                pass

        return f"{fallback_index}"

    def _format_duration_text(self, session: dict) -> str:
        duration_seconds = session.get("duration_seconds")
        try:
            total_seconds = int(duration_seconds)
        except (TypeError, ValueError):
            return ""

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _format_time_ratio_text(self, session: dict) -> str:
        good_seconds = self._coerce_float(session.get("good_posture_seconds", 0))
        total_seconds = self._coerce_float(
            session.get("total_detection_seconds", session.get("duration_seconds", 0))
        )

        if total_seconds <= 0:
            return ""

        return f"{self._seconds_to_hhmmss(good_seconds)}/{self._seconds_to_hhmmss(total_seconds)}"

    def _seconds_to_hhmmss(self, seconds: float) -> str:
        total_seconds = max(0, int(round(seconds)))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        remaining_seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"

    def _extract_session_meta(self, session: dict) -> str:
        duration_text = session.get("good_posture_time_text", "")
        if duration_text:
            return duration_text

        fallback_duration = session.get("duration_text", "")
        if fallback_duration:
            return fallback_duration

        return ""
