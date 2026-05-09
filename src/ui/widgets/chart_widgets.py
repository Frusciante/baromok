"""차트 위젯 모듈

통계 데이터 시각화 차트
"""

import matplotlib

matplotlib.use("Qt5Agg")  # PyQt5/PyQt6 호환성을 위해 명시적으로 설정

# 한글 폰트 설정 (Windows 환경)
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import logging

from src.ui.styles.theme import ThemeManager, Colors

logger = logging.getLogger(__name__)


class StatisticsLineChart(QWidget):
    """바른자세 유지율 추이 선 그래프"""

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

        # 레이아웃
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        logger.info("StatisticsLineChart 초기화 완료")

    def plot_data(self, sessions_data: list):
        """데이터 플로팅

        Args:
            sessions_data: [{"good_posture_percentage": float}, ...] 형식의 리스트
        """
        try:
            if not sessions_data:
                self._show_empty_message()
                return

            # 데이터 추출
            session_nums = list(range(1, len(sessions_data) + 1))
            retention_rates = [
                s.get("good_posture_percentage", 0) if isinstance(s, dict) else 0
                for s in sessions_data
            ]

            # Figure 초기화
            self.figure.clear()
            ax = self.figure.add_subplot(111)

            # 선 그래프 그리기
            ax.plot(
                session_nums,
                retention_rates,
                marker="o",
                linewidth=2,
                markersize=8,
                color=Colors.PURPLE_PRIMARY.value,
                markerfacecolor=Colors.PINK_PRIMARY.value,
                markeredgecolor=Colors.PINK_PRIMARY.value,
                markeredgewidth=1.5,
                label="바른자세 유지율",
            )

            # 축 레이블
            ax.set_xlabel("세션 번호", fontsize=11, fontweight="bold")
            ax.set_ylabel("유지율 (%)", fontsize=11, fontweight="bold")
            ax.set_ylim(0, 105)
            ax.set_xlim(0.5, len(session_nums) + 0.5)

            # Y축 눈금 (10% 간격)
            ax.set_yticks(range(0, 101, 10))

            # 그리드
            ax.grid(True, linestyle="--", alpha=0.3, color=Colors.GRAY_DARK.value)

            # 배경색
            ax.set_facecolor(Colors.WHITE.value)

            # 범례
            ax.legend(loc="upper left", fontsize=10)

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
            self.canvas.draw()
        except Exception as e:
            logger.error(f"빈 메시지 표시 중 오류: {e}")
