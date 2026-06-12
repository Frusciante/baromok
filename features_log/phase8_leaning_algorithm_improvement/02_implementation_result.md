# 기댄 자세 알고리즘 개선 구현 결과 보고서

## 1. 개요
기존의 광대 거리 비율 방식의 한계를 극복하기 위해, 머리 높이(`head_height`)와 거리 대리 지표(`distance_proxy`) 간의 RANSAC 선형 회귀 모델을 도입하여 기댄 자세 판정 알고리즘을 개선하였습니다.

## 2. 주요 구현 내용

### A. 지표 계산 (`src/core/indicator_calculator.py`)
- `head_height` 지표 추가: 눈과 광대의 Y 좌표 평균을 이용해 계산 (1.0 - avg_y).
- `PostureIndicators` 데이터클래스 및 EMA 필터에 신규 지표 통합.

### B. Baseline 모델링 (`src/core/baseline_manager.py`)
- **Triple RANSAC 모델 도입**:
    1.  `shoulder_cheek_model`: 어깨 너비 기반 광대 거리 예측 (거북목용)
    2.  `shoulder_height_model`: 어깨 너비 기반 머리 높이 예측 (기댄 자세용 - 메인)
    3.  `eye_height_model`: 눈 사이 거리 기반 머리 높이 예측 (기댄 자세용 - 보조)
- **디버그 시각화 개선**:
    - `debug_plots/` 내부에 각 모델별 서브디렉토리(`shoulder_cheek`, `shoulder_height`, `eye_height`)를 생성하여 결과 그래프를 분류 저장.
- **Persistence 개선**: RANSAC 모델의 정확한 복원을 위해 3개 모델의 원시 샘플 데이터를 `baseline.json`에 포함하여 저장하도록 수정.

### C. 판정 엔진 (`src/core/judgment_engine.py`)
- **로직 분리**: 
    - **거북목(Forward Head)**: 기존과 동일하게 `cheek_distance` 기반 편차 사용.
    - **기댄 자세(Recline)**: 신규 `head_height` 기반 편차를 **단독으로 사용**.
- 어깨 랜드마크 누락 시에도 눈 사이 거리를 활용하여 기댄 자세 판정이 중단되지 않도록 개선.

## 3. 검증 결과
- **단위 테스트 (`test/test_leaning_algorithm_v2.py`)**:
    - 머리 높이 계산 정확도 확인.
    - RANSAC 모델 피팅 및 파일 저장/로드 성공 확인.
    - 기댄 자세 발생 시 편차 기반 점수 산출 및 트리거 확인.
- **회귀 테스트 (`test/test_phase6_algorithm_v1.py`)**:
    - `head_height` 추가에 따른 기존 테스트 코드의 시그니처 오류 수정 및 통과 확인.

## 4. 향후 계획
- 실제 다양한 조명 및 카메라 각도 환경에서 사용자의 피드백을 수집하여 감도(`recline_sensitivity`) 최적화 진행.
