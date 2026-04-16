# 나쁜 자세 정의서 v0.1

<p><a href="../copilot-instructions.md">메인 지침</a> | <a href="./operation/common.md">로직 규칙</a> | <a href="./ui/common.md">UI 규칙</a></p>

## 목차
<p>
<a href="#1-목적">1. 목적</a> |
<a href="#2-공통-전제">2. 공통 전제</a> |
<a href="#3-나쁜-자세-정의">3. 나쁜 자세 정의</a> |
<a href="#4-운영-규칙-문서-분리">4. 운영 규칙 문서 분리</a> |
<a href="#5-후속-구현-메모">5. 후속 구현 메모</a> |
<a href="#6-빠른-기준표">6. 빠른 기준표</a>
</p>

- 프로젝트: MediaPipe 기반 상체 자세 측정(웹캠)
- 작성일: 2026-03-26

## 1. 목적

나쁜 자세를 규칙 기반으로 정의하고, 프레임 단위 및 시간 누적으로 판정하기 위한 기준을 정리한다.

판정 기준의 실제 수치/가중치/임계값은 md가 아니라 JSON에서만 관리한다.
참조: `./operation/posture_definition_criteria.json`
문서: `./operation/posture_definition_criteria_documentation.md`

## 2. 공통 전제

- 입력: 웹캠 정면 영상(어깨~머리 상체 중심)
- 제한 조건: 측면 카메라는 사용하지 않음(정면 단일 카메라 전용)
- 기본 랜드마크: 코, 양쪽 눈, 양쪽 광대, 양쪽 어깨
- 오탐 방지: 단일 프레임이 아니라 "지속 시간" 조건 함께 사용
  - 권장: 2~3초 이상 연속 조건 만족 시 나쁜 자세 판정

### 2.1 핵심 기준(정리본)

- 공통 baseline
  - 시작 시 기준 자세를 촬영하고 `cheek_distance`, `eye_distance`, `face_shoulder_ratio`를 baseline으로 저장
  - baseline 촬영 시간은 <a href="./operation/posture_definition_criteria.json">baseline.capture.duration_seconds</a>를 따른다.
- 거북목/누운 자세
  - 얼굴-어깨 비율 및 얼굴 거리 변화만 사용
  - 사용 지표: `cheek_distance`, `eye_distance`, `face_shoulder_ratio`
- 다리 꼰 자세/턱 괸 자세
  - 목-어깨 정렬 지표를 활용
  - 사용 지표: `shoulder_tilt_deg`, `neck_offset`, `eye_line_tilt`
  - 턱 괸 자세는 추가로 얼굴 가림(`chin_occlusion`)과 손-얼굴 근접(`hand_near_face`) 신호 활용

## 3. 나쁜 자세 정의

### 3.1 의자에 누운 자세(기댄 자세)

**의미**
- 상체가 뒤로 과하게 기대져 정렬이 무너진 상태

**관찰 포인트(정면 웹캠 기준, 추정)**
- 얼굴이 baseline보다 멀어짐: `cheek_distance` 또는 `eye_distance` 감소
- 얼굴/어깨 비율 변화: `face_shoulder_ratio = cheek_distance / shoulder_width`
- 어깨 기울기(`shoulder_tilt_deg`)는 보조 신호

**판정 예시**
- 자세 판정 임계값/보조 신호/지속 시간은 <a href="./operation/posture_definition_criteria.json">posture_types.recline.primary_conditions.cheek_distance_baseline_change_percent.threshold_percent</a>, <a href="./operation/posture_definition_criteria.json">posture_types.recline.secondary_signals</a>, <a href="./operation/posture_definition_criteria.json">posture_types.recline.sustain_seconds</a>를 따른다.

**한계/비고**
- 정면 단일 카메라에서는 뒤로 기대는 동작을 완벽히 분리하기 어려움
- 따라서 얼굴 거리 변화와 어깨 지표를 결합한 확률적 판정을 사용
- 즉, "정렬이 똑바른 채로 누운 자세"도 얼굴 멀어짐이 지속되면 감지 대상

---

### 3.2 거북목 자세

**의미**
- 머리가 어깨 중심선 대비 전방 또는 편위된 상태

**관찰 포인트**
- 얼굴이 baseline보다 가까워짐: `cheek_distance` 또는 `eye_distance` 증가
- `face_shoulder_ratio` 상승(머리가 카메라 쪽으로 전진하면 증가 경향)

**판정 예시**
- 자세 판정 임계값/지속 시간은 <a href="./operation/posture_definition_criteria.json">posture_types.forward_head.primary_conditions.cheek_distance_baseline_change_percent.threshold_percent</a>, <a href="./operation/posture_definition_criteria.json">posture_types.forward_head.primary_conditions.face_shoulder_ratio_baseline_change_percent.threshold_percent</a>, <a href="./operation/posture_definition_criteria.json">posture_types.forward_head.sustain_seconds</a>를 따른다.

**한계/비고**
- 정면 카메라 전용 환경에서는 전방/좌우 편위를 통합 지표로 운영
- 전방 이동은 얼굴 거리 변화(`cheek_distance`, `eye_distance`)와 얼굴-어깨 비율(`face_shoulder_ratio`) 중심으로 추정

---

### 3.3 다리 꼰 자세(어깨 높이 비대칭 기반 추정)

