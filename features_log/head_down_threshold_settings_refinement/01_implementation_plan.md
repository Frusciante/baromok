# 고개 숙임 각도 설정 범위 수정 및 기준 파일 연동

## 1. 개요
환경설정의 '고개 숙임 각도' 슬라이더를 기존 민감도 방식(1-100)에서 실제 각도 수치(3-20°)를 직접 표시하고 조절하는 방식으로 개선한다. 또한, 이 설정값이 변경될 경우 `posture_definition_criteria.json`(기준 파일)에도 즉시 반영되어 영구 저장되도록 한다.

## 2. 주요 변경 사항

### 2.1. 설정 모델 (`src/config.py`)
- `SettingsConfig` 클래스에 `head_down_threshold` 필드 추가.
- `ConfigManager`에 판정 기준(`posture_criteria`)을 업데이트하고 파일로 저장하는 `save_posture_criteria_to_json()` 메서드 추가.
- 기본값 로드 및 초기화 로직에 `head_down_threshold` 반영.

### 2.2. UI 구성 (`src/ui/widgets/settings_widgets.py`)
- `SensitivitySettingsWidget`에서 `head_down_threshold`를 위한 별도 슬라이더 처리 로직 구현.
- 슬라이더 범위를 3.0 ~ 20.0으로 설정하고, 라벨에 단위(°)와 함께 실제 수치를 표시.
- 슬라이더 변경 시 민감도 변환 없이 수치를 그대로 전달하도록 수정.

### 2.3. 애플리케이션 로직 (`src/ui/app.py`)
- `_apply_settings`에서 카메라 워커의 판정 매니저에 `head_down_threshold`를 전달.
- `_persist_settings_if_dirty`에서 `head_down_threshold`가 변경된 경우 `ConfigManager`를 통해 `posture_definition_criteria.json` 파일을 업데이트.
- (부가) 거북목 거리 임계값(`forward_head_distance_threshold`)도 기준 파일과 동기화되도록 보강.

## 3. 검증 계획
- [ ] 환경설정 화면에서 '고개 숙임 각도' 슬라이더가 3-20 범위로 동작하는지 확인.
- [ ] 수치가 슬라이더 우측에 직접 표시되는지 확인.
- [ ] 설정을 저장하거나 화면을 나갈 때 `data/config.json`과 `data/posture_definition_criteria.json`이 모두 업데이트되는지 확인.
- [ ] 앱 재시작 시 변경된 수치가 슬라이더에 유지되는지 확인.
