# Phase 2: 자세 분석 엔진 - 구현 계획서

**기능**: MediaPipe 기반 랜드마크 추출, 자세 지표 계산, baseline 관리, 판정 로직, 상태 머신  
**예상 기간**: 8-12시간  
**예상 완료일**: 2026-04-30 (집중 구현 시)

---

## 1. 개요

### 목표
- 웹캠 프레임에서 MediaPipe를 사용해 얼굴, 어깨, 손 랜드마크 추출
- 추출된 랜드마크로부터 자세 관련 지표 계산 (거리, 비율, 각도)
- 초기 바른자세(baseline) 수집 및 저장
- baseline 대비 변화량 기반 자세 판정
- 프레임 점수 및 상태 머신을 통한 확정 판정

### 핵심 특징
- **MediaPipe task 기반**: holistic, solutions 미사용
- **JSON 기반 임계값**: 코드에 하드코딩하지 않음
- **노이즈 필터링**: 이동평균, 중앙값 필터 적용
- **시간 누적 조건**: 단일 프레임이 아닌 지속시간 기준
- **4가지 자세 감지**: 기댄, 거북목, 다리 꼰, 턱 괸

---

## 2. 구현 모듈별 상세 계획

### 2.1 landmark_extractor.py
**목적**: MediaPipe에서 랜드마크 추출

#### 클래스: `LandmarkExtractor`

**초기화**
```python
class LandmarkExtractor:
    def __init__(self, model_path: str = None):
        """
        Args:
            model_path: MediaPipe task 파일 경로 (.task)
                        None이면 기본 위치에서 자동 검색
        """
```

**메서드**

1. `initialize_models()`
   - 필요한 MediaPipe 모델 로드 (.task 파일)
   - 모델 종류: pose_landmarker.task, face_landmarker.task, hand_landmarker.task
   - 각 모델별 신뢰도 임계값 설정
   - 예외: 모델 파일 없으면 FileNotFoundError 발생

2. `extract_landmarks(frame: np.ndarray) -> dict`
   - 입력: OpenCV 프레임 (BGR)
   - 반환: 
     ```python
     {
         'pose': {
             'landmarks': [(x, y), ...],  # 33개 포즈 랜드마크
             'confidences': [0.9, ...],
             'timestamp_ms': 1234567
         },
         'face': {
             'landmarks': [(x, y, z), ...],  # 468개 얼굴 랜드마크
             'confidences': [0.95, ...],
             'timestamp_ms': 1234567
         },
         'hands': {
             'landmarks': [[(x, y, z), ...], ...],  # 2개 손 × 21개 랜드마크
             'handedness': ['Right', 'Left'],
             'confidences': [[0.9, ...], ...],
             'timestamp_ms': 1234567
         }
     }
     ```
   - 에러 처리: 프레임 없음, 모델 로드 실패 등

3. `get_relevant_landmarks(frame: np.ndarray) -> dict`
   - 자세 판정에 필요한 랜드마크만 추출
   - 필요한 포인트:
     - 얼굴: 코(30), 양쪽 눈(1,4), 양쪽 광대(152,378), 턱(199,427)
     - 어깨: 왼쪽(11), 오른쪽(12)
     - 손: 손가락 팁(손별 4,8,12,16,20)
   - 신뢰도 필터링: threshold 0.5 이상만 반환
   - 반환:
     ```python
     {
         'face_center': (x, y),
         'left_eye': (x, y),
         'right_eye': (x, y),
         'left_cheek': (x, y),
         'right_cheek': (x, y),
         'chin_points': [(x, y), ...],
         'left_shoulder': (x, y),
         'right_shoulder': (x, y),
         'left_hand_tips': [(x, y, z), ...],
         'right_hand_tips': [(x, y, z), ...],
         'confidences': {...}
     }
     ```

4. `normalize_landmarks(landmarks: dict, frame_width: int, frame_height: int) -> dict`
   - 랜드마크 좌표 정규화 (0~1 범위)
   - 용도: 카메라 거리/각도 변화에 대한 안정성 향상

**테스트 포인트**
- 모델 로드 성공 여부
- 프레임에서 랜드마크 추출 가능 여부
- 신뢰도 필터링 적용 확인
- 정규화 계산 검증

---

