# Phase 4 구현 계획

**작성일**: 2026-04-29  
**단계**: Phase 4 (엔진↔UI 통합)  
**예상 기간**: 25-35시간

---

## 목차

1. [목표 및 범위](#목표-및-범위)
2. [아키텍처 개요](#아키텍처-개요)
3. [상세 구현 계획](#상세-구현-계획)
4. [단계별 작업 분해](#단계별-작업-분해)
5. [신호/슬롯 매핑](#신호슬롯-매핑)
6. [데이터 흐름](#데이터-흐름)
7. [검증 전략](#검증-전략)

---

## 목표 및 범위

### 목표
Phase 3에서 구축한 UI와 Phase 2의 자세 분석 엔진을 연동하여:
1. ✅ 실시간 카메라 입력 처리
2. ✅ 자세 감지 결과를 UI에 표시
3. ✅ 통계 데이터 수집 및 시각화
4. ✅ 실시간 알림 및 상태 업데이트

### 범위
- 카메라 스레드 (별도 스레드에서 프레임 처리)
- 신호/슬롯 기반 스레드-안전 통신
- 실시간 데이터 갱신 (UI 블로킹 없음)
- 세션 데이터 저장 (JSON 기반)

### 제외 사항
- Phase 5 (검증/최적화)는 별도 진행
- 고급 차트 라이브러리 (matplotlib/PyQtGraph)는 placeholder 유지

---

## 아키텍처 개요

### 컴포넌트 다이어그램

```
┌─────────────────────────────────────────────────────┐
│  UI 계층 (PyQt)                                     │
│  ┌────────────┬──────────┬───────────────────────┐ │
│  │ MainWindow │ 5 Screens│ AlertPopup/Widgets    │ │
│  └─────┬──────┴───┬──────┴────────────┬──────────┘ │
└────────┼──────────┼───────────────────┼────────────┘
         │ 신호    │ 신호              │ 신호
         ▼         ▼                   ▼
┌──────────────────────────────────────────────────────┐
│  비즈니스 로직 계층                                  │
│  ┌──────────────────────────────────────────────┐  │
│  │  SessionManager (세션 관리, 데이터 저장)    │  │
│  └────────────────┬─────────────────────────────┘  │
└───────────────────┼────────────────────────────────┘
                    │ 인스턴스 참조
┌───────────────────▼────────────────────────────────┐
│  엔진 계층 (Phase 2 컴포넌트)                      │
│  ┌───────────┬───────────┬────────────────────┐   │
│  │ Landmark  │ Indicator │ Judgment & State   │   │
│  │ Extractor │ Calculator│ Machine            │   │
│  └───────────┴─┬─────────┴────────────────────┘   │
└────────────────┼─────────────────────────────────┘
                 │ 인스턴스 참조
┌────────────────▼─────────────────────────────────┐
│  카메라 스레드                                    │
│  ┌────────────────────────────────────────────┐  │
│  │ CameraWorker (QThread 기반)                │  │
│  │ - 프레임 읽기 (30 FPS)                     │  │
│  │ - 랜드마크 추출                            │  │
│  │ - 신호 방출                                │  │
│  └────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

### 계층별 책임

| 계층 | 책임 | 구성 요소 |
|------|------|---------|
| **UI** | 사용자 입력/출력 | MainWindow, 5 Screens, AlertPopup |
| **비즈니스 로직** | 세션 관리, 데이터 저장 | SessionManager |
| **엔진** | 자세 분석 | LandmarkExtractor, IndicatorCalculator, JudgmentEngine, StateMachine |
| **카메라** | 스레드 기반 프레임 처리 | CameraWorker |

---

## 상세 구현 계획

### 1. CameraWorker (새 파일)

**파일**: `src/core/camera_worker.py`  
**목적**: QThread 기반 카메라 스레드  
**예상 라인**: 200-250줄

#### 클래스 정의

```python
class CameraWorker(QThread):
    """카메라 스레드 워커"""
    
    # 신호
    frame_processed_signal = pyqtSignal(dict)      # 처리된 프레임 데이터
    status_changed_signal = pyqtSignal(str)        # 상태 변경
    error_signal = pyqtSignal(str)                 # 오류 메시지
    
    def __init__(self, landmark_extractor, indicator_calculator, judgment_engine):
        """
        Args:
            landmark_extractor: LandmarkExtractor 인스턴스
            indicator_calculator: IndicatorCalculator 인스턴스
            judgment_engine: JudgmentEngine 인스턴스
        """
        pass
    
    def run(self):
        """스레드 메인 루프"""
        pass
    
    def process_frame(self, frame) -> dict:
        """
        프레임 처리
        
        Returns:
            {
                'frame': numpy array (annotated),
                'landmarks': ExtractedLandmarks,
                'indicators': PostureIndicators,
                'posture_type': str,
                'probability': float,
                'state': PostureState,
                'timestamp': datetime
            }
        """
        pass
    
    def stop_capture(self):
        """캡처 중지"""
        pass
```

#### 주요 메서드

- `run()`: OpenCV 루프 (30 FPS)
- `process_frame()`: 프레임→랜드마크→지표→판정
- `stop_capture()`: 안전한 종료

#### 신호

| 신호 | 데이터 | 목적 |
|------|--------|------|
| `frame_processed_signal` | dict | UI 업데이트 (프리뷰, 상태) |
| `status_changed_signal` | str | 상태 메시지 |
| `error_signal` | str | 오류 처리 |

---

### 2. SessionManager (새 파일)

**파일**: `src/core/session_manager.py`  
**목적**: 세션 데이터 관리 및 저장  
**예상 라인**: 200-250줄

#### 클래스 정의

```python
class SessionManager:
    """세션 데이터 관리자"""
    
    def __init__(self, config: ConfigManager):
        """
        Args:
            config: ConfigManager 싱글톤
        """
        self.config = config
        self.current_session: Optional[SessionData] = None
        self.sessions_history: List[SessionData] = []
    
    def start_session(self):
        """새 세션 시작"""
        pass
    
    def add_frame_data(self, frame_data: dict):
        """
        프레임 데이터 추가
        
        Args:
            frame_data: {
                'posture_type': str,
                'probability': float,
                'state': PostureState,
                'timestamp': datetime
            }
        """
        pass
    
    def end_session(self) -> SessionData:
        """
        세션 종료 및 저장
        
        Returns:
            SessionData (통계 포함)
        """
        pass
    
    def calculate_session_stats(self) -> dict:
        """
        세션 통계 계산
        
        Returns:
            {
                'duration_seconds': int,
                'total_frames': int,
                'posture_distribution': {
                    'forward_head': 15,
                    'recline': 10,
                    'crossed_leg': 5,
                    'chin_rest': 20,
                    'normal': 950
                },
                'good_posture_percentage': 79.6,
                'bad_posture_percentage': 20.4,
                'posture_changes': int,  # 상태 변화 횟수
                'max_bad_duration': int  # 최악 지속 시간 (초)
            }
        """
        pass
    
    def load_recent_sessions(self, count: int = 10) -> List[SessionData]:
        """최근 N개 세션 로드"""
        pass
    
    def save_session_to_file(self, session: SessionData, filepath: str):
        """세션을 JSON으로 저장"""
        pass
    
    def load_session_from_file(self, filepath: str) -> SessionData:
        """JSON에서 세션 로드"""
        pass
```

#### SessionData 데이터클래스

```python
@dataclass
class SessionData:
    """세션 데이터"""
    session_id: str              # UUID
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: int
    total_frames: int
    frame_records: List[FrameRecord]  # 매 프레임 기록
    statistics: dict             # 통계 (calculate_session_stats 결과)
    notes: str = ""              # 사용자 메모
```

#### FrameRecord 데이터클래스

```python
@dataclass
class FrameRecord:
    """프레임별 기록"""
    timestamp: datetime
    posture_type: str           # "normal", "forward_head", etc.
    probability: float          # 0-1
    state: str                  # "NORMAL", "WARNING", "BAD_POSTURE"
    indicators: dict            # PostureIndicators 필드
```

---

### 3. UI 업데이트 로직

#### 3.1 BaselineScreen 업데이트

**파일**: `src/ui/screens/__init__.py`

```python
class BaselineScreen(QWidget):
    """업데이트된 BaselineScreen"""
    
    baseline_captured_signal = pyqtSignal()
    
    def __init__(self, theme_manager: ThemeManager, camera_worker):
        """
        Args:
            theme_manager: ThemeManager
            camera_worker: CameraWorker (카메라 스레드)
        """
        super().__init__()
        self.camera_worker = camera_worker
        self.theme_manager = theme_manager
        
        # camera_worker 신호 연결
        self.camera_worker.frame_processed_signal.connect(
            self._on_frame_processed
        )
        self.setup_ui()
    
    def start_capture(self):
        """촬영 시작"""
        # 기존 5초 카운트다운 → 실제 카메라 시작
        self.camera_worker.start()
    
    def _on_frame_processed(self, frame_data: dict):
        """프레임 처리 완료 시 호출"""
        # frame_data['frame']: 주석 달린 프레임 (numpy)
        # frame_data['timestamp']: 타임스탬프
        # 프리뷰 업데이트
        self._update_preview(frame_data['frame'])
        # 진행바 업데이트
        self._update_progress()
    
    def _update_preview(self, frame: numpy.ndarray):
        """프리뷰 업데이트"""
        # OpenCV → QPixmap 변환
        # QLabel에 표시
        pass
```

#### 3.2 DetectionScreen 업데이트

**파일**: `src/ui/screens/__init__.py`

```python
class DetectionScreen(QWidget):
    """업데이트된 DetectionScreen"""
    
    detection_paused_signal = pyqtSignal()
    detection_stopped_signal = pyqtSignal()
    
    def __init__(self, theme_manager: ThemeManager, camera_worker, session_manager):
        """
        Args:
            theme_manager: ThemeManager
            camera_worker: CameraWorker
            session_manager: SessionManager
        """
        self.camera_worker = camera_worker
        self.session_manager = session_manager
        self.start_time = None
        
        # 신호 연결
        self.camera_worker.frame_processed_signal.connect(
            self._on_frame_processed
        )
        self.setup_ui()
        self._start_timer()  # 사용 시간 업데이트 타이머
    
    def _on_frame_processed(self, frame_data: dict):
        """프레임 처리 완료 시 호출"""
        # 프리뷰 업데이트
        self._update_preview(frame_data['frame'])
        
        # 자세 상태 업데이트
        state = frame_data['state']
        posture_type = frame_data['posture_type']
        probability = frame_data['probability']
        self._update_posture_status(state, posture_type, probability)
        
        # 세션 데이터 추가
        self.session_manager.add_frame_data(frame_data)
        
        # 상태 변화 시 AlertPopup 표시
        if self._should_show_alert(state, posture_type):
            self._show_alert(posture_type)
    
    def _update_posture_status(self, state: str, posture_type: str, probability: float):
        """자세 상태 업데이트"""
        # 상태 라벨 색상 변경
        # - NORMAL: 초록
        # - WARNING: 노랑
        # - BAD_POSTURE: 빨강
        pass
    
    def _update_preview(self, frame: numpy.ndarray):
        """프리뷰 업데이트"""
        pass
    
    def _show_alert(self, posture_type: str):
        """알림 표시"""
        pass
    
    def _start_timer(self):
        """사용 시간 타이머 시작"""
        pass
    
    def stop_detection(self):
        """감지 종료"""
        # 세션 종료
        session_stats = self.session_manager.end_session()
        # StatisticsScreen에 데이터 전달
        # HubScreen으로 복귀
        pass
```

#### 3.3 StatisticsScreen 업데이트

**파일**: `src/ui/screens/__init__.py`

```python
class StatisticsScreen(QWidget):
    """업데이트된 StatisticsScreen"""
    
    def __init__(self, theme_manager: ThemeManager, session_manager):
        """
        Args:
            session_manager: SessionManager
        """
        self.session_manager = session_manager
        self.setup_ui()
        self._load_statistics()
    
    def _load_statistics(self):
        """최근 10개 세션 통계 로드"""
        recent_sessions = self.session_manager.load_recent_sessions(10)
        
        # 데이터 준비
        dates = [s.start_time.strftime("%m-%d") for s in recent_sessions]
        percentages = [s.statistics['good_posture_percentage'] for s in recent_sessions]
        
        # 차트 그리기 (matplotlib/PyQtGraph)
        self._draw_chart(dates, percentages)
    
    def _draw_chart(self, dates: list, percentages: list):
        """바 차트 그리기"""
        # matplotlib.figure.Figure 또는 PyQtGraph PlotWidget 사용
        pass
```

---

### 4. 메인 애플리케이션 업데이트

**파일**: `src/ui/app.py`

```python
class BarorokApp:
    """업데이트된 BarorokApp"""
    
    def __init__(self):
        # 기존 초기화...
        
        # 엔진 컴포넌트 초기화
        self.landmark_extractor = LandmarkExtractor(self.config)
        self.indicator_calculator = IndicatorCalculator(self.config)
        self.baseline_manager = BaselineManager(self.config)
        self.judgment_engine = JudgmentEngine(self.config, self.baseline_manager)
        self.state_machine = StateMachine(self.config)
        
        # 비즈니스 로직 초기화
        self.session_manager = SessionManager(self.config)
        
        # 카메라 워커 초기화
        self.camera_worker = CameraWorker(
            self.landmark_extractor,
            self.indicator_calculator,
            self.judgment_engine
        )
        
        # UI 생성 (카메라 워커 전달)
        self._setup_screens()
    
    def _setup_screens(self):
        """화면 생성 시 필요한 의존성 주입"""
        self.baseline_screen = BaselineScreen(
            self.theme_manager,
            self.camera_worker
        )
        self.detection_screen = DetectionScreen(
            self.theme_manager,
            self.camera_worker,
            self.session_manager
        )
        self.statistics_screen = StatisticsScreen(
            self.theme_manager,
            self.session_manager
        )
        # ... 기타 화면
```

---

## 단계별 작업 분해

### Task 1: CameraWorker 구현 (4-5시간)
- [ ] 파일 생성: `src/core/camera_worker.py`
- [ ] QThread 상속 클래스 정의
- [ ] `run()` 메서드 (30 FPS 루프)
- [ ] `process_frame()` 메서드
- [ ] 신호 정의 및 방출
- [ ] 오류 처리 (카메라 미사용 등)
- [ ] 테스트 (프레임 처리 확인)

### Task 2: SessionManager 구현 (3-4시간)
- [ ] 파일 생성: `src/core/session_manager.py`
- [ ] SessionData, FrameRecord 데이터클래스
- [ ] 세션 시작/종료 로직
- [ ] 통계 계산 (good_posture_percentage 등)
- [ ] JSON 저장/로드
- [ ] 최근 세션 로드 (최대 10개)
- [ ] 테스트 (세션 데이터 저장 확인)

### Task 3: BaselineScreen 통합 (3-4시간)
- [ ] 카메라 워커 신호 연결
- [ ] 프리뷰 업데이트 (OpenCV → QPixmap)
- [ ] 진행바 업데이트
- [ ] 촬영 완료 신호 처리
- [ ] 오류 메시지 표시
- [ ] 테스트

### Task 4: DetectionScreen 통합 (5-6시간)
- [ ] 카메라 워커 신호 연결
- [ ] 프리뷰 업데이트
- [ ] 자세 상태 업데이트 (색상 변경)
- [ ] 사용 시간 타이머 (00:00:00 형식)
- [ ] 알림 팝업 표시 (거북목, 기댄자세 등)
- [ ] 세션 데이터 저장
- [ ] 종료 버튼 처리
- [ ] 테스트

### Task 5: StatisticsScreen 통합 (4-5시간)
- [ ] 세션 데이터 로드
- [ ] 차트 그리기 (matplotlib 또는 PyQtGraph)
- [ ] 평균 계산 및 표시
- [ ] 테스트

### Task 6: 메인 애플리케이션 통합 (2-3시간)
- [ ] 엔진 컴포넌트 초기화
- [ ] SessionManager 초기화
- [ ] CameraWorker 초기화
- [ ] 의존성 주입 (UI 생성 시)
- [ ] 신호 연결 (전체)
- [ ] 통합 테스트

### Task 7: 검증 및 디버깅 (2-3시간)
- [ ] 프레임 처리 속도 확인 (30 FPS 유지)
- [ ] UI 반응성 확인 (블로킹 없음)
- [ ] 메모리 누수 확인
- [ ] 오류 처리 테스트
- [ ] 성능 최적화

---

## 신호/슬롯 매핑

### CameraWorker → UI 신호

| 신호 | 수신처 | 액션 |
|------|--------|------|
| `frame_processed_signal` | BaselineScreen | 프리뷰 업데이트 |
| `frame_processed_signal` | DetectionScreen | 프리뷰 + 상태 업데이트 |
| `status_changed_signal` | MainWindow | 상태바 업데이트 (향후) |
| `error_signal` | MainWindow | 오류 팝업 |

### UI → Engine 신호

| 신호 | 동작 |
|------|------|
| BaselineScreen.baseline_captured_signal | JudgmentEngine에 baseline 설정 |
| DetectionScreen.detection_stopped_signal | SessionManager.end_session() |
| HubScreen.start_detection_signal | CameraWorker.start() |

---

## 데이터 흐름

### 감지 시작 → 종료 흐름

```
HubScreen
  │
  └─ "감지 시작" 버튼
       │
       ▼
DetectionScreen.setup_ui()
  │
  └─ CameraWorker.start() [QThread 시작]
       │
       ├─ 30ms마다 frame_processed_signal 방출
       │
       ▼
DetectionScreen._on_frame_processed()
  │
  ├─ 프리뷰 업데이트 (OpenCV → QPixmap)
  ├─ 자세 상태 업데이트 (색상)
  ├─ SessionManager.add_frame_data()
  └─ 필요시 AlertPopup 표시
       │
       ├─ "일시정지" 버튼 → CameraWorker.pause()
       │
       └─ "종료" 버튼
            │
            ▼
       SessionManager.end_session()
            │
            ├─ 통계 계산
            ├─ JSON 저장 (data/sessions/)
            └─ StatisticsScreen에 데이터 전달
                 │
                 ▼
            StatisticsScreen.show()
                 │
                 └─ 차트 그리기
```

---

## 검증 전략

### 1. 단위 테스트 (각 Task마다)
- CameraWorker: 프레임 처리 속도 확인
- SessionManager: 데이터 저장/로드 확인
- 화면: 신호 연결 확인

### 2. 통합 테스트
- 전체 플로우 (시작 → 감지 → 종료)
- UI 반응성 (프레임 처리 중 UI 블로킹 없음)
- 메모리 누수 확인

### 3. 성능 테스트
- FPS 유지 (30 FPS)
- CPU 사용률
- 메모리 사용률

### 4. 오류 처리 테스트
- 카메라 미연결
- 불완전한 프레임
- 디스크 저장 실패

---

## 예상 시간 표

| Task | 예상 시간 | 우선순위 |
|------|----------|---------|
| Task 1: CameraWorker | 4-5시간 | ⭐⭐⭐ |
| Task 2: SessionManager | 3-4시간 | ⭐⭐⭐ |
| Task 3: BaselineScreen 통합 | 3-4시간 | ⭐⭐ |
| Task 4: DetectionScreen 통합 | 5-6시간 | ⭐⭐⭐ |
| Task 5: StatisticsScreen 통합 | 4-5시간 | ⭐⭐ |
| Task 6: 메인앱 통합 | 2-3시간 | ⭐⭐⭐ |
| Task 7: 검증 & 디버깅 | 2-3시간 | ⭐⭐ |
| **합계** | **25-35시간** | |

---

## 다음 단계

1. ✅ 이 계획 검토 및 확정
2. ⏳ Task 1 (CameraWorker) 구현 시작
3. ⏳ Task 2 (SessionManager) 구현
4. ⏳ UI 통합 (Tasks 3-5)
5. ⏳ 검증 및 최적화 (Task 7)

---

**작성**: GitHub Copilot  
**상태**: 구현 준비 완료
