# Phase 6 Step 3: 수집 및 지표 연산 모듈 수정 요약

## 1. LandmarkExtractor 변경
- 원시 정규화 좌표가 도출된 후 추출된 주요 신체 포인트(얼굴 중심, 광대, 눈, 어깨)를 Flatten하여 `OneEuroFilter`에 일괄 통과시켜 잔떨림 억제 및 보정 로직을 추가했습니다.

## 2. BaselineManager 변경
- 기존의 수집된 5초간 데이터에 대해 추가적으로 `shoulder_width`와 `face_shoulder_ratio`를 쌍으로 묶어 `RansacQuadraticModel`을 훈련시키는 과정을 `finish_baseline_collection`에 추가했습니다.
- `BaselineMetrics`의 직렬화/역직렬화(json 저장 및 로드)에 모델 파라미터가 아닌 **원시 샘플 데이터 세트**(`ransac_x_samples`, `ransac_y_samples`)를 저장하여 런타임에 RANSAC 모델을 다시 피팅하여 재현하도록 구현했습니다.
- 판정 엔진에서 RANSAC 모델을 호출하여 현재 어깨 너비에 따른 예측 얼굴 비율을 구하는 `get_expected_ratio` 인터페이스를 열어두었습니다.

## 3. IndicatorCalculator 변경
- `hand_face_score` 신규 계산(`calculate_hand_near_score` 추가)을 구현하여 손과 얼굴 사이의 상호작용 점수를 0~1로 수치화했습니다. `PostureIndicators` 데이터 클래스에도 반영했습니다.
- 계산된 9가지 모든 중요 지표에 `EMAFilter`를 통과시켜 극단적인 프레임 스파이크 현상을 안정적으로 잡아주도록 처리했습니다.