### 2.2 indicator_calculator.py
**목적**: 랜드마크에서 자세 지표 계산

#### 클래스: `IndicatorCalculator`

**초기화**
```python
class IndicatorCalculator:
    def __init__(self):
        """자세 지표 계산기"""
```

**메서드**

1. `calculate_cheek_distance(left_cheek: tuple, right_cheek: tuple) -> float`
   - 양쪽 광대뼈 간 거리
   - 정규화된 좌표 사용
   - 반환: 0~1 범위의 거리값

2. `calculate_eye_distance(left_eye: tuple, right_eye: tuple) -> float`
   - 양쪽 눈 간 거리
   - 반환: 정규화된 거리값

3. `calculate_face_shoulder_ratio(cheek_distance: float, shoulder_width: float) -> float`
   - 얼굴 너비 / 어깨 너비
   - 비율 증가: 머리가 카메라에 가까워짐 (거북목)
   - 비율 감소: 머리가 카메라에서 멀어짐 (누운 자세)
   - 반환: 0~2 범위의 비율값

4. `calculate_shoulder_width(left_shoulder: tuple, right_shoulder: tuple) -> float`
   - 양쪽 어깨 간 거리
   - 반환: 정규화된 거리값

5. `calculate_shoulder_tilt_degree(left_shoulder: tuple, right_shoulder: tuple) -> float`
   - 좌우 어깨 높이 차이 (도 단위)
   - 양수: 오른쪽 어깨가 높음
   - 음수: 왼쪽 어깨가 높음
   - 절댓값 클수록 다리 꼬거나 한쪽 팔 사용 중
   - 반환: -30~30 도

6. `calculate_neck_offset(nose: tuple, shoulder_center: tuple) -> float`
   - 코와 어깨 중심의 수평 거리
   - 큰 값: 머리가 어깨 중심선에서 벗어남
   - 반환: 정규화된 거리값

7. `calculate_eye_line_tilt(left_eye: tuple, right_eye: tuple) -> float`
   - 눈 수평선과 프레임 수평선의 각도 차이
   - 큰 값: 머리가 기울어짐 (턱 괸 자세 가능성)
   - 반환: -45~45 도

8. `calculate_chin_occlusion(chin_points: list, hand_tips: dict) -> float`
   - 손과 턱의 겹침 정도
   - 반환: 0~1 (0=겹침없음, 1=완전겹침)

9. `calculate_hand_near_face(hand_tips: dict, face_center: tuple, threshold: float = 0.15) -> bool`
   - 손이 얼굴 근처에 있는지 판단
   - threshold: 얼굴 크기 대비 거리 비율
   - 반환: True/False

**저장 구조**
```python
class PostureIndicators:
    """자세 지표 데이터"""
    cheek_distance: float
    eye_distance: float
    face_shoulder_ratio: float
    shoulder_width: float
    shoulder_tilt_deg: float
    neck_offset: float
    eye_line_tilt: float
    chin_occlusion: float
    hand_near_face: bool
    timestamp: float
```

**테스트 포인트**
- 각 지표 계산 결과 범위 검증
- 정규화 적용 확인
- 각도 계산 정확성
- 신뢰도 필터링

---

### 2.3 baseline_manager.py
**목적**: baseline 수집, 저장, 비교

#### 클래스: `BaselineManager`

**초기화**
```python
class BaselineManager:
    def __init__(self, config: ConfigManager):
        """
        Args:
            config: 설정 관리자
        """
        self.baseline_metrics = {}
        self.collection_frames = []
        self.is_collecting = False
```

**메서드**

1. `start_baseline_collection()`
   - baseline 수집 시작
   - `is_collecting = True`
   - `collection_frames = []` 초기화
   - 로깅: "baseline 수집 시작"

2. `add_frame_to_collection(indicators: PostureIndicators)`
   - baseline 수집 중 프레임 추가
   - 조건: `is_collecting == True`
   - 지표 저장: collection_frames에 append

