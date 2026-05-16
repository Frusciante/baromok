# Phase 6 Step 1: 판정 기준 JSON 및 환경 설정 업데이트

## 변경 사항 요약
1. **의존성 업데이트**
   - `requirements.txt`에 RANSAC 처리를 위한 `scikit-learn` 추가 완료.
2. **JSON 스키마 확장 (`posture_definition_criteria.json`)**
   - `filters` 파라미터(One Euro, EMA) 신설.
   - `baseline.capture` 방식을 `distance_movement_ransac`으로 변경하고 수집 시간을 조정.
   - `global_rules.state_machine`에 `thresholds` 및 `temporal_validation` 항목으로 시간 조건(1.5초, 1.8초) 등 구체적 임계값 추가.
   - `posture_types` 내 거북목, 기댄 자세 등의 `primary_conditions`를 RANSAC 기반 점수(`ratio_up_score`, `face_near_score` 등)에 맞게 조정.
   - `frame_scoring.likelihood_formulas`를 `algorithm_reference.md` 기준의 새로운 점수 계산식으로 변경.