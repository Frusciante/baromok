# 멀티스레드 자세 탐지 아키텍처 구현 계획서

## 1. 개요
현재의 순차적(Sequential) 자세 탐지 구조를 멀티스레드 기반의 병렬 구조로 개편합니다. 각 자세별(거북목, 기댄 자세, 턱 괸 자세 등) 판정 로직을 독립적인 스레드에서 수행함으로써 여러 나쁜 자세가 동시에 발생하는 상황을 정확하게 포착하고 시스템의 반응성을 극대화하는 것이 목적입니다.

## 2. 주요 설계 방향

### A. 역할 분리 (Producer-Consumer 패턴)
- **생산자 (`CameraWorker`)**: 카메라 프레임 캡처, 랜드마크 추출 및 공통 지표(`PostureIndicators`) 산출을 담당합니다. 계산된 지표는 판정 워커들에게 신호(Signal)로 전달됩니다.
- **소비자 (`PostureJudgeWorker`)**: 각 자세 유형별로 독립적인 인스턴스가 생성됩니다. 전달받은 지표를 자신의 스레드 분석하여 판정 결과를 산출합니다.
- **조정자 (`JudgmentEngine` & `StateMachine`)**: 여러 워커로부터 비동기적으로 수집된 결과를 통합합니다. 기존 단일 자세 추적 방식에서 **다중 활성 자세 추적** 방식으로 업그레이드됩니다.

### B. 다중 탐지 지원 (Multi-posture Tracking)
- `PostureJudgmentResult`에 단일 `dominant_posture` 대신 `active_postures` 리스트를 포함합니다.
- `StateMachine`은 동시에 여러 나쁜 자세가 감지될 경우 이를 모두 추적하며, UI에 통합된 상태 정보를 제공합니다.

## 3. 구현 단계

### 1단계: 판정 워커 시스템 구축 (`src/core/judge_workers.py`)
- `QObject` 기반의 `BaseJudgeWorker` 클래스 정의.
- 자세별 하위 클래스 구현 (`ForwardHeadJudge`, `ReclineJudge`, `ChinRestJudge` 등).
- 모든 워커를 생성하고 스레드를 할당/관리하는 `PostureJudgeManager` 구현.

### 2단계: 카메라 워커 비동기화 (`src/core/camera_worker.py`)
- `process_frame` 내의 순차적 판정 호출을 제거.
- 지표 산출 직후 `PostureJudgeManager`에 신호를 발신하도록 수정.

### 3단계: 조정 로직 및 상태 머신 고도화
- `JudgmentEngine`이 여러 워커의 결과를 수집하여 `active_postures`를 관리하도록 수정.
- `StateMachine`이 다중 자세의 지속 시간을 각각 추적하고 통합 상태를 결정하도록 개선.

### 4단계: 통합 검증 및 UI 반영
- 여러 자세 동시 발생 시 시각적/청각적 경고의 우선순위 및 표시 방식 최적화.
- 멀티스레드 도입에 따른 CPU/메모리 부하 및 지연 시간(Latency) 측정.

## 4. 검증 계획
- **단위 테스트**: 각 판정 워커가 독립적으로 정확한 결과를 내놓는지 확인.
- **동시성 테스트**: 두 가지 이상의 나쁜 자세가 취해졌을 때 누락 없이 모두 감지되는지 확인.
- **회귀 테스트**: 기존 단일 자세 감지 성능이 저하되지 않았는지 확인.
