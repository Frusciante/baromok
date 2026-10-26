# 홍채 기반 거리 알고리즘 개선 구현 결과서

## 1. 구현 요약
임시로 적용되어 있던 `-20cm` 덧셈 보정을 제거하고, 실측 데이터셋(30~70cm 구간) 분석 및 실시간 검증을 통해 외곽 4점 가로 지름 추출 + 양안 평균 + 곱셈형 보정 계수(`distance_correction_scale`) 기반의 거리 계산 알고리즘을 실제 애플리케이션에 적용하였다.

## 2. 주요 변경 내역

### 2.1. 홍채 지름 추출 개선 (`src/core/landmark_extractor.py`)
- 홍채 중심점(468, 473)이 반지름 평균에 포함되어 지름이 약 20% 과소 추정되던 문제를 해결하기 위해 외곽 4점(좌: 469~472, 우: 474~477)만 사용하도록 변경.
- 정수(`int`) 절사를 제거하고 부동소수점 픽셀 좌표를 그대로 사용하여 원거리 양자화 노이즈 감소.
- 홍채 외곽 포인트의 `presence`/`visibility`가 0으로 반환되는 MediaPipe 특성을 반영하여 신뢰도 필터를 생략하고 두 대각선 중 긴 값(가로 지름)을 추출.

### 2.2. 핀홀 거리 산출식 및 보정 계수 적용 (`src/core/indicator_calculator.py`, `data/posture_definition_criteria.json`)
- 고정 `-20.0cm` 오프셋 제거.
- 양안 중 최솟값(`min`) 대신 양안 평균(`mean`)을 사용하여 단일 눈 노이즈 편향 완화.
- `data/posture_definition_criteria.json`의 `eye_monitoring.distance_correction_scale`을 로드하여 곱셈 보정을 수행하도록 구성.

### 2.3. 비ASCII(한글) 경로 모델 로드 우회 (`src/ui/app.py`)
- Windows 환경에서 프로젝트 경로에 한글이 포함될 경우 MediaPipe `.task` 파일을 열지 못하는 문제를 방지하기 위해, 앱 시작 시 ASCII 임시 경로(`%TEMP%/baromok_models`)로 모델 파일을 복사하여 로드하도록 개선.

## 3. 검증 결과
- 30~70cm 구간 실측 이미지 30장 및 20cm 근거리 실시간 웹캠 테스트에서 전 구간 오차 목표(MAE 3cm 이하, 평균 오차율 ±5% 이내)를 달성함을 확인.
