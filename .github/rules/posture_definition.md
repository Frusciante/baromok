# 나쁜 자세 정의서

<p><a href="../copilot-instructions.md">메인 지침</a> | <a href="./operation/common.md">로직 규칙</a> | <a href="./ui/common.md">UI 규칙</a></p>

## 목차
<p>
<a href="#목적">목적</a> |
<a href="#공통-전제">공통 전제</a> |
<a href="#나쁜-자세-정의">나쁜 자세 정의</a> |
<a href="#운영-규칙-문서-분리">운영 규칙 문서 분리</a> |
<a href="#후속-구현-메모">후속 구현 메모</a> |
<a href="#빠른-기준표">빠른 기준표</a>
</p>

## 목적

나쁜 자세를 규칙 기반으로 정의하고, 프레임 단위 및 시간 누적으로 판정하기 위한 기준을 정리합니다.
판정 기준의 실제 수치 및 임계값은 JSON에서 단일 소스로 관리합니다.
참조: <a href="./operation/posture_definition_criteria.json">./operation/posture_definition_criteria.json</a>

## 공통 전제

- **입력**: 웹캠 정면 영상 (상체 중심)
- **제한**: 정면 단일 카메라 전용
- **지표**: 코, 눈, 광대, 어깨 등 주요 랜드마크 활용
- **판정**: 단일 프레임이 아닌 지속 시간 조건을 함께 적용하여 오탐 방지

### 핵심 기준

- **공통 Baseline (자세 맞춤)**
  - 거리별 다단계 데이터를 수집하여 신체 지표 간의 관계를 학습합니다.
  - 상세 기술 사양: <a href="./operation/posture_system_summary.md">./operation/posture_system_summary.md</a>
  - 설정 참조: <a href="./operation/posture_definition_criteria.json">baseline.capture</a>
- **자세별 지표 활용**
  - 거북목/기댄 자세: 얼굴-어깨 비율 및 거리 변화 추적
  - 비대칭 자세: 목-어깨 정렬 및 기울기 지표 활용
  - 턱 괸 자세: 얼굴 가림 및 손-얼굴 근접 신호 활용

---

## 나쁜 자세 정의

### 의자에 누운 자세 (기댄 자세)
- **의미**: 상체가 뒤로 과하게 기대진 상태
- **관찰**: 얼굴이 기준점보다 멀어지거나 얼굴-어깨 비율이 감소함
- **판정**: 임계값 및 지속 시간은 <a href="./operation/posture_definition_criteria.json">posture_types.recline</a>을 참조하십시오.

### 거북목 자세
- **의미**: 머리가 전방으로 편위된 상태
- **관찰**: 얼굴이 기준점보다 가까워지거나 얼굴-어깨 비율이 상승함
- **판정**: 임계값 및 지속 시간은 <a href="./operation/posture_definition_criteria.json">posture_types.forward_head</a>를 참조하십시오.

### 턱 괸 자세
- **의미**: 손이나 팔로 턱을 받친 상태
- **관찰**: 머리 기울기 증가, 얼굴 영역 가림, 손-얼굴 근접 신호 검출
- **판정**: 임계값 및 보조 신호 기준은 <a href="./operation/posture_definition_criteria.json">posture_types.chin_rest_estimated</a>를 참조하십시오.

## 운영 규칙 문서 분리

- 점수화 및 판정 운영 규칙은 별도 문서에서 상세히 다룹니다.
- 참조: <a href="./operation/posture_operation.md">./operation/posture_operation.md</a>

## 빠른 기준표

| 자세 유형 | 핵심 지표 | 판정 기준 참조 | 지속 시간 참조 |
| :--- | :--- | :--- | :--- |
| **기댄 자세** | 머리 높이 감소, 거리 변화 | JSON 참조 | JSON 참조 |
| **거북목** | 비율 증가, 거리 변화 | JSON 참조 | JSON 참조 |
| **턱 괸 자세** | 손-얼굴 근접, 가림, 기울기 | JSON 참조 | JSON 참조 |

� |

