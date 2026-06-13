# 전 자세 유형 감도 설정 확장 구현 계획서

## 1. 개요
현재 "거북목"과 "기댄 자세"에만 국한된 감도 설정 기능을 모든 탐지 가능 자세(턱 괸 자세, 화면 가까움, 고개 돌림, 고개 기울임)로 확장합니다. 이를 통해 사용자가 자신의 환경과 신체 특성에 맞춰 모든 경고의 민감도를 세밀하게 조정할 수 있도록 합니다.

## 2. 주요 변경 사항

### A. 설정 데이터 구조 확장 (`src/config.py`)
- `SettingsConfig` 클래스에 신규 필드 추가:
    - `chin_rest_sensitivity`
    - `eye_close_sensitivity`
    - `turned_head_sensitivity`
    - `side_tilt_sensitivity`
- `load_from_json` 및 기본값 로드 로직에 위 필드들 통합.

### B. 멀티스레드 워커 동기화 로직 강화 (`src/core/judge_workers.py`)
- `PostureJudgeManager.update_sensitivities` 메서드가 모든 자세의 감도값을 받아 각 워커에게 배분하도록 수정.
- 각 워커 클래스(예: `ChinRestWorker`, `EyeCloseWorker`)가 `self.sensitivity` 값을 판정 로직에 반영하도록 보완.

### C. UI 구성 개편 (`src/ui/widgets/settings_widgets.py`)
- `SensitivitySettingsWidget` 레이아웃 및 로직 수정:
    - 기존 2개 슬라이더에서 6개 슬라이더 체제로 확장.
    - 각 자세별 적절한 감도 범위(Min, Max) 및 단계(Step) 정의.
    - 스크롤 영역을 고려한 위젯 높이 최적화.

### D. 통합 연동 (`src/ui/app.py` & `src/core/judgment_engine.py`)
- 앱 초기화 및 설정 저장 시 모든 감도 지표가 `JudgmentEngine`과 `CameraWorker`를 거쳐 워커들에게 전달되도록 데이터 흐름 수정.

## 3. 구현 단계
1. **1단계**: `src/config.py`의 `SettingsConfig` 구조 업데이트.
2. **2단계**: `src/core/judge_workers.py`에서 전 자세 감도 수신 및 반영 로직 구현.
3. **3단계**: `src/ui/widgets/settings_widgets.py`에서 6종 감도 조절 UI 구현.
4. **4단계**: `src/ui/app.py` 등에서의 데이터 전달 파이프라인 최종 연결.

## 4. 검증 계획
- 각 슬라이더 조절 시 해당 판정 워커의 `self.sensitivity` 값이 즉시 변경되는지 디버그 로그로 확인.
- 실제 자세를 취했을 때 감도 설정값(낮음 vs 높음)에 따라 경고 발생 빈도가 의도대로 변하는지 확인.