3. `finish_baseline_collection(fps: int = 30) -> bool`
   - baseline 수집 완료
   - 수집 시간 검증: `config.get_baseline_config()['capture']['duration_seconds']` (기본 5초)
   - 필요 프레임 수: 5초 × 30FPS = 150프레임
   - 평균/중앙값 계산:
     ```python
     self.baseline_metrics = {
         'cheek_distance': np.median([f.cheek_distance for f in self.collection_frames]),
         'eye_distance': np.median([f.eye_distance for f in self.collection_frames]),
         'face_shoulder_ratio': np.median([f.face_shoulder_ratio for f in self.collection_frames]),
         'shoulder_width': np.median([f.shoulder_width for f in self.collection_frames]),
         ...
     }
     ```
   - 저장: JSON 파일 (예: data/baseline.json)
   - 반환: 성공 여부

4. `save_baseline_to_file(filepath: str = "data/baseline.json")`
   - baseline 메트릭을 JSON으로 저장
   - 디렉토리 자동 생성
   - 타임스탬프 포함

5. `load_baseline_from_file(filepath: str = "data/baseline.json") -> bool`
   - 저장된 baseline 로드
   - 파일 없으면 False 반환
   - baseline_metrics 업데이트

6. `get_baseline_metrics() -> dict`
   - 현재 baseline 메트릭 반환

7. `calculate_change_percentage(current_value: float, metric_name: str) -> float`
   - baseline 대비 변화율 (%) 계산
   - 예: cheek_distance가 baseline보다 10% 작으면 -10 반환
   - 공식: `(current - baseline) / baseline × 100`
   - 에러 처리: baseline이 0이면 0 반환

8. `is_baseline_valid() -> bool`
   - baseline이 충분한 데이터로 설정되었는지 확인
   - 모든 필수 지표가 있는지 검증

**저장 포맷**
```json
{
  "timestamp": "2026-04-29T13:00:00",
  "collection_duration_seconds": 5,
  "frame_count": 150,
  "metrics": {
    "cheek_distance": 0.35,
    "eye_distance": 0.18,
    "face_shoulder_ratio": 0.55,
    "shoulder_width": 0.42,
    "shoulder_tilt_deg": 2.5,
    "neck_offset": 0.05,
    "eye_line_tilt": 1.2,
    ...
  }
}
```

**테스트 포인트**
- baseline 수집 시간 검증 (5초)
- 평균/중앙값 계산 정확성
- JSON 저장/로드
- 변화율 계산

---

### 2.4 judgment_engine.py
**목적**: 자세 판정 로직 구현

#### 클래스: `JudgmentEngine`

**초기화**
```python
class JudgmentEngine:
    def __init__(self, config: ConfigManager, baseline_manager: BaselineManager):
        """
        Args:
            config: 설정 관리자
            baseline_manager: baseline 관리자
        """
        self.config = config
        self.baseline_manager = baseline_manager
        self.posture_history = {}  # 자세별 프레임 누적
```

**메서드**

1. `judge_single_frame(indicators: PostureIndicators) -> dict`
   - 단일 프레임에 대한 자세 판정
   - 반환: 
     ```python
     {
         'postures': {
             'forward_head': {'likelihood': 0.75, 'triggered': True},
             'recline': {'likelihood': 0.2, 'triggered': False},
             'crossed_leg_estimated': {'likelihood': 0.3, 'triggered': False},
             'chin_rest_estimated': {'likelihood': 0.1, 'triggered': False}
         },
         'dominant_posture': 'forward_head',  # 가장 확률이 높은 자세
         'timestamp': 1234567
     }
     ```

#### 판정 로직 (각 자세별)

**A. forward_head (거북목)**