**의미**
- 하체 비대칭이 상체로 전달되어 좌우 어깨 높이가 달라진 상태를 추정

**관찰 포인트**
- `abs(shoulder_tilt_deg)` 증가
- `neck_offset` 증가가 함께 나타나면 비대칭 가능성 강화

**판정 예시**
- 자세 판정 임계값/반복 창/지속 시간은 <a href="./operation/posture_definition_criteria.json">posture_types.crossed_leg_estimated.primary_conditions.abs_shoulder_tilt_deg.threshold</a>, <a href="./operation/posture_definition_criteria.json">posture_types.crossed_leg_estimated.secondary_signals</a>, <a href="./operation/posture_definition_criteria.json">posture_types.crossed_leg_estimated.repeat_window_seconds</a>, <a href="./operation/posture_definition_criteria.json">posture_types.crossed_leg_estimated.sustain_seconds</a>를 따른다.

**한계/비고**
- 원인은 다리 꼰 자세 외에도 팔 사용, 책상 높이, 카메라 각도 등이 가능
- 결과 문구는 "다리 꼰 자세 추정" 또는 "골반/하체 비대칭 의심" 권장

---

### 3.4 턱 괸 자세

**의미**
- 손/팔로 턱을 받쳐 머리 정렬이 무너진 상태

**관찰 포인트(현재 랜드마크 기준 제한적)**
- 머리 기울기(`eye_line_tilt`) 증가
- 한쪽 어깨 상승 + 머리 편위 동시 발생
- 턱 라인/하안면 가림 증가(`chin_occlusion`)
- 손목/손가락 랜드마크가 얼굴 영역 근처에서 지속 검출(`hand_near_face`)

**판정 예시(제한적 휴리스틱)**
- 자세 판정 임계값/보조 신호/지속 시간은 <a href="./operation/posture_definition_criteria.json">posture_types.chin_rest_estimated.primary_conditions.eye_line_tilt_deg.threshold</a>, <a href="./operation/posture_definition_criteria.json">posture_types.chin_rest_estimated.primary_conditions.shoulder_tilt_deg.threshold</a>, <a href="./operation/posture_definition_criteria.json">posture_types.chin_rest_estimated.primary_conditions.neck_offset_baseline_change_percent.threshold_percent</a>, <a href="./operation/posture_definition_criteria.json">posture_types.chin_rest_estimated.auxiliary_signals</a>, <a href="./operation/posture_definition_criteria.json">posture_types.chin_rest_estimated.sustain_seconds</a>를 따른다.

**한계/비고(중요)**
- 정확도 향상을 위해 손/팔 랜드마크(손목, 팔꿈치)와 얼굴 가림률 계산 필요
- 권장 확장: MediaPipe Pose의 `wrist`, `elbow` 사용

**구현용 계산 정의(추가)**
- 손-얼굴 근접, 턱 가림, 점수화 계산식의 실제 수식과 임계값은 <a href="./operation/posture_definition_criteria.json">posture_types.chin_rest_estimated.auxiliary_signals.hand_near_face.threshold</a>, <a href="./operation/posture_definition_criteria.json">posture_types.chin_rest_estimated.auxiliary_signals.chin_occlusion.threshold</a>, <a href="./operation/posture_definition_criteria.json">posture_types.chin_rest_estimated.auxiliary_signals.chin_occlusion.fallback.landmark_count_near_chin.threshold</a>를 따른다.

## 4. 운영 규칙 문서 분리

- 점수화/판정 운영 규칙은 별도 문서에서 관리한다.
- 참조: `./operation/posture_operation.md`
- 판정 기준(임계값/가중치/지속 시간)은 JSON의 `baseline`, `posture_types`, `frame_scoring`, `event_judgment`, `global_rules`에서만 관리한다.
- 참조: `./operation/posture_definition_criteria.json`

## 5. 후속 구현 메모

- baseline 캘리브레이션(개인별 기준) 필수: 시작 시 5초 수집 결과로 baseline 고정
- 이동평균/중앙값 필터로 랜드마크 노이즈 완화
- 턱 괸 자세 정확도 개선을 위해 손/팔 랜드마크 추가

## 6. 빠른 기준표

| 자세 유형 | 핵심 지표 | 예시 임계값 | 최소 지속 시간 | 출력 문구 |
|---|---|---|---|---|
| 의자에 누운 자세 | cheek_distance 감소(1차), face_shoulder_ratio/shoulder_tilt_deg(보조) | `posture_types.recline.primary_conditions` | `posture_types.recline.sustain_seconds` | 기댄 자세 의심 |
| 거북목 | cheek_distance 증가, eye_distance 증가, face_shoulder_ratio | `posture_types.forward_head.primary_conditions` | `posture_types.forward_head.sustain_seconds` | 거북목 경향 |
| 다리 꼰 자세(추정) | shoulder_tilt_deg, neck_offset | `posture_types.crossed_leg_estimated.primary_conditions` | `posture_types.crossed_leg_estimated.sustain_seconds` | 다리 꼰 자세 추정 |
| 턱 괸 자세(의심) | eye_line_tilt, shoulder_tilt_deg, neck_offset, chin_occlusion/hand_near_face | `posture_types.chin_rest_estimated.primary_conditions` | `posture_types.chin_rest_estimated.sustain_seconds` | 턱 괸 자세 의심 |
