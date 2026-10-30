# Posture Monitoring System Technical Summary

<p><a href="../../copilot-instructions.md">메인 지침</a> | <a href="../posture_definition.md">자세 정의서</a> | <a href="./common.md">로직 규칙</a> | <a href="./posture_operation.md">운영 규칙</a></p>

## 목차
<p>
<a href="#1-핵심-설계-철학">1. 핵심 설계 철학</a> |
<a href="#2-정보-수집-방식">2. 정보 수집 방식</a> |
<a href="#3-모델-학습">3. 모델 학습</a> |
<a href="#4-자세-탐지-로직-및-임계값">4. 자세 탐지 로직 및 임계값</a> |
<a href="#5-필터링-아키텍처">5. 필터링 아키텍처</a> |
<a href="#6-에이전트-구현-팁">6. 에이전트 구현 팁</a>
</p>

이 문서는 MediaPipe와 RANSAC 회귀 모델을 결합하여 단일 정면 카메라 환경에서 정밀한 상체 자세를 감지하는 시스템의 설계 사양서입니다. 다른 프로젝트에 이 로직을 적용하거나 코딩 에이전트가 시스템을 이해하는 데 최적화되어 있습니다.

---

## 1. 핵심 설계 철학
- **Depth Proxy**: 단일 RGB 카메라의 불안정한 깊이 추정 대신, **픽셀 상의 어깨 너비(Shoulder Width)**를 거리(깊이)의 독립 변수($x$)로 사용합니다.
- **Linear Calibration**: 어깨 너비(거리) 변화에 따른 **광대 너비(얼굴 크기)** 변화를 1차(선형) 함수($y = m x + b$)로 모델링하여 정상 자세의 기준점(Expected Value)을 동적으로 산출합니다.
- **Outlier Rejection**: 자세 맞춤 시 발생하는 사용자의 불필요한 움직임을 **RANSACRegressor**로 필터링하여, 어깨 너비에 따른 광대 너비의 순수 상관 관계 신호만 추출합니다.

---

## 2. 정보 수집 방식 (Data Collection)

### 2.1. 다단계 Move-Burst 수집 사이클
사용자의 거리별 데이터를 확보하기 위해 지정된 횟수만큼 샘플을 수집합니다. 횟수는 <a href="./posture_definition_criteria.json">baseline.capture.expected_samples</a>를 참조하십시오.
1.  **MOVE 단계**: 사용자에게 새로운 거리(앞 또는 뒤)로 이동하도록 요청합니다. 대기 시간은 <a href="./posture_definition_criteria.json">baseline.capture.wait_seconds</a>를 참조하십시오.
2.  **BURST 단계**: 해당 지점에 도달하면 지정된 시간 동안 고속으로 원시 프레임 데이터를 수집합니다. 수집 기간은 <a href="./posture_definition_criteria.json">baseline.capture.collect_seconds</a>를 참조하십시오.
3.  **데이터 처리**:
    *   수집 단계에서는 지연을 없애기 위해 **EMA/One Euro 필터를 비활성화**한 원시(Raw) 좌표를 사용합니다.
    *   버스트 구간의 모든 프레임 데이터(어깨 너비 및 광대 거리)를 필터링 없이 그대로 `dist_samples` 리스트에 저장합니다 (고밀도 데이터 확보).

### 2.2. 수집 대상 지표
- **독립 변수 ($x_1$, 어깨 감지 시)**: `shoulder_width` (랜드마크 11, 12번 사이의 유클리드 거리) - **거리(깊이) 척도**
- **독립 변수 ($x_2$, 어깨 미감지 대비)**: `eye_distance` (양안 중심 간 유클리드 거리) - **어깨 미감지 시 거리 척도**
- **종속 변수 ($y_1$)**: `cheek_distance` (랜드마크 234, 454번 사이의 유클리드 거리) - **기대 얼굴 크기 (`Shoulder-Cheek` 모델)**
- **종속 변수 ($y_2$)**: `head_height` (얼굴 높이 지표) - **기대 머리 높이 (`Shoulder-Height` 및 `Eye-Height` 모델)**

> **어깨 미감지 폴백(Fallback)**: 초기 자세 수집 시 어깨가 감지되지 않거나 유효 샘플이 부족하더라도 수집 실패로 처리하지 않으며, 어깨를 사용하지 않는 모델(`Eye-Height` 모델 및 홍채 기반 화면 얼굴 가까움 감지 모델)만 활성화하여 정상 동작합니다.

---

## 3. 모델 학습 (RANSAC Linear Regression)

수집된 고밀도 원시 데이터를 바탕으로 `scikit-learn`의 RANSAC 알고리즘을 수행합니다.

### 3.1. 학습 파이프라인
```python
# PolynomialFeatures(degree=1) + RANSACRegressor (Linear)
X = shoulder_widths.reshape(-1, 1) # 어깨 너비 (독립 변수)
y = cheek_distances               # 광대 거리 (종속 변수)
# 1차 선형 모델: y = m * x + b
model = make_pipeline(PolynomialFeatures(degree=1), RANSACRegressor())
model.fit(X, y)
```

### 3.2. RANSAC 사용 이유
- 사용자가 앞뒤로 이동하는 과정에서 고개를 숙이거나 어깨를 트는 등 **이상치(Outlier)** 데이터가 반드시 포함됩니다.
- RANSAC은 전체 데이터 중 모델에 부합하는 **Inliers(정상 자세에서의 어깨-광대 상관 관계)**만을 선택하여 회귀 곡선을 만들기 때문에, 수집 시 완벽한 자세를 유지하지 않아도 정밀한 모델링이 가능합니다.