```python
def _judge_forward_head(self, indicators: PostureIndicators) -> dict:
    """
    조건:
    - cheek_distance 증가 (얼굴이 카메라에 가까워짐)
    - face_shoulder_ratio 증가
    
    계산식:
    - cheek_distance_change = (current - baseline) / baseline × 100
    - face_ratio_change = (current - baseline) / baseline × 100
    
    임계값 (JSON에서 로드):
    - cheek_distance_threshold_percent: 8%
    - face_shoulder_ratio_threshold_percent: 15%
    
    확률 계산:
    score = 0.6 * normalize(cheek_distance_change) + 0.4 * normalize(face_ratio_change)
    """
    criteria = self.config.get_posture_type_config('forward_head')
    cheek_change = self.baseline_manager.calculate_change_percentage(
        indicators.cheek_distance, 'cheek_distance'
    )
    ratio_change = self.baseline_manager.calculate_change_percentage(
        indicators.face_shoulder_ratio, 'face_shoulder_ratio'
    )
    
    # 임계값 확인
    cheek_threshold = criteria['primary_conditions']['cheek_distance_baseline_change_percent']['threshold_percent']
    ratio_threshold = criteria['primary_conditions']['face_shoulder_ratio_baseline_change_percent']['threshold_percent']
    
    cheek_triggered = cheek_change >= cheek_threshold
    ratio_triggered = ratio_change >= ratio_threshold
    
    # 확률 계산
    cheek_score = self._normalize_score(cheek_change / cheek_threshold, 0, 2)  # 0~2배 범위
    ratio_score = self._normalize_score(ratio_change / ratio_threshold, 0, 2)
    
    likelihood = 0.6 * cheek_score + 0.4 * ratio_score
    triggered = cheek_triggered and ratio_triggered  # 둘 다 만족해야 발동
    
    return {
        'likelihood': likelihood,
        'triggered': triggered,
        'details': {
            'cheek_change_percent': cheek_change,
            'ratio_change_percent': ratio_change,
            'cheek_threshold': cheek_threshold,
            'ratio_threshold': ratio_threshold
        }
    }
```

**B. recline (기댄 자세)**

```python
def _judge_recline(self, indicators: PostureIndicators) -> dict:
    """
    조건:
    - cheek_distance 감소 (얼굴이 카메라에서 멀어짐)
    - face_shoulder_ratio 감소
    
    임계값 (JSON에서 로드):
    - cheek_distance_threshold_percent: -10% (음수)
    - 지속시간: 2초
    """
    criteria = self.config.get_posture_type_config('recline')
    cheek_change = self.baseline_manager.calculate_change_percentage(
        indicators.cheek_distance, 'cheek_distance'
    )
    
    cheek_threshold = criteria['primary_conditions']['cheek_distance_baseline_change_percent']['threshold_percent']
    cheek_triggered = cheek_change <= -cheek_threshold  # 음수이므로 <= 사용
    
    cheek_score = self._normalize_score(abs(cheek_change) / cheek_threshold, 0, 2)
    likelihood = cheek_score
    triggered = cheek_triggered
    
    return {
        'likelihood': likelihood,
        'triggered': triggered,
        'details': {
            'cheek_change_percent': cheek_change,
            'threshold': cheek_threshold
        }
    }
```

**C. crossed_leg_estimated (다리 꼰 자세 추정)**

```python
def _judge_crossed_leg_estimated(self, indicators: PostureIndicators) -> dict:
    """
    조건:
    - abs(shoulder_tilt_deg) > 임계값
    - 반복 창에서 여러 번 나타남
    
    임계값 (JSON에서 로드):
    - shoulder_tilt_threshold: 6도
    - repeat_window_seconds: 10초
    - sustain_seconds: 3초
    """
    criteria = self.config.get_posture_type_config('crossed_leg_estimated')
    shoulder_tilt = abs(indicators.shoulder_tilt_deg)
    
    threshold = criteria['primary_conditions']['abs_shoulder_tilt_deg']['threshold']
    shoulder_triggered = shoulder_tilt > threshold
    
    # 점수: 절댓값이 클수록 높음
    tilt_score = self._normalize_score(shoulder_tilt / threshold, 0, 2)
    likelihood = tilt_score
    triggered = shoulder_triggered
    
    return {
        'likelihood': likelihood,
        'triggered': triggered,
        'details': {
            'shoulder_tilt_deg': indicators.shoulder_tilt_deg,
            'threshold': threshold
        }
    }
```

**D. chin_rest_estimated (턱 괸 자세 추정)**

