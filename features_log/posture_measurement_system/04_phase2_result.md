# Phase 2 구현 결과 보고서

**작성일**: 2026-04-29  
**완료 상태**: ✓ 완료  
**예상 기간**: 8-12시간 → **실제 기간**: 약 2시간

---

## 1. 완료된 작업

### 1.1 landmark_extractor.py
**목적**: MediaPipe 랜드마크 추출

**주요 클래스**: `LandmarkExtractor`

**기능**:
- MediaPipe task 파일 기반 모델 로드 (pose, face, hand)
- 웹캠 프레임에서 33개 포즈, 468개 얼굴, 21개×2 손 랜드마크 추출
- 자동 신뢰도 필터링 (threshold: 0.5)
- 정규화된 좌표 변환 (0~1 범위)

**핵심 메서드**:
- `initialize_models()`: 3개 MediaPipe 모델 로드
- `extract_landmarks(frame)`: 프레임에서 전체 랜드마크 추출
- `get_relevant_landmarks(extracted, width, height)`: 자세 판정 필요 랜드마크만 추출
- `normalize_landmarks(landmarks, width, height)`: 좌표 정규화

**데이터 구조**:
- `LandmarkData`: 랜드마크 좌표 + 신뢰도 + 타임스탐프
- `ExtractedLandmarks`: pose + face + hands 통합

**특징**:
- 에러 처리: 모델 로드 실패 시 경고만 출력 (프로세스 계속)
- 로깅: 각 모델 로드 성공/실패 기록
- 유연성: 신뢰도 임계값 설정 가능

---

### 1.2 indicator_calculator.py
**목적**: 자세 관련 지표 계산

**주요 클래스**: `IndicatorCalculator`

**계산 지표** (9개):
1. `cheek_distance`: 양쪽 광대 간 거리 (0~1)
2. `eye_distance`: 양쪽 눈 간 거리 (0~1)
3. `face_shoulder_ratio`: 얼굴-어깨 비율 (0~2)
4. `shoulder_width`: 양쪽 어깨 간 거리 (0~1)
5. `shoulder_tilt_deg`: 어깨 기울기 (-90~90°)
6. `neck_offset`: 목-어깨 정렬 오차 (0~1)
7. `eye_line_tilt`: 눈 수평선 기울기 (-90~90°)
8. `chin_occlusion`: 턱 가림 정도 (0~1)
9. `hand_near_face`: 손-얼굴 근접 여부 (bool)

**핵심 메서드**:
- `calculate_*()`: 각 지표별 계산 함수 (8개)
- `calculate_all_indicators(landmarks)`: 모든 지표 한 번에 계산
- 필수 랜드마크 확인 및 None 반환 (부재 시)

**데이터 구조**:
- `PostureIndicators`: 모든 지표를 담는 dataclass

**특징**:
- GeometryHelper 활용: 거리, 각도 계산
- 정규화: 모든 값을 범위 내로 클립
- 에러 처리: None 값 안전하게 처리

---

### 1.3 baseline_manager.py
**목적**: Baseline 수집 및 관리

**주요 클래스**: `BaselineManager`

**기능**:
- 바른자세 초기 수집 (5초, 150프레임 @30FPS)
- 평균/중앙값 계산 (외이값 제거)
- JSON 저장/로드
- Baseline 대비 변화율 계산

**핵심 메서드**:
- `start_baseline_collection()`: 수집 시작
- `add_frame_to_collection()`: 프레임 누적
- `finish_baseline_collection()`: 수집 완료 & 계산
- `save_baseline_to_file()`: JSON 저장 (자동 디렉토리 생성)
- `load_baseline_from_file()`: JSON 로드
- `calculate_change_percentage(current_value, metric_name)`: 변화율 계산
- `is_baseline_valid()`: 필수 지표 확인

**데이터 구조**:
- `BaselineMetrics`: 타임스탐프 + 수집시간 + 프레임수 + 지표 딕셔너리

