# 통계 유지율 정규화, 어깨 미감지 폴백 모델 전환 및 기댄 자세 방어 로직 개선 계획서

## 1. 개요
1. **통계 화면 바른 자세 유지율 100% 초과(219%) 버그 수정**: 세션 통계 산출 시 분자(`good_posture_seconds`)와 분모(`duration_seconds`)의 시간 측정 기준을 통일하고, 재측정 화면 진입 시 세션 생명주기와 예열(`warmup`) 프레임 필터링을 보완한다.
2. **어깨 미감지(또는 프레임 부족) 시 어깨 미사용 모델 폴백**: 기준 자세 수집 시 어깨가 감지되지 않거나 유효 샘플이 부족하더라도 재측정을 요구하지 않고, 어깨를 사용하지 않는 모델(`Eye-Height` 모델 및 홍채 화면 거리 모델)만 활성화하여 자세 판정을 수행한다.
3. **턱 괸 자세(얼굴 주변 손 감지 + 어깨 기울기) 시 기댄 자세 오판정 방어**: 한쪽 팔로 턱을 괴어 평균 높이가 낮아질 때 기댄 자세로 잘못 인식되지 않도록, 얼굴 주변에 손이 감지된 상태에서 어깨 선 각도가 기울어졌을 때 기댄 자세를 방어하고 턱 괸 자세 상호 배제 로직을 추가한다. (손이 얼굴 주변에 없을 때는 어깨 기울기로 인해 일률적으로 바른 자세로 탐지되지 않도록 한다.)

## 2. 주요 변경 사항

### 2.1. 세션 통계 및 생명주기 보완 (`src/core/session_manager.py`, `src/ui/screens/statistics_screen.py`, `src/ui/screens/detection_screen.py`, `src/ui/app.py`)
- `add_frame_data`, `_calculate_stats_from_db`, `DetectionScreen._on_frame_processed`에서 `baseline` 및 `warmup` 프레임을 제외.
- `_calculate_stats_from_db`에서 상태별 시간 비율(`normal_ratio`, `warning_ratio`, `bad_ratio`)을 세션 총 시간(`dur`)에 곱해 `good_posture_seconds`, `warning_posture_seconds`, `bad_posture_seconds`를 정규화하여 합계가 `duration_seconds`와 항상 일치하도록 수정.
- `DateAggregator.aggregate`에서 상태별 시간 합을 분모로 우선 사용하고 유지율을 `0.0~100.0%`로 클램핑.
- 감지 중 기준 자세 설정(`screen_index == 0`) 진입 시 진행 중인 세션을 먼저 정상 종료(`end_session`)하도록 수정.

### 2.2. 어깨 미감지 시 어깨 미사용 모델 전환 (`src/core/baseline_manager.py`, `src/core/judge_workers.py`, `src/ui/screens/detection_screen.py`)
- `BaselineManager.is_baseline_valid`에서 `shoulder_width` 및 `shoulder_cheek_model.is_fitted` 필수 요구 조건 제거.
- `ForwardHeadWorker`: `shoulder_cheek_model.is_fitted`가 `True`이고 현재 프레임에 `shoulder_width`가 있을 때만 어깨-광대 비율 편차 모델을 사용하고, 그렇지 않으면 홍채 기반 눈-화면 거리 모델만 사용.
- `ReclineWorker`: `shoulder_height_model.is_fitted`가 `True`이고 현재 프레임에 `shoulder_width`가 있을 때만 어깨-높이 모델을 사용하고, 그렇지 않으면 `eye_height_model`(`eye_distance` → `head_height`)을 사용.

### 2.3. 턱 괸 자세 시 어깨 기울기 기반 기댄 자세 방어 (`src/core/judge_workers.py`, `src/core/judgment_engine.py`, `data/posture_definition_criteria.json`)
- `ForwardHeadWorker._is_guarded`, `ReclineWorker._is_guarded`: 손이 얼굴 주변에 없을 때 어깨 기울기만으로 나쁜 자세 판정이 일률적으로 가드(바른 자세 처리)되지 않도록 단독 어깨 기울기 가드 제거.
- `ReclineWorker.handle_indicators`:
  - 얼굴 주변에 손이 감지(`hand_near_face` 또는 `chin_occlusion > 0.25`)된 상태에서 어깨 선 기울기(`abs(shoulder_tilt_deg)` 또는 기준 자세 대비 변화량)가 `posture_types.recline.guards.max_shoulder_tilt`(`6.0°`) 이상일 때 기댄 자세 점수를 `0.0`으로 억제.
- `ChinRestWorker.handle_indicators`: 얼굴 주변에 손이 감지되었을 때 어깨 기울기(`shoulder_tilt_deg`) 점수를 분자에 정상 반영하여 턱 괸 자세 인식률 개선.
- `JudgmentEngine`: `chin_rest_estimated` 활성/확정 시 `recline`을 상호 배제하도록 추가.
