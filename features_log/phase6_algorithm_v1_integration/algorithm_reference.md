# Posture Monitor Algorithm Reference (v1.0)

이 문서는 단일 정면 RGB 카메라(웹캠)를 이용하여 사용자의 상체 자세를 모니터링하는 시스템의 핵심 알고리즘과 수학적/논리적 구조를 AI 에이전트 및 개발자가 이해하기 쉽도록 문서화한 것입니다.

## 1. System Architecture & Data Flow

시스템은 다음 파이프라인을 거쳐 프레임 단위 데이터를 처리합니다.
1. **Inference:** MediaPipe Tasks (Face, Pose, Hand Landmarkers) 동시 실행
2. **Coordinate Extraction:** 주요 Keypoint 추출
3. **1st Stage Filtering:** (Removed in v1.1) 원시 좌표에 대한 One-Euro 필터 제거 — 현재는 MediaPipe에서 제공하는 원시 정규화 좌표를 그대로 사용합니다. 필요 시 지표(level) 또는 UI 레이어에서 별도 평활화(EMA 등)를 적용할 것을 권장합니다.
4. **Metric Calculation:** 정규화된 거리, 각도, 비율 연산
5. **2nd Stage Filtering:** (Removed in v1.1) 연산된 지표에 대한 EMA 평활화는 기본 파이프라인에서 제거되었습니다. 지표 안정화가 필요하면 별도의 모듈이나 시각화 레이어에서 선택적으로 적용하세요.
6. **Calibration/Prediction:** RANSAC 2차 곡선 모델을 통한 기대 비율(`Expected Ratio`) 예측
7. **Scoring:** 기준값 대비 오차를 바탕으로 각 자세(거북목, 기댄 자세 등)별 점수 산출
8. **State Machine:** 시간 지속 조건(Temporal Thresholding)을 통한 최종 상태 확정

---

## 2. Signal Filtering Algorithms (Updated)

원래 이 프로젝트는 프레임 단위의 미세 떨림을 억제하기 위해 좌표 레벨(One-Euro)과 지표 레벨(EMA)의 이중 필터링을 사용했습니다. 그러나 설계 변경에 따라 2026-06-02부로 기본 파이프라인에서 모든 자동 평활화(One-Euro, EMA)를 제거하고 MediaPipe가 제공하는 원시 정규화 좌표(raw normalized coordinates)를 사용하도록 했습니다.

이 변경의 주요 이유:
- 필터는 반응성(특히 One-Euro의 파라미터)에 따라 지연을 유발할 수 있으며, 특정 사용자/환경에서 보정이 어렵습니다.
- Baseline(재측정) 수집 시 원시 값을 그대로 수집하는 것이 데이터의 신뢰성과 재현성에 유리합니다.
- 시스템 복잡도를 낮추고, 평활화가 필요할 경우 상위 레이어(지표 계산 또는 UI)에 책임을 명확히 위임하기 위함입니다.

권장 사항:
- 실시간 UI에서의 시각적 안정성을 위해 필요하면 UI 레이어에서 `EMA(alpha=0.1~0.2)` 같은 경량 평활화를 적용하십시오.
- 알고리즘 파라미터 튜닝이 필요한 경우, 지표(level) 단위로 선택적 EMA를 적용하거나, 사용자 설정으로 토글 가능한 필터 모듈을 분리해 두는 것이 안전합니다.

히스토리(참고):
- 이전(버전 v1.0): One-Euro(좌표 레벨) + EMA(지표 레벨)
- 현재(버전 v1.1): 기본 파이프라인에서 필터 제거, 원시 좌표 사용

---

## 3. Calibration: RANSAC Quadratic Modeling (원근 왜곡 보정)

단일 카메라의 깊이 추정이 부정확한 문제를 해결하기 위해, 픽셀 상의 **어깨 너비(Shoulder Width)**를 깊이의 대리 지표(Depth Proxy)로 사용하는 수학적 모델을 적용했습니다.

### 3.1. 원리 (Shoulder Width vs Expected Ratio)
- 카메라에서 멀어지면 어깨 너비(Pixel)가 작아짐.
- 원근 왜곡(Perspective Distortion)으로 인해 멀어질수록 `얼굴 너비 / 어깨 너비` 비율(`face_shoulder_ratio`)도 함께 작아지는 현상을 모델링.
- 사용자가 아주 가까운 거리부터 팔이 닿지 않을 정도의 거리까지 총 6단계로 나누어 이동하며 `(x: shoulder_width, y: face_shoulder_ratio)` 샘플을 수집.
- 각 단계마다 3초의 이동 대기 시간 후 5초간 가만히 정지한 상태로 데이터를 수집하는 방식으로 진행하여 안정적인 곡선 피팅 데이터 확보.

