# 통계 화면 차트 구현 계획

**작성일**: 2026-05-09  
**단계**: Phase 4 후속 (UI 상세 완성)  
**예상 기간**: 3-4시간

---

## 목차

1. [목표 및 범위](#목표-및-범위)
2. [현재 상태](#현재-상태)
3. [기술 검토](#기술-검토)
4. [구현 계획](#구현-계획)
5. [차트 설계](#차트-설계)
6. [검증 전략](#검증-전략)

---

## 목표 및 범위

### 목표
- ✅ StatisticsScreen의 placeholder 차트 구현
- ✅ 최근 10개 세션 데이터 시각화
- ✅ 바른자세 유지율 추이 표시
- ✅ 실시간 데이터 로드 및 업데이트

### 범위

| 항목 | 내용 |
|------|------|
| **차트 유형** | 선 그래프 (Line Chart) |
| **데이터** | 세션 ID, 바른자세 유지율(%), 타임스탬프 |
| **X축** | 세션 번호 (1~10) 또는 시간 |
| **Y축** | 바른자세 유지율 (0~100%) |
| **시계열** | 최근 10개 세션 (오래된 순서대로) |
| **인터랙션** | 마우스 호버 시 값 표시 (도구팁) |

### 제외 사항
- 고급 커스터마이징 (색상 선택, 레이아웃 변경 등)
- 데이터 내보내기 (CSV/PDF)
- 다중 선 그래프 (다른 지표 비교)

---

## 현재 상태

### StatisticsScreen 구조
```python
class StatisticsScreen(QWidget):
    - 제목: "최근 10개 세션 바른자세 유지율"
    - 차트: [차트 영역]\n(Phase 5에서 matplotlib/PyQtGraph) [placeholder]
    - 통계: 평균 유지율 텍스트 표시
    - 버튼: 돌아가기
```

### 문제점
- 차트 영역이 QLabel placeholder로만 구현됨
- 실제 데이터 시각화 없음
- 세션 데이터 활용 미흡

---

## 기술 검토

### 후보 라이브러리

| 라이브러리 | 장점 | 단점 | 선택 |
|-----------|------|------|------|
| **matplotlib** | 강력한 기능, 풍부한 문서, PyQt 연동 쉬움 | 약간 무거움 | ✅ 채택 |
| **PyQtGraph** | 경량, PyQt 네이티브 | 학습곡선 높음, 문서 부족 | - |
| **Plotly** | 인터랙티브 좋음 | 웹 기반, 오버헤드 | - |

### 선택 근거
- matplotlib + PyQt5Agg backend 조합
- `matplotlib.backends.backend_qt5agg.FigureCanvasQTAgg` 사용
- 기존 프로젝트와의 통합 용이

---

## 구현 계획

### 1단계: 의존성 확인 및 추가 (5분)

**필요한 패키지**:
```bash
pip list | grep matplotlib
# matplotlib이 이미 설치되어 있을 가능성 높음
```

만약 없으면:
```bash
pip install matplotlib
```

### 2단계: 차트 위젯 클래스 생성 (40분)

**파일**: `src/ui/widgets/chart_widgets.py` (새 파일)

**주요 클래스**:
```python
class StatisticsLineChart(QWidget):
    """바른자세 유지율 추이 선 그래프"""
    
    def __init__(self, theme_manager: ThemeManager):
        # matplotlib Figure 생성
        # PyQt5Agg canvas 설정
        
    def plot_data(self, sessions_data: list):
        """세션 데이터 플로팅"""
        # X축: 세션 번호
        # Y축: 유지율 (%)
        # 스타일: 선 그래프 + 마커
        
    def update_data(self, sessions_data: list):
        """데이터 업데이트 (새로고침)"""
```

### 3단계: StatisticsScreen 통합 (30분)

**수정 항목**:
- placeholder QLabel 제거
- StatisticsLineChart 위젯 추가
- 데이터 로드 및 플로팅
- 세션 변경 시 자동 갱신

### 4단계: 스타일링 및 테마 연동 (15분)

**요소**:
- 차트 배경색: 테마 색상 적용
- 선 색상: 프로젝트 컬러 팔레트 사용
- 폰트: ThemeManager 스케일 적용
- 테두리: 테마 규칙 준수

### 5단계: 검증 및 테스트 (20분)

---

## 차트 설계

### 데이터 구조

```python
# SessionManager에서 반환되는 데이터 구조
sessions_data = [
    {
        "session_id": "uuid",
        "timestamp": "2026-05-09 10:00:00",
        "good_posture_percentage": 78.5,
        ...
    },
    ...
]
```

### 차트 렌더링

```
Y축: 0~100% (바른자세 유지율)
     |
 100%|     ●
     |    / \
  80%|   /   ●---●
     |  /         \
  60%|_/__________●__
     |_____________________ X축
     1   2   3   4   5    (세션 번호)
```

### 스타일 규칙

| 요소 | 값 |
|------|-----|
| 선 색상 | #7B5BA8 (PURPLE_PRIMARY) |
| 마커 색상 | #E85D75 (PINK_PRIMARY) |
| 마커 크기 | 8px |
| 선 두께 | 2px |
| 배경색 | #F5F5F5 (GRAY_LIGHT) |
| 그리드 | 밝은 회색, 점선 |

---

## 구현 상세

### A. 차트 위젯 클래스

**위치**: `src/ui/widgets/chart_widgets.py`

```python
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QWidget, QVBoxLayout

class StatisticsLineChart(QWidget):
    """바른자세 유지율 추이 선 그래프"""
    
    def __init__(self, theme_manager):
        super().__init__()
        self.theme_manager = theme_manager
        
        # Figure 생성 (10인치 x 4인치, DPI 100)
        self.figure = Figure(figsize=(10, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        
        # 레이아웃
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.setLayout(layout)
    
    def plot_data(self, sessions_data: list):
        """데이터 플로팅"""
        if not sessions_data:
            self._show_empty_message()
            return
        
        # 데이터 추출
        session_nums = list(range(1, len(sessions_data) + 1))
        retention_rates = [s.get("good_posture_percentage", 0) for s in sessions_data]
        
        # 축 설정
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # 선 그래프 그리기
        ax.plot(session_nums, retention_rates, 
                marker='o', linewidth=2, markersize=8,
                color='#7B5BA8', markerfacecolor='#E85D75',
                label='바른자세 유지율')
        
        # 축 레이블
        ax.set_xlabel('세션 번호', fontsize=11)
        ax.set_ylabel('유지율 (%)', fontsize=11)
        ax.set_ylim(0, 100)
        
        # 그리드
        ax.grid(True, linestyle='--', alpha=0.3)
        
        # 범례
        ax.legend(loc='upper left')
        
        self.canvas.draw()
    
    def _show_empty_message(self):
        """데이터 없음 메시지 표시"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, '데이터 없음', 
                ha='center', va='center', fontsize=14)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        self.canvas.draw()
```

### B. StatisticsScreen 수정

```python
def setup_ui(self):
    """UI 구성"""
    layout = QVBoxLayout()
    
    # 제목
    title = QLabel("최근 10개 세션 바른자세 유지율")
    layout.addWidget(title)
    
    # 차트 위젯 (새로)
    from src.ui.widgets.chart_widgets import StatisticsLineChart
    self.chart_widget = StatisticsLineChart(self.theme_manager)
    layout.addWidget(self.chart_widget, 1)
    
    # 데이터 로드 및 플로팅
    if self.session_manager:
        recent_sessions = self.session_manager.load_recent_sessions(10)
        sessions_data = [
            {
                "good_posture_percentage": session.statistics.get("good_posture_percentage", 0)
            }
            for session in recent_sessions
        ]
        self.chart_widget.plot_data(sessions_data)
    
    # 평균 유지율
    avg_label = QLabel(...)
    layout.addWidget(avg_label)
    
    # 돌아가기 버튼
    back_btn = QPushButton("돌아가기")
    layout.addWidget(back_btn)
    
    self.setLayout(layout)
```

---

## 검증 전략

### 정적 검증
- `src/ui/widgets/chart_widgets.py` 오류 확인
- import 문제 없는지 확인
- matplotlib 버전 호환성 확인

### 기능 검증
1. **차트 렌더링**:
   - 차트가 정상 표시되는가?
   - 데이터가 올바르게 플로팅되는가?

2. **데이터 로드**:
   - 세션 데이터 로드 성공?
   - 최근 10개 세션 정렬 정상?

3. **스타일**:
   - 차트 색상이 테마와 일치하는가?
   - DPI 스케일링 적용되는가?

4. **빈 상태**:
   - 데이터 없을 때 적절한 메시지 표시?

---

## 참고 사항

- matplotlib은 이미 requirements.txt에 포함되어 있을 가능성 높음
- FigureCanvas는 PyQt6 호환성 확인 필요
- DPI 스케일링을 위해 figsize 조정 필요할 수 있음
