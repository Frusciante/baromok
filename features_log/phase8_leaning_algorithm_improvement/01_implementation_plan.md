# 기댄 자세 알고리즘 개선 구현 계획서

## 1. 개요
현재 기댄 자세는 광대 사이 거리와 어깨 너비의 비율(혹은 어깨 너비에 따른 광대 거리 예측)을 기반으로 판정하고 있습니다. 하지만 환경에 따라 판정의 정확도가 떨어지는 문제가 있어, 머리의 높이(Y 좌표)와 거리 대리 지표(어깨 너비 또는 눈 사이 거리) 간의 선형 회귀 모델을 도입하여 기댄 자세 판정 로직을 개선하고자 합니다.

## 2. 주요 변경 사항

### A. 기존 초기 자세 설정(Calibration) 과정 재사용
- **추가 UI 단계 없음**: 사용자가 현재 수행하는 "초기 자세 설정(3단계: 옆으로 기울임, 정면, 반대쪽 기울임)" 과정을 그대로 활용합니다.
- **데이터 동시 수집**: 기존 광대 거리 수집 시 머리 높이(`head_height`)와 거리 대리 지표(`distance_proxy`) 데이터를 함께 추출하여 `data/baseline.json`에 저장합니다.

### B. 지표 계산 개선 (`src/core/indicator_calculator.py`)
- 머리 높이(`head_height`) 지표 추가
  - 눈 중앙의 Y 좌표 또는 광대 중앙의 Y 좌표를 기반으로 계산 (MediaPipe 좌표계 기준 `1.0 - y`)
- 거리 대리 지표(`distance_proxy`) 선택 로직 준비
  - 어깨가 보이면 어깨 너비, 보이지 않으면 눈 사이 거리를 사용

### C. Baseline 관리 개선 (`src/core/baseline_manager.py`)
- 새로운 RANSAC 모델 추가: `height_ransac_model`
  - 독립 변수 ($x$): `shoulder_width` (또는 `eye_distance`)
  - 종속 변수 ($y$): `head_height`
- `baseline.json` 포맷 업데이트: 높이 관련 샘플 데이터(`ransac_h_samples` 등) 추가 저장
- `get_expected_height(distance_proxy)` 메서드 추가

### D. 판정 엔진 개선 (`src/core/judgment_engine.py`)
- 기댄 자세(`recline`) 판정 로직 수정
  - 기존 광대 거리 편차 기반에서 머리 높이 편차 기반으로 변경
  - 어깨 랜드마크 존재 여부에 따른 동적 대리 지표($x$) 전환 (Shoulder -> Eye)
  - RANSAC 모델의 기대 높이 대비 현재 높이의 편차로 판정

## 3. 알고리즘 상세
1. **수집 단계 (Calibration)**:
   - 사용자가 바른 자세에서 앞뒤로 움직일 때 `(distance_proxy, head_height)` 쌍을 수집
   - RANSAC을 이용해 $y = m \cdot x + b$ 선형 모델 도출
2. **판정 단계 (Inference)**:
   - 현재 `distance_proxy`에 대한 `expected_height` 산출
   - `deviation = measured_height - expected_height`
   - 사용자가 뒤로 기대면 머리 높이가 낮아지거나(카메라 각도에 따라 다름) 특정 방향으로 변화하는 것을 감지

## 4. 구현 단계
1. **1단계**: `indicator_calculator.py`에서 필요한 지표 산출 로직 추가
2. **2단계**: `baseline_manager.py`에서 새로운 RANSAC 모델 통합 및 수집 로직 수정
3. **3단계**: `judgment_engine.py`에서 기댄 자세 판정 로직을 높이 기반으로 교체
4. **4단계**: 테스트 코드를 통한 알고리즘 검증 및 기존 기능과의 호환성 확인

## 5. 검증 계획
- **단위 테스트**: `indicator_calculator` 및 `baseline_manager`의 모델 피팅 로직 검증
- **통합 테스트**: 다양한 거리에서 기댄 자세를 취했을 때 일관된 판정이 나오는지 확인
- **비교 테스트**: 기존 광대 거리 기반 방식과 정확도 비교