```python
def _judge_chin_rest_estimated(self, indicators: PostureIndicators) -> dict:
    """
    조건:
    - eye_line_tilt >= 임계값
    - shoulder_tilt >= 임계값
    - hand_near_face 또는 chin_occlusion
    
    임계값 (JSON에서 로드):
    - eye_line_tilt_threshold: 8도
    - shoulder_tilt_threshold: 6도
    """
    criteria = self.config.get_posture_type_config('chin_rest_estimated')
    
    eye_threshold = criteria['primary_conditions']['eye_line_tilt_deg']['threshold']
    shoulder_threshold = criteria['primary_conditions']['shoulder_tilt_deg']['threshold']
    
    eye_triggered = abs(indicators.eye_line_tilt) >= eye_threshold
    shoulder_triggered = abs(indicators.shoulder_tilt_deg) >= shoulder_threshold
    hand_triggered = indicators.hand_near_face or indicators.chin_occlusion > 0.2
    
    # 점수
    eye_score = self._normalize_score(abs(indicators.eye_line_tilt) / eye_threshold, 0, 2)
    shoulder_score = self._normalize_score(abs(indicators.shoulder_tilt_deg) / shoulder_threshold, 0, 2)
    hand_score = 1.0 if indicators.hand_near_face else indicators.chin_occlusion / 0.25
    
    likelihood = 0.35 * eye_score + 0.2 * shoulder_score + 0.45 * hand_score
    triggered = (eye_triggered or shoulder_triggered) and hand_triggered
    
    return {
        'likelihood': likelihood,
        'triggered': triggered,
        'details': {
            'eye_line_tilt': indicators.eye_line_tilt,
            'shoulder_tilt': indicators.shoulder_tilt_deg,
            'hand_near_face': indicators.hand_near_face,
            'chin_occlusion': indicators.chin_occlusion
        }
    }
```

2. `accumulate_frame(posture_judgments: dict, fps: int = 30)`
   - 프레임 판정 결과 누적
   - 각 자세별로 연속 프레임 카운트
   - 예:
     ```python
     self.posture_history['forward_head'] += 1  # triggered되면 증가
     self.posture_history['crossed_leg_estimated'] = 0  # 아니면 리셋
     ```

3. `get_confirmed_posture(fps: int = 30) -> Optional[str]`
   - 지속시간 조건을 만족한 자세 반환
   - 예: forward_head의 지속시간이 2초 이상이면 확정
   - 공식: `frame_count >= (sustain_seconds × fps)`
   - 우선순위: 지속시간이 가장 긴 자세 반환
   - 반환: 'forward_head', 'recline', 'crossed_leg_estimated', 'chin_rest_estimated', None

4. `_normalize_score(value: float, min_val: float, max_val: float) -> float`
   - 값을 0~1 범위로 정규화
   - np.clip 사용

**저장 포맷**
```python
class PostureJudgment:
    """단일 프레임 판정 결과"""
    forward_head_likelihood: float  # 0~1
    forward_head_triggered: bool
    recline_likelihood: float
    recline_triggered: bool
    crossed_leg_likelihood: float
    crossed_leg_triggered: bool
    chin_rest_likelihood: float
    chin_rest_triggered: bool
    dominant_posture: Optional[str]
    timestamp: float
```

**테스트 포인트**
- 각 자세별 임계값 적용 확인
- 확률 계산 범위 (0~1)
- 지속시간 누적
- 확정 판정 로직

---

### 2.5 state_machine.py
**목적**: 상태 관리 및 전이

#### 클래스: `PostureState` (Enum)

```python
class PostureState(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    BAD_POSTURE = "bad_posture"
```

#### 클래스: `StateMachine`

**초기화**
```python
class StateMachine:
    def __init__(self, config: ConfigManager):
        """
        Args:
            config: 설정 관리자
        """
        self.current_state = PostureState.NORMAL
        self.state_enter_time = time.time()
        self.config = config
        self.state_transition_callbacks = []
```

**메서드**

1. `update_state(confirmed_posture: Optional[str]) -> PostureState`
   - 상태 전이 로직
   - 입력: 확정된 자세 (또는 None)
   - 상태 전이 규칙 (JSON에서 로드):
     ```
     NORMAL:
       - confirmed_posture가 None → NORMAL 유지
       - confirmed_posture가 있음 → WARNING 전이
     
     WARNING:
       - confirmed_posture가 None → NORMAL 전이
       - confirmed_posture가 있음 → BAD_POSTURE 전이 (5초 이상 지속 시)
     
     BAD_POSTURE:
       - confirmed_posture가 None → WARNING 전이 (1초 후)
       - confirmed_posture가 있음 → BAD_POSTURE 유지
     ```
   - 반환: 현재 상태

