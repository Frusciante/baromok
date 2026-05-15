# Phase 6 Step 4: 판정 엔진 및 상태 머신 업데이트 요약

## 1. JudgmentEngine 변경
- RANSAC 기반 캘리브레이션 함수인 `get_expected_ratio()`를 가져와 거북목(`forward_head`)과 기댄 자세(`recline`)의 현재 비율 오차(`ratio_up_score`, `ratio_down_score`)를 구하는 로직으로 완전히 교체했습니다.
- `chin_rest`(턱 괸 자세)에도 신규 지표인 `hand_face_score`와 `neck_offset` 점수를 가중치로 합산하는 새로운 v1.0 공식을 반영했습니다.
- 임계값을 0.45(`warning_threshold`) 기준으로 설정하여, 해당 점수를 넘어야 트리거(triggered) 되도록 연동했습니다.

## 2. StateMachine 변경
- Hysteresis(상태 쿨다운) 로직을 추가하여, `temporal_validation.min_state_hold_sec`(1.8초) 동안은 상태 깜빡임을 방지하도록 구현했습니다.
- 이전처럼 고정값(3초)이 아닌 `min_duration_sec`(1.5초)를 바탕으로, WARNING에서 BAD_POSTURE로 넘어가는 더 정밀한 시간 기반 점진적 알림 전이를 구축했습니다.