# Phase 3: PyQt UI - 구현 계획서

**기능**: 6개 화면 구현, 레이아웃, 스타일, 상태 표시  
**예상 기간**: 10-15시간  
**목표**: UI 프레임 완성 (Phase 4에서 엔진과 연결)

---

## 1. 개요

### 목표
- PyQt6 기반 데스크톱 UI 구현
- 6개 화면: 초기 촬영, 허브, 설정, 통계, 감지 진행, 경고
- Windows 환경 최적화 (DPI, 폰트, 레이아웃)
- 상태별 색상 & 레이아웃 변경

### 아키텍처
```
MainWindow (QMainWindow)
  ├── Header (상단 헤더)
  ├── QStackedWidget (화면 전환)
  │   ├── BaselineScreen (초기 촬영)
  │   ├── HubScreen (메인 허브)
  │   ├── SettingsScreen (환경 설정)
  │   ├── StatisticsScreen (통계)
  │   ├── DetectionScreen (감지 진행)
  │   └── AlertWidget (경고)
  └── Footer (하단 안내)
```

---

## 2. 주요 모듈별 계획

### 2.1 main_window.py (메인 윈도우)

**클래스**: `MainWindow(QMainWindow)`

**기능**:
- 상단 헤더: 앱명 + 최소화/닫기 버튼
- QStackedWidget으로 화면 관리
- 하단 고정 안내 문구
- 윈도우 크기: 1280x800 (최소 800x600)

**메서드**:
- `__init__()`: UI 초기화
- `setup_ui()`: 레이아웃 구성
- `switch_to_screen(screen_name)`: 화면 전환
- `setup_styles()`: 스타일시트 적용
- `closeEvent()`: 종료 처리

**특징**:
- DPI 스케일 자동 대응 (QGuiApplication.primaryScreen().devicePixelRatio())
- 폰트 자동 스케일
- 창 크기 조정 시 레이아웃 유지

---

### 2.2 styles/theme.py (테마 & 스타일시트)

**색상 팔레트**:
```python
Colors = {
    'primary_purple': '#7B5BA8',      # 보라 (주요 액션)
    'primary_pink': '#E85D75',        # 핑크 (강조/경고)
    'light_gray': '#F5F5F5',          # 배경
    'dark_gray': '#999999',           # 텍스트 (약함)
    'text_black': '#333333',          # 텍스트 (주요)
    'white': '#FFFFFF',               # 흰색
    'success_green': '#4CAF50',       # 정상 (초록)
    'warning_yellow': '#FFC107',      # 경고 (노랑)
    'danger_red': '#F44336',          # 위험 (빨강)
}
```

**스타일시트**:
- QPushButton: 보라 배경, 둥근 모서리(10px), hover 효과
- QLabel: 폰트 스케일 자동
- QSlider: 커스텀 색상
- QCheckBox: 보라 체크
- 다크/라이트 모드 준비 (선택)

**DPI 스케일 함수**:
```python
def scale_size(size: int, dpi_scale: float = 1.0) -> int:
    """크기를 DPI에 맞춰 스케일링"""
    return int(size * dpi_scale)

def scale_font(font_size: int, dpi_scale: float = 1.0) -> int:
    """폰트 크기를 DPI에 맞춰 스케일링"""
    return int(font_size * dpi_scale)
```

---

### 2.3 screens/baseline_screen.py (초기 바른자세 촬영)

**레이아웃**:
- 상단: "초기 바른자세 촬영" 타이틀 배지
- 중앙: 웹캠 프리뷰 영역 (카드형)
- 중간: 촬영 가이드 (체크리스트)
- 하단: "촬영" 버튼 (큼, 보라색)

**기능**:
- 웹캠 프리뷰 표시 (QLabel + QPixmap)
- 카운트다운 표시 (5초)
- 진행 상황 바 (QProgressBar)
- 촬영 완료 후 다음 화면으로 자동 전환 (또는 버튼)

**신호**:
- `baseline_captured_signal`: baseline 수집 완료

---

### 2.4 screens/hub_screen.py (메인 허브)

**레이아웃**:
- 중앙: 일러스트 영역 (QLabel 또는 QPixmap)
- 오른쪽: 버튼 2개 (환경 설정, 나의 통계)
- 하단: "바로목 감지 시작" 버튼 (큼, 주요)

**기능**:
- 버튼 클릭 → 해당 화면 전환
- 아이콘 + 텍스트 버튼

**신호**:
- `start_detection_signal`: 감지 시작
- `open_settings_signal`: 설정 화면
- `open_statistics_signal`: 통계 화면

---

### 2.5 screens/settings_screen.py (환경 설정)

**레이아웃**:
- 좌측: 카테고리 버튼 (4개)
  - 알림 설정
  - 소리 설정
  - 팝업 설정
  - 자동 시작
- 우측: 설정값 UI
  - 토글 (QCheckBox 또는 QToggleButton)
  - 슬라이더 (QSlider)
  - 라디오 버튼 (QRadioButton)
- 하단: "확인" 버튼

**기능**:
- 카테고리 선택 시 우측 UI 변경
- 슬라이더로 소리 크기 조절 (0~100)
- 팝업 위치 선택 (중앙/상단)
- "확인" 버튼 클릭 시 설정 저장

**신호**:
- `settings_saved_signal(settings)`: 설정 저장

---