### 3.2. 알고리즘: RANSAC + Polynomial Features
- `scikit-learn`의 `RANSACRegressor`와 `PolynomialFeatures(degree=2)` 파이프라인 사용.
- **이유:** 사용자가 움직이는 과정에서 발생하는 이상치(Outlier)를 RANSAC이 걸러내고, 정상적인 점들만 모아 완벽한 2차 곡선(포물선) `y = ax^2 + bx + c` 를 추정.
- **결과 예측:** 실시간 측정된 어깨 너비(`x`)를 이 함수에 대입하면, 현재 거리에서 정상적인 정렬을 유지할 때 기대되는 얼굴 비율(`Expected Ratio`)을 정확히 산출함.

---

## 4. Key Metrics Calculation

랜드마크(0~1 정규화 좌표)를 바탕으로 다음 지표들을 계산합니다.

### 4.1. Distances (유클리드 거리)
- `cheek_distance`: 왼쪽 광대(234)와 오른쪽 광대(454) 사이의 거리. (얼굴 크기 척도)
- `shoulder_width`: 왼쪽 어깨(11)와 오른쪽 어깨(12) 사이의 거리.

### 4.2. Ratios & Angles
- `face_shoulder_ratio`: `cheek_distance / shoulder_width`. (가장 중요한 형태 지표)
- `shoulder_tilt_deg`: 양어깨 선의 기울기(각도).
- `eye_line_tilt`: 양쪽 눈의 기울기(각도).
- `neck_offset`: `abs(코 x좌표 - 양어깨 중점 x좌표) / shoulder_width`. (목의 좌우 쏠림 정도)

### 4.3. Hand-Face Interaction (턱 괸 자세 판정용)
- 손목(0), 검지 끝(8)과 얼굴의 근접도(`near_score`) 및 턱 가림 정도(`occlusion_score`)를 측정.
- 얼굴 중앙과 턱끝(152)을 기준으로 반경 안에 들어온 픽셀 개수를 통해 `hand_face_score` (0~1) 산출.

---

## 5. Posture Scoring Logic (자세 점수화 모델)

각 자세 이탈 점수(0.0 ~ 1.0)는 베이스라인(초기 정상 상태) 및 예측된 `Expected Ratio`와의 오차를 통해 계산됩니다.

### 5.1. Forward Head (거북목 경향)
- **조건:** 얼굴이 예상보다 커짐(가까워짐) + 비율이 `Expected Ratio`보다 붕괴(커짐).
- **계산식:** `0.3 * face_near_score + 0.7 * ratio_up_score`
- 허용 오차(`scale` 상수)를 아주 타이트하게(e.g., 0.08~0.10) 조여 미세한 목 내밈도 잡아냄.

### 5.2. Reclined Posture (기댄 자세 / 의자에 눕기)
- **조건:** 얼굴이 예상보다 작아짐(멀어짐) + 비율이 `Expected Ratio`보다 붕괴(작아짐).
- **계산식:** `0.3 * face_far_score + 0.7 * ratio_down_score`

### 5.3. Chin Rest (턱 괸 자세)
- **조건:** 손-얼굴 근접 + 목 쏠림 + 어깨 기울어짐 + 시선 기울어짐 동시 발생.
- **계산식:** `0.35*eye_tilt + 0.2*shoulder_tilt + 0.15*neck_offset + 0.3*hand_face`

---

## 6. State Machine & Event Confirmation (상태 제어)

순간적인 점수 상승으로 인한 오탐(False Positive)을 막기 위해 Time-based State Machine을 운영합니다.

1. **Thresholds (임계값):**
   - 경고(Warning) 진입: `0.45`
   - 나쁜 자세(Bad Posture) 확정 점수: `0.60` (각 개별 이벤트는 `0.55`)
2. **Temporal Validation (지속 시간 검증):**
   - 산출된 점수가 임계값을 초과하더라도 즉시 알리지 않음.
   - `min_duration_sec` (예: 1.5초) 이상 해당 점수를 연속 유지해야 확정(Confirmed) 이벤트로 인정.
3. **State Hysteresis (상태 쿨다운):**
   - 상태가 변경되면(예: NORMAL -> BAD_POSTURE) 최소 `1.8초`(`min_state_hold_sec`) 동안 상태를 유지하여 UI 깜빡임 방지.