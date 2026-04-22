# 동작 구현 상황 체크리스트

<p><a href="./copilot-instructions.md">메인 지침</a> | <a href="./rules/operation/common.md">로직 규칙</a> | <a href="./rules/operation/posture_operation.md">자세 측정 운영 규칙</a> | <a href="./rules/posture_definition.md">자세 정의서</a></p>

## 목차
<p>
<a href="#1-사용-기준">1. 사용 기준</a> |
<a href="#2-기준-데이터-로딩">2. 기준 데이터 로딩</a> |
<a href="#3-baseline-및-지표-계산">3. baseline 및 지표 계산</a> |
<a href="#4-자세-판정-로직">4. 자세 판정 로직</a> |
<a href="#5-상태-머신">5. 상태 머신</a> |
<a href="#6-mediapipe모델-구성">6. MediaPipe/모델 구성</a> |
<a href="#7-검증-및-문서-동기화">7. 검증 및 문서 동기화</a>
</p>

## 1. 사용 기준
- 목적: 현재 구현 상태를 빠르게 점검하고 누락 항목을 추적한다.
- 기준 문서: `rules/operation/common.md`, `rules/operation/posture_operation.md`, `rules/operation/posture_definition_criteria_documentation.md`
- 상태 표시: 완료는 `[x]`, 미완료는 `[ ]`로 관리한다.

## 2. 기준 데이터 로딩
- [ ] `rules/operation/posture_definition_criteria.json` 로더 연결
- [ ] 로딩 실패 시 기본값 침묵 대체 없이 예외 처리
- [ ] 스키마 실패 시 키 경로 포함 에러 메시지 출력
- [ ] 판정 수치가 코드 상수/별도 md에 중복되지 않음

## 3. baseline 및 지표 계산
- [ ] baseline 수집 시간 `baseline.capture.duration_seconds`(5초) 적용
- [ ] baseline 지표(`cheek_distance`, `eye_distance`, `face_shoulder_ratio`) 저장
- [ ] 프레임별 변화량 계산 로직 구현
- [ ] 노이즈 완화를 위한 필터(이동평균/중앙값 등) 적용 여부 확인

## 4. 자세 판정 로직
- [ ] `posture_types.recline` 조건/지속시간 적용
- [ ] `posture_types.forward_head` 조건/지속시간 적용
- [ ] `posture_types.crossed_leg_estimated` 조건/반복창/지속시간 적용
- [ ] `posture_types.chin_rest_estimated` 조건/보조신호/지속시간 적용
- [ ] `event_judgment.immediate` 및 `event_judgment.confirmed` 반영
- [ ] `frame_scoring.likelihood_formulas` 반영

## 5. 상태 머신
- [ ] 상태 집합(`NORMAL`, `WARNING`, `BAD_POSTURE`) 구현
- [ ] 전이 규칙(`global_rules.state_machine.transitions`) 구현
- [ ] 상태 전이 시 이벤트/로그/알림 연계 동작 확인

## 6. MediaPipe/모델 구성
- [ ] `holistic` 미사용
- [ ] `solutions` 미사용
- [ ] 필요한 모델을 `.task` 단위로 분리 관리

## 7. 검증 및 문서 동기화
- [ ] 정상/예외/경계 케이스 테스트 수행
- [ ] 회귀 위험 항목 점검
- [ ] 검증 불가 항목과 사유 기록
- [ ] 코드 변경 시 관련 md/json 문서 동기화