---

## 4. 자세 탐지 로직 및 임계값 (Detection & Thresholds)

### 4.1. 기대치 계산 (Expected Value)
실시간 프레임에서 측정된 `shoulder_width`($x$)를 학습된 모델에 대입하여, 현재 거리에서 기대되는 **정상 광대 너비**($y_{expected}$)를 구합니다.
*   `expected_cheek = m * x + b`
*   `deviation (%) = (measured_cheek - expected_cheek) / expected_cheek`

### 4.2. 자세별 탐지 임계값 (Sensitivity)
시스템은 `deviation` 수치를 바탕으로 자세 가능도(Likelihood)를 산출합니다. 점수 범위 및 정규화 기준은 <a href="./posture_definition_criteria.json">frame_scoring</a> 설정을 따릅니다.

| 자세 유형 | 핵심 로직 | 허용 오차 (`scale`) | 확정 임계값 | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **기댄 자세 (Recline)** | 머리 높이 `deviation` < 0 (`Shoulder-Height` 또는 어깨 미감지 시 `Eye-Height` 모델) | <a href="../../../data/posture_definition_criteria.json">frame_scoring.sensitivities.recline</a> | <a href="../../../data/posture_definition_criteria.json">posture_types.recline.sustain_seconds</a> | 고개 숙임, 또는 얼굴 주변에 손이 감지(`hand_near_face`/`chin_occlusion`)되면서 어깨 선 기울기(<a href="../../../data/posture_definition_criteria.json">posture_types.recline.guards.max_shoulder_tilt</a>)가 함께 발생할 때만 판정 억제 (어깨 기울기 단독으로는 억제하지 않음) |
| **거북목 (Forward Head)** | 광대 거리 `deviation` > 0 (`Shoulder-Cheek` 모델) | <a href="../../../data/posture_definition_criteria.json">frame_scoring.sensitivities.forward_head</a> | <a href="../../../data/posture_definition_criteria.json">posture_types.forward_head.sustain_seconds</a> | 어깨-광대 비율 편차 기준으로 판정 |
| **화면 얼굴 가까움 (Eye Close)** | 홍채 기반 눈-화면 거리(`eye_screen_distance_cm`) ≤ 임계값 | <a href="../../../data/posture_definition_criteria.json">eye_monitoring.distance_threshold_cm</a> | <a href="../../../data/posture_definition_criteria.json">posture_types.eye_close.sustain_seconds</a> | 홍채 거리 알고리즘으로 단독 판정하며 피드백 메시지(<a href="../../../data/posture_definition_criteria.json">posture_types.eye_close.alert_message</a>) 제공 |
| **턱 괸 자세 (Chin Rest)** | 얼굴 주변 손 감지(`hand_near_face`/`chin_occlusion`) 시 복합 신호(눈 기울기 + 어깨 기울기 + 손-얼굴 점수) 평가 | - | <a href="../../../data/posture_definition_criteria.json">posture_types.chin_rest_estimated.sustain_seconds</a> | 어깨 기울기는 얼굴 주변에 손이 있을 때만 평가하며, 활성화 시 기댄 자세(`recline`)를 상호 배제 |

### 4.3. 홍채 기반 눈-화면 거리 산출 (Iris Screen Distance)
- **홍채 지름 추출**: MediaPipe FaceMesh의 홍채 중심점(468, 473)을 제외한 외곽 4점(좌: 469~472, 우: 474~477)의 실수 픽셀 좌표에서 두 대각선 길이 중 큰 값(가로 지름)을 추출합니다.
- **핀홀 카메라 거리 공식 및 곱셈 보정**:
  * `f_px = frame_width / (2 * tan(HFOV / 2))` (<a href="../../../data/posture_definition_criteria.json">eye_monitoring.camera_horizontal_fov_deg</a>)
  * `z_cm = ((iris_diameter_mm * f_px) / iris_px) / 10.0` (<a href="../../../data/posture_definition_criteria.json">eye_monitoring.iris_diameter_mm</a>)
  * 양안 평균 거리에 곱셈형 보정 계수(<a href="../../../data/posture_definition_criteria.json">eye_monitoring.distance_correction_scale</a>)를 곱해 최종 거리를 산출합니다.

---

## 5. 필터링 아키텍처

1.  **Stage 1: One Euro Filter**
    *   대상: 랜드마크 3D 좌표 (`x, y, z`)
    *   설정: <a href="./posture_definition_criteria.json">filters.one_euro</a>
    *   효과: 미세한 떨림(Jitter) 제거 및 실시간 반응성 확보.
2.  **Stage 2: EMA (Exponential Moving Average)**
    *   대상: 계산된 `MetricSnapshot` 및 `Likelihoods`
    *   설정: <a href="./posture_definition_criteria.json">filters.ema</a>
    *   효과: 수치 급변을 방지하고 부드러운 UI 갱신.

---

## 6. 에이전트 구현 팁
- **Calibration 시각화**: `ransac_fit_{현재시간}.png`를 통해 산출된 선형 곡선과 샘플 점들이 모델을 잘 따르는지 확인하십시오.
- **Normalization**: 모든 거리는 이미지 해상도에 독립적이도록 MediaPipe의 정규화 좌표(0.0~1.0)를 사용해야 합니다.
- **Fallback**: `scikit-learn`이 없는 환경을 대비해 `np.polyfit`을 이용한 최소자승법(Least Squares) 백업 로직을 구현하는 것이 좋습니다.