### 2.6 screens/statistics_screen.py (나의 통계)

**레이아웃**:
- 상단: "최근 10개 세션 바른자세 유지율" 타이틀
- 중앙: 막대 차트 (QChart 또는 matplotlib)
- 하단: 평균 유지율 표시

**기능**:
- 막대 차트: 날짜별 유지율 (%)
- 평균선: 평균 유지율
- 강조 막대: 특정 세션 강조
- 툴팁: 날짜, 유지율, 시간 정보

**신호**:
- `back_to_hub_signal`: 허브로 돌아가기

---

### 2.7 screens/detection_screen.py (감지 진행)

**레이아웃**:
- 상단: 상태 표시 (감지중/일시정지) + 환경 설정 바로가기
- 중앙: 사용 시간 표시 (큰 폰트, 시간:분:초 포맷)
- 중앙 하단: 웹캠 프리뷰
- 하단: 현재 자세 상태 라벨 (색상 코딩)
  - 초록: 바른 자세 (NORMAL)
  - 주황: 경고 (WARNING)
  - 빨강: 나쁜 자세 (BAD_POSTURE)
- 버튼: "감지 일시정지", "감지 종료"

**기능**:
- 실시간 자세 상태 업데이트 (Signal/Slot)
- 타이머: 사용 시간 표시
- 상태별 색상 변경
- 일시정지/재시작 토글
- 종료 시 통계 저장

**신호**:
- `detection_started_signal`: 감지 시작
- `detection_paused_signal`: 감지 일시정지
- `detection_resumed_signal`: 감지 재시작
- `detection_stopped_signal`: 감지 종료
- `posture_state_changed_signal(state, confirmed_posture)`: 자세 상태 변경

---

### 2.8 widgets/alert_popup.py (경고 팝업)

**레이아웃**:
- 배너형: 화면 상단 고정 (이미지: red banner)
- 토스트형: 중앙 또는 상단 (둥근 모서리, 반투명)

**기능**:
- 메시지 표시
- 자동 닫기 (3초) 또는 수동 닫기
- 중복 경고 억제 (쿨다운)
- 아이콘 + 텍스트

**신호**:
- `alert_closed_signal`: 경고 닫힘

---

### 2.9 widgets/custom_widgets.py (커스텀 위젯)

**위젯 목록**:
1. `RoundedButton`: 둥근 모서리 버튼
2. `StateLabel`: 상태 표시 라벨 (색상 코딩)
3. `ProgressCircle`: 원형 진행 표시기
4. `TimeDisplay`: 시간 표시 (시:분:초)
5. `ToggleButton`: 토글 버튼

---

## 3. 이벤트 흐름

```
MainWindow
  ├─ BaselineScreen
  │   └─ [촬영 완료] → HubScreen
  ├─ HubScreen
  │   ├─ [감지 시작] → DetectionScreen
  │   ├─ [환경 설정] → SettingsScreen
  │   └─ [통계] → StatisticsScreen
  ├─ SettingsScreen
  │   └─ [확인] → HubScreen
  ├─ StatisticsScreen
  │   └─ [돌아가기] → HubScreen
  ├─ DetectionScreen
  │   ├─ [일시정지/재시작] (토글)
  │   ├─ [환경 설정] → SettingsScreen
  │   └─ [종료] → HubScreen (통계 저장)
  └─ AlertPopup
      └─ [자동/수동 닫기]
```

---

## 4. Phase 3 체크리스트

- [ ] main_window.py
  - [ ] QMainWindow 기본 구조
  - [ ] QStackedWidget 화면 관리
  - [ ] 헤더 & 푸터 구성
  - [ ] DPI 스케일 적용

- [ ] styles/theme.py
  - [ ] 색상 팔레트 정의
  - [ ] 스타일시트 작성
  - [ ] DPI 스케일 함수

- [ ] screens/baseline_screen.py
  - [ ] 레이아웃 구성
  - [ ] 웹캠 프리뷰 (준비)
  - [ ] 카운트다운 UI

- [ ] screens/hub_screen.py
  - [ ] 레이아웃 구성
  - [ ] 버튼 3개

- [ ] screens/settings_screen.py
  - [ ] 좌측 카테고리
  - [ ] 우측 설정값 UI
  - [ ] 설정 저장 로직

- [ ] screens/statistics_screen.py
  - [ ] 레이아웃 구성
  - [ ] 차트 (준비)

- [ ] screens/detection_screen.py
  - [ ] 레이아웃 구성
  - [ ] 상태 표시
  - [ ] 타이머 UI

- [ ] widgets/alert_popup.py
  - [ ] 배너형 & 토스트형

- [ ] widgets/custom_widgets.py
  - [ ] RoundedButton
  - [ ] StateLabel
  - [ ] TimeDisplay

---

## 5. 기술 스택

- **UI 프레임워크**: PyQt6
- **차트**: matplotlib 또는 PyQtGraph
- **레이아웃**: QVBoxLayout, QHBoxLayout, QGridLayout
- **스타일**: QSS (Qt Stylesheet)

---

## 6. 다음 단계

1. Phase 3 계획 검토 및 승인
2. main_window.py + theme.py 기본 구현
3. 6개 화면 순차 구현
4. 커스텀 위젯 구현
5. 전체 레이아웃 테스트
6. Phase 3 결과 보고서 작성

---

**구현 시작 준비 완료.**
