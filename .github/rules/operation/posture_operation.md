# 자세 측정 운영 규칙

<p><a href="../../copilot-instructions.md">메인 지침</a> | <a href="../posture_definition.md">자세 정의서</a> | <a href="../ui/posture_ui.md">UI 세부 규칙</a></p>

## 목차
<p>
<a href="#프레임-점수">프레임 점수</a> |
<a href="#이벤트-판정">이벤트 판정</a> |
<a href="#상태-머신">상태 머신</a> |
<a href="#구현-체크포인트">구현 체크포인트</a>
</p>

- 판정 기준의 실제 수치 및 임계값은 JSON에서 통합 관리합니다.
- 기준 파일: <a href="../../../data/posture_definition_criteria.json">../../../data/posture_definition_criteria.json</a>
- 기준 문서: <a href="./posture_definition_criteria_documentation.md">./posture_definition_criteria_documentation.md</a>

## 프레임 점수

- 프레임 점수 범위와 자세별 가능도 계산식은 아래 설정을 따릅니다.
- 참조: <a href="../../../data/posture_definition_criteria.json">frame_scoring</a>

## 이벤트 판정

- 즉시 판정 및 확정 판정(지속 시간 조건 등) 기준은 아래 설정을 따릅니다.
- 참조: <a href="../../../data/posture_definition_criteria.json">event_judgment</a> 및 <a href="../../../data/posture_definition_criteria.json">posture_types</a>

## 상태 머신

- 상태 머신의 상태 정의 및 전이 규칙은 아래 설정을 따릅니다.
- 참조: <a href="../../../data/posture_definition_criteria.json">global_rules.state_machine</a>

## 구현 체크포인트

- 시간 누적 조건을 적용하여 판정의 안정성을 확보합니다.
- Baseline 대비 변화량을 모든 계산의 기준으로 유지합니다.
- 환경 변화에 대응 가능하도록 임계값 조정을 고려합니다.
- 모델 파일은 개별적으로 분리하여 관리합니다.