**저장 포맷** (JSON):
```json
{
  "timestamp": "2026-04-29T13:00:00",
  "collection_duration_seconds": 5.0,
  "frame_count": 150,
  "metrics": {
    "cheek_distance": 0.35,
    "eye_distance": 0.18,
    "face_shoulder_ratio": 0.55,
    ...
  }
}
```

**특징**:
- 자동 저장: finish_baseline_collection() 후 바로 저장
- 변화율: baseline=0 처리 (0 반환)
- 검증: 80% 이상 프레임 수 확인

---

### 1.4 judgment_engine.py
**목적**: 자세 판정 로직

**주요 클래스**: `JudgmentEngine`

**4가지 자세 판정**:

#### A. forward_head (거북목)
- 조건: cheek_distance ↑ + face_shoulder_ratio ↑
- 임계값: cheek_distance ≥ 8%, ratio ≥ 15%
- 확률: 0.6 × cheek_score + 0.4 × ratio_score
- 지속시간: 2초

#### B. recline (기댄 자세)
- 조건: cheek_distance ↓
- 임계값: cheek_distance ≤ -10%
- 확률: 절댓값 기반 정규화
- 지속시간: 2초

#### C. crossed_leg_estimated (다리 꼰 자세)
- 조건: abs(shoulder_tilt_deg) > 6°
- 임계값: 6도
- 확률: shoulder_tilt 기반
- 지속시간: 3초

#### D. chin_rest_estimated (턱 괸 자세)
- 조건: (eye_line_tilt ≥ 8° OR shoulder_tilt ≥ 6°) AND (hand_near_face OR chin_occlusion > 0.2)
- 확률: 0.35 × eye_score + 0.2 × shoulder_score + 0.45 × hand_score
- 지속시간: 2초

**핵심 메서드**:
- `judge_single_frame(indicators)`: 단일 프레임 판정
- `accumulate_frame(judgment)`: 시간 누적
- `get_confirmed_posture(fps)`: 지속시간 만족 자세 반환
- `_judge_*()`: 자세별 판정 함수 (4개)

**데이터 구조**:
- `PostureJudgmentResult`: 각 자세별 확률 + triggered 상태 + 우위 자세
- `PostureType`: Enum (FORWARD_HEAD, RECLINE, CROSSED_LEG, CHIN_REST)

**특징**:
- JSON 기반 임계값: 코드 하드코딩 없음
- 확률 기반: 0~1 범위 정규화
- 지속시간 누적: 프레임 단위 카운트
- 디버그 로깅: 각 자세 판정 상세 기록
- 에러 처리: 예외 발생 시 likelihood=0, triggered=False

---

### 1.5 state_machine.py
**목적**: 상태 관리

**주요 클래스**: `StateMachine`

**상태** (3가지):
- `NORMAL`: 바른 자세
- `WARNING`: 경고 (나쁜 자세 감지)
- `BAD_POSTURE`: 지속적인 나쁜 자세

**상태 전이 규칙**:
```
NORMAL:
  + confirmed_posture = None → NORMAL 유지
  + confirmed_posture ≠ None → WARNING 전이

WARNING:
  + confirmed_posture = None → NORMAL 전이
  + confirmed_posture ≠ None (3초 이상) → BAD_POSTURE 전이

BAD_POSTURE:
  + confirmed_posture = None (1초 이상) → WARNING 전이
  + confirmed_posture ≠ None → BAD_POSTURE 유지
```

**핵심 메서드**:
- `update_state(confirmed_posture, fps)`: 상태 전이 로직
- `register_state_change_callback(callback)`: 상태 변경 콜백 등록
- `get_current_state()`: 현재 상태 조회
- `get_time_in_current_state()`: 상태 경과 시간 조회
- `reset()`: 초기화

**데이터 구조**:
- `StateTransitionEvent`: 상태 전이 이벤트 (from, to, posture, timestamp, duration)
- `PostureState`: Enum