2. `register_state_change_callback(callback: Callable[[PostureState], None])`
   - 상태 변경 시 실행할 콜백 등록
   - UI 업데이트 등에 사용

3. `trigger_state_change_event(new_state: PostureState)`
   - 상태 변경 이벤트 발생
   - 타임스탬프 기록
   - 등록된 모든 콜백 실행

4. `get_time_in_current_state() -> float`
   - 현재 상태에서 경과한 시간 (초)
   - 반환: time.time() - self.state_enter_time

5. `reset()`
   - 상태를 NORMAL으로 초기화
   - 타임스탬프 리셋

**저장 포맷**
```python
class StateTransitionEvent:
    """상태 전이 이벤트"""
    from_state: PostureState
    to_state: PostureState
    confirmed_posture: Optional[str]
    timestamp: float
    time_in_previous_state: float
```

**테스트 포인트**
- 상태 전이 규칙 검증
- 콜백 호출 확인
- 타이밍 조건 검증 (예: 5초 이상)

---

## 3. 통합 구조

```
frame (OpenCV)
  ↓
LandmarkExtractor.extract_landmarks()
  ↓ landmarks
IndicatorCalculator.calculate_*()
  ↓ PostureIndicators
┌─────────────────────┐
│ baseline 수집 중?    │
│ (첫 5초)           │
└─────────────────────┘
  Yes → BaselineManager.add_frame_to_collection()
  No  ↓
JudgmentEngine.judge_single_frame()
  ↓ PostureJudgment (likelihood, triggered)
JudgmentEngine.accumulate_frame()
  ↓ (시간 누적)
JudgmentEngine.get_confirmed_posture()
  ↓ confirmed_posture (또는 None)
StateMachine.update_state()
  ↓ PostureState
[이벤트 발생] → UI 업데이트, 알림 등
```

---

## 4. 에러 처리 및 안정성

### 예외 시나리오
1. **랜드마크 부재**: 신뢰도 필터링으로 처리 (default=0)
2. **baseline 부재**: 첫 5초 동안 자동 수집 후 진행
3. **계산 오버플로우**: np.clip으로 범위 제한
4. **프레임 드롭**: 타임스탬프로 추적, 보간 가능

### 로깅
- 각 단계별 로깅 (DEBUG 레벨)
- 자세 판정 시 상세 로깅 (INFO 레벨)
- 에러는 ERROR 레벨

---

## 5. Phase 2 체크리스트

- [ ] landmark_extractor.py
  - [ ] 모델 로드 로직
  - [ ] 랜드마크 추출 및 필터링
  - [ ] 정규화
  
- [ ] indicator_calculator.py
  - [ ] 7개 지표 계산 함수
  - [ ] PostureIndicators 클래스
  - [ ] 범위 검증
  
- [ ] baseline_manager.py
  - [ ] 수집, 저장, 로드
  - [ ] 변화율 계산
  - [ ] JSON 포맷
  
- [ ] judgment_engine.py
  - [ ] 4가지 자세 판정 로직
  - [ ] 확률 계산
  - [ ] 지속시간 누적
  
- [ ] state_machine.py
  - [ ] 상태 전이 규칙
  - [ ] 콜백 시스템
  - [ ] 타이밍 조건

- [ ] 통합 테스트
  - [ ] 각 모듈별 단위 테스트
  - [ ] 모듈 간 데이터 흐름 검증
  - [ ] 성능 측정 (FPS 확인)

---

## 6. 주의사항

1. **JSON 기반 설정**: 모든 임계값은 JSON에서 로드 (코드에 하드코딩 X)
2. **노이즈 필터**: helpers.py의 이동평균, 중앙값 필터 활용
3. **시간 누적**: 단일 프레임이 아닌 연속 프레임 조건 적용
4. **정규화**: 카메라 거리/각도 변화에 대한 안정성
5. **MediaPipe**: task 파일만 사용, holistic/solutions 금지

---

## 7. 다음 단계

1. 본 계획 검토 및 확인
2. landmark_extractor.py 구현
3. indicator_calculator.py 구현
4. baseline_manager.py 구현
5. judgment_engine.py 구현
6. state_machine.py 구현
7. 통합 테스트 및 검증
8. Phase 2 결과 보고서 작성

---

**구현 준비 완료. 이 계획으로 진행하시겠습니까?**
