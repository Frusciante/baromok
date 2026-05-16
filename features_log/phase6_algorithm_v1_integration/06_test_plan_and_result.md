# Phase 6: Posture Monitor Algorithm v1.0 통합 테스트 계획 및 결과

**작성일**: 2026-05-13
**단계**: Phase 6 통합
**상태**: 📋 테스트 대기 중

## 1. 테스트 목표
새롭게 통합된 v1.0 자세 분석 알고리즘(One Euro, EMA 필터, RANSAC 보정, 신규 점수 공식, Hysteresis 상태 머신)이 기존 아키텍처와 통합되어 정상적으로 동작하는지 검증한다.

## 2. 자동화 테스트 계획 (`test_phase6_algorithm_v1.py`)

| 테스트 항목 | 목적 | 예상 결과 |
|---|---|---|
| **Test 1: 상태 저장형 필터 (One Euro, EMA)** | 필터 유틸리티의 정상 동작 확인 | 입력값에 대해 에러 없이 부드럽게 평활화된 결과 반환 |
| **Test 2: RANSAC 캘리브레이션 모델** | `baseline_manager`의 RANSAC 곡선 적합(fit) 동작 확인 | 데이터 주입 후 `get_expected_ratio()`가 정상적으로 곡선 예상값 반환 |
| **Test 3: 신규 지표 연산 (`hand_face_score`)** | `indicator_calculator`의 손/턱 상호작용 점수 연산 검증 | 손이 얼굴에 가까울 때 `hand_face_score` 점수가 높게 반환됨 |
| **Test 4: 새로운 점수 기반 판정 (`JudgmentEngine`)** | RANSAC 기반 거북목, 턱 괸 자세 판별 동작 검증 | 비율 오차에 따라 `triggered=True` 및 `likelihood > warning_threshold` 반환 |
| **Test 5: 상태 머신 Hysteresis (시간 쿨다운)** | 상태 머신의 `min_state_hold_sec`(1.8초) 방어 로직 확인 | 짧은 스파이크 프레임 유입 시 상태가 깜빡이지 않고 기존 상태 유지 |

## 3. 수동(GUI) 테스트 계획
1. **거리 불변성 캘리브레이션 테스트**: 초기 수집 화면에서 "앞뒤로 멀어졌다 가까워지는 동작"을 통해 RANSAC을 학습시키고, 이후 카메라 거리가 바뀌어도 오탐되지 않는지 확인한다.
2. **상태 전환 깜빡임 테스트**: 1초 이내로 나쁜 자세를 취했다가 복귀할 때 UI가 깜빡이지 않는지 확인한다.

## 4. 자동화 테스트 결과
**수행일**: 2026-05-14
**결과**: ✅ 5/5 통과
- Test 1: One Euro & EMA 필터 동작 검증 (통과)
- Test 2: BaselineManager RANSAC 캘리브레이션 검증 (통과)
- Test 3: 신규 지표 연산 검증 (통과)
- Test 4: 새로운 RANSAC 오차 점수 기반 판정 검증 (통과)
- Test 5: 상태 머신 Hysteresis 검증 (통과)

## 5. 수동 테스트 결과
*(수행 대기 중)*