**특징**:
- 콜백 시스템: 상태 변경 시 등록된 함수 호출 (UI 업데이트용)
- 타이밍 조건: 3초(WARNING→BAD), 1초(BAD→WARNING)
- 상세 로깅: 각 전이 이유 기록

---

## 2. 파일 구조 (Phase 2)

```
src/core/
├── __init__.py
├── landmark_extractor.py      (✓ 완성)
├── indicator_calculator.py    (✓ 완성)
├── baseline_manager.py        (✓ 완성)
├── judgment_engine.py         (✓ 완성)
└── state_machine.py           (✓ 완성)
```

---

## 3. 주요 특징 및 설계 결정

### 3.1 MediaPipe 통합
- **선택**: task 파일 기반 (holistic/solutions 미사용)
- **이유**: 모듈화, 버전 고정, 의존성 명확화
- **구현**: pose_landmarker, face_landmarker, hand_landmarker 분리 로드

### 3.2 JSON 기반 임계값
- **선택**: posture_definition_criteria.json에서 로드
- **이유**: 사용자 환경 적응, 재구현 불필요
- **구현**: ConfigManager 활용

### 3.3 시간 누적 조건
- **선택**: 단일 프레임이 아닌 지속시간 기준
- **이유**: 오탐 방지 (노이즈/짧은 움직임 무시)
- **구현**: JudgmentEngine의 posture_history 카운트

### 3.4 확률 기반 판정
- **선택**: 각 자세별 확률값 (0~1)
- **이유**: UI에서 신뢰도 시각화 가능
- **구현**: 정규화된 점수 가중 합산

### 3.5 상태 머신 콜백
- **선택**: 상태 변경 시 콜백 함수 호출
- **이유**: Phase 4에서 UI 업데이트 용이
- **구현**: register_state_change_callback()

---

## 4. Phase 2 체크리스트

- [x] landmark_extractor.py
  - [x] 모델 로드 로직
  - [x] 랜드마크 추출 및 필터링
  - [x] 정규화
  
- [x] indicator_calculator.py
  - [x] 9개 지표 계산 함수
  - [x] PostureIndicators 클래스
  - [x] 범위 검증 (클립)
  
- [x] baseline_manager.py
  - [x] 수집, 저장, 로드
  - [x] 변화율 계산
  - [x] JSON 포맷
  
- [x] judgment_engine.py
  - [x] 4가지 자세 판정 로직
  - [x] 확률 계산
  - [x] 지속시간 누적
  - [x] 디버그 로깅
  
- [x] state_machine.py
  - [x] 상태 전이 규칙
  - [x] 콜백 시스템
  - [x] 타이밍 조건

---

## 5. 코드 품질

### 가독성
- 명확한 메서드명 & docstring
- 한국어 주석 (복잡 로직)
- 단일 책임 원칙 준수

### 에러 처리
- 예외 발생 시 로깅 & 안전한 기본값 반환
- None 값 안전하게 처리
- 범위 검증 (np.clip)

### 성능
- 불필요한 계산 최소화
- 벡터 연산 활용 (NumPy)
- 메모리 효율 (generator 고려)

### 테스트 가능성
- 팩토리 함수 제공 (mock 용이)
- 의존성 주입 (config, baseline_manager)
- 로깅으로 디버깅 가능

---

## 6. 다음 단계 (Phase 3)

**PyQt UI 구현**

필요한 작업:
1. 6개 화면 구현 (initial_baseline, hub, settings, statistics, detection, alert)
2. 엔진과의 시그널/슬롯 연결
3. 실시간 자세 업데이트
4. 통계 저장 및 표시

---

## 7. 주의사항 (Phase 3에서)

1. **웹캠 처리**: 별도 QThread에서 landmark_extractor 실행
2. **UI 업데이트**: Signal/Slot으로 메인 스레드에 전달
3. **파일 저장**: data/baseline.json 경로 확인
4. **에러 처리**: 웹캠 권한, 모델 로드 실패 등

---

**Phase 2 완료. Phase 3 준비 완료.**
