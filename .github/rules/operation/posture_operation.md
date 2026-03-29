# 자세 측정 운영 규칙

- 기준 문서: `../posture_definition.md`
- 목적: 프레임 점수화, 이벤트 확정, 상태 전이를 일관된 방식으로 운영한다.
- 판정 기준의 실제 수치/가중치/임계값은 md나 코드가 아니라 JSON에서만 관리한다.
- 기준 파일: `./posture_definition_criteria.json`
- 기준 문서: `./posture_definition_criteria_documentation.md`

## 1. 프레임 점수

- 프레임 점수 범위는 `frame_scoring.score_range`를 따른다.
- 자세별 가능도 계산식은 `frame_scoring.likelihood_formulas`를 따른다.

## 2. 이벤트 판정

- 즉시 판정 기준은 `event_judgment.immediate`를 따른다.
- 확정 판정 기준은 `event_judgment.confirmed`와 `posture_types.*.sustain_seconds`를 따른다.

## 3. 상태 머신

- 상태 머신 정의는 `global_rules.state_machine.states`를 따른다.
- 상태 전이 규칙은 `global_rules.state_machine.transitions`를 따른다.

## 4. 구현 체크포인트

- 단일 프레임 값만 사용하지 않고 시간 누적 조건을 함께 적용한다.
- baseline 대비 변화량을 모든 점수 계산의 기준으로 유지한다.
- 임계값은 사용자 환경(카메라 위치/거리)에 맞춰 조정 가능하게 설계한다.
- MediaPipe는 `holistic`과 `solutions`를 사용하지 않고, 모델 task 파일(`.task`)을 사용한다.
- 포즈/손/얼굴 등 필요한 모델은 task 파일 단위로 각각 분리해 관리한다.
