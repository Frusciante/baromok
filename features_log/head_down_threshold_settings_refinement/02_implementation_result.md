# 고개 숙임 각도 설정 개선 결과 보고서

## 1. 구현 요약
사용자의 요청에 따라 '고개 숙임 각도' 설정을 직관적인 각도 수치 기반으로 변경하고, 이를 시스템 기준 파일과 연동하였습니다.

## 2. 상세 변경 내역

### 2.1. 데이터 모델 및 관리 (`src/config.py`)
- `SettingsConfig`: `head_down_threshold` 필드 추가 및 Pydantic 연동.
- `ConfigManager`:
    - `update_posture_criteria(key_path, value)`: 중첩된 JSON 키 경로를 지원하는 업데이트 메서드 구현.
    - `save_posture_criteria_to_json()`: `posture_definition_criteria.json` 파일 저장 기능 구현.

### 2.2. UI 개선 (`src/ui/widgets/settings_widgets.py`)
- `SensitivitySettingsWidget`:
    - `head_down_threshold` 슬라이더를 3-20 범위로 고정.
    - 수치 표시 라벨에 `int(val)°` 형식 적용.
    - `_on_head_down_slider_changed` 콜백 신설.

### 2.3. 시스템 연동 (`src/ui/app.py`)
- `_apply_settings`: 워커(JudgeManager)에 `head_down_threshold` 주입.
- `_persist_settings_if_dirty`:
    - 사용자 설정 저장 시 `head_down_threshold`가 변경되었다면 기준 파일의 `posture_types.head_down.threshold` 업데이트.
    - `forward_head_distance_threshold` 또한 기준 파일의 `eye_monitoring.distance_threshold_cm`와 동기화.

## 3. 결과 확인
- UI에서 슬라이더 조작 시 3°에서 20°까지 정수 단위로 변경됨을 확인.
- 설정 저장 시 `data/posture_definition_criteria.json` 파일의 `head_down.threshold` 값이 실시간으로 변경되는 것을 파일 탐색기로 확인 완료.
- 앱 재시작 시 변경된 각도 값이 유지됨을 확인.
