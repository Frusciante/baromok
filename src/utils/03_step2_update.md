# Phase 6 Step 2: 필터 및 유틸리티 구현 결과

## 변경 사항 요약
1. **One Euro Filter 구현 (`src/utils/helpers.py`)**
   - 상태 저장(stateful) 방식으로 프레임 간 타임스탬프와 좌표 변화량을 추적해 가변 컷오프를 적용하는 `OneEuroFilter` 클래스를 구현했습니다.
   - Numpy 벡터 연산을 지원하여 N차원 랜드마크 배열을 한 번에 스무딩할 수 있습니다.
2. **EMA Filter 보강 (`src/utils/helpers.py`)**
   - 프레임별로 연속적인 스무딩 상태를 유지할 수 있는 `EMAFilter` 클래스를 신설했습니다.
3. **RANSAC Quadratic Model 헬퍼 구현 (`src/utils/helpers.py`)**
   - RANSAC 적합 관리를 위한 `RansacQuadraticModel` 클래스를 신설했습니다.
   - 의존성 지연 로드(lazy import)를 적용해 파일 시작 시 런타임 오버헤드를 막고, `scikit-learn`의 `PolynomialFeatures(degree=2)`와 `RANSACRegressor`를 파이프라인으로 묶어 2차 포물선 예측 모델의 생성과 결과값 반환을 처리합니다.
   - 예외 처리와 `is_fitted` 상태 관리를 통해 안전한 `fit` 및 `predict` 동작을 보장합니다.