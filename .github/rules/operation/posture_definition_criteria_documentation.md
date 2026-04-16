# 자세 판정 기준 JSON 문서

<p><a href="../../copilot-instructions.md">메인 지침</a> | <a href="../posture_definition.md">자세 정의서</a> | <a href="./posture_operation.md">운영 규칙</a></p>

## 목차
<p>
<a href="#1-관리-원칙">1. 관리 원칙</a> |
<a href="#2-json-최상위-키-설명">2. JSON 최상위 키 설명</a> |
<a href="#3-posture_types-키-설명">3. posture_types 키 설명</a> |
<a href="#4-수정-절차">4. 수정 절차</a> |
<a href="#5-검증-체크리스트">5. 검증 체크리스트</a> |
<a href="#6-예시-변경-시나리오">6. 예시 변경 시나리오</a> |
<a href="#7-운영-규칙-키-범위">7. 운영 규칙 키 범위</a> |
<a href="#8-관련-문서">8. 관련 문서</a> |
<a href="#9-json-스키마-검증-체크리스트운영용">9. JSON 스키마 검증 체크리스트</a> |
<a href="#10-json-로더-적용-규칙구현-기준">10. JSON 로더 적용 규칙</a> |
<a href="#11-참조-표기-규칙">11. 참조 표기 규칙</a>
</p>

- 기준 파일: <a href="./posture_definition_criteria.json">./posture_definition_criteria.json</a>
- 목적: 자세 판정 기준을 문서가 아닌 JSON 단일 소스로 관리하고, 팀이 같은 방식으로 수정하도록 한다.

## 1. 관리 원칙

- 임계값, 가중치, 지속 시간, 상태 전이 규칙은 JSON에만 작성한다.
- md 문서에는 설명과 참조만 남기고 수치 기준을 중복 기재하지 않는다.
- 코드에는 하드코딩된 판정 임계값을 두지 않고 JSON 로딩 결과를 사용한다.
- `primary_conditions`의 각 조건은 문자열 플레이스홀더를 사용하지 않고 객체 형태로 작성한다.
- 조건 객체는 기본적으로 `operator`와 `threshold` 또는 `threshold_percent`를 포함한다.
- `tuning_range_percent`는 운영 중 감도 조정을 위한 참고 범위이며, 기본 판정에는 `threshold_percent`를 사용한다.

## 2. JSON 최상위 키 설명

- `version`: 기준 포맷 버전
- `domain`: 기준이 적용되는 도메인 식별자
- `description`: 기준 파일 설명
- `baseline`: 개인 기준 자세 캘리브레이션 정의
- `global_rules`: 공통 지속 시간/상태 머신 규칙
- `posture_types`: 자세 유형별 판정 기준
- `frame_scoring`: 프레임 점수 범위와 가능도 계산식
- `event_judgment`: 즉시/확정 판정 방식
- `message_policy`: 사용자 메시지 표현 정책

### baseline.capture 하위 키

- `method`: baseline 수집 방식
- `duration_seconds`: baseline 수집 고정 시간(초)

## 3. posture_types 키 설명

- `recline`: 기댄 자세 관련 기준
- `forward_head`: 거북목 경향 기준
- `crossed_leg_estimated`: 다리 꼰 자세 추정 기준
- `chin_rest_estimated`: 턱 괸 자세 추정 기준

각 posture 항목 공통 키
- `display_label`: 사용자 표시 문구
- `primary_conditions`: 주 판정 조건
- `secondary_signals` 또는 `auxiliary_signals`: 보조 신호
- `sustain_seconds`: 확정 최소 지속 시간

### 3.0 primary_conditions 표현 규칙

- 퍼센트 기반 변화 조건은 아래 키를 사용한다.
  - `operator`: 비교 연산자(`>=`, `<=`, `>`, `<`)
  - `threshold_percent`: 기본 판정 임계값
  - `tuning_range_percent`(선택): 운영 조정 범위(`min`, `max`)
- 각도/거리 등 절대값 조건은 아래 키를 사용한다.
  - `operator`: 비교 연산자
  - `threshold`: 기본 판정 임계값
- 문자열 형태의 임시 키워드(예: `threshold_in_model`, `baseline_increase`)는 사용하지 않는다.

### 3.1 자세별 참조 키(표현 통일)

- 의자에 누운 자세
  - 임계값/보조 신호/지속 시간: `posture_types.recline.primary_conditions`, `posture_types.recline.secondary_signals`, `posture_types.recline.sustain_seconds`
- 거북목
  - 임계값/지속 시간: `posture_types.forward_head.primary_conditions`, `posture_types.forward_head.sustain_seconds`
- 다리 꼰 자세(추정)
  - 임계값/반복 창/지속 시간: `posture_types.crossed_leg_estimated.primary_conditions`, `posture_types.crossed_leg_estimated.secondary_signals`, `posture_types.crossed_leg_estimated.repeat_window_seconds`, `posture_types.crossed_leg_estimated.sustain_seconds`
- 턱 괸 자세(의심)
  - 임계값/보조 신호/지속 시간: `posture_types.chin_rest_estimated.primary_conditions`, `posture_types.chin_rest_estimated.auxiliary_signals`, `posture_types.chin_rest_estimated.sustain_seconds`

## 4. 수정 절차

1. JSON 파일에서 기준값을 수정한다.
2. 영향 받는 코드가 JSON 로딩 기반으로 동작하는지 확인한다.
3. md 문서는 수치 자체를 적지 않고 JSON 참조 상태만 확인한다.
4. 변경 사유와 테스트 결과를 구현/테스트 문서에 기록한다.

## 5. 검증 체크리스트

- 중복 기준이 md 또는 코드 상수로 남아 있지 않은가?
- `posture_types`의 모든 항목에 `display_label`과 `sustain_seconds`가 있는가?
- 퍼센트/임계값 키 이름이 기존 네이밍과 일치하는가?
- 상태 머신 전이가 서비스 로직과 충돌하지 않는가?

## 6. 예시 변경 시나리오

- 거북목 감도를 완화하려면
  - `posture_types.forward_head.primary_conditions`의 증가 퍼센트 임계값을 조정한다.
- 다리 꼰 자세 확정 시간을 늘리려면
  - `posture_types.crossed_leg_estimated.sustain_seconds`를 조정한다.

## 7. 운영 규칙 키 범위

- 판정 기준(임계값/가중치/지속 시간)은 아래 키 범위에서만 관리한다.
  - `baseline`
  - `posture_types`
  - `frame_scoring`
  - `event_judgment`
  - `global_rules`

## 8. 관련 문서

- <a href="../posture_definition.md">../posture_definition.md</a>
- <a href="./posture_operation.md">./posture_operation.md</a>
- <a href="./common.md">./common.md</a>

## 9. JSON 스키마 검증 체크리스트(운영용)

- 최상위 키 존재 여부
  - `version`, `domain`, `baseline`, `global_rules`, `posture_types`, `frame_scoring`, `event_judgment`, `message_policy`
- `posture_types` 공통 키 확인
  - 각 자세 항목에 `display_label`, `primary_conditions`, `sustain_seconds` 존재
- `primary_conditions` 값 타입 확인
  - 문자열 금지, 객체만 허용
- 조건 객체 규칙 확인
  - 퍼센트 조건: `operator` + `threshold_percent` 필수
  - 절대값 조건: `operator` + `threshold` 필수
  - `tuning_range_percent`는 선택이며, 사용할 경우 `min`, `max`를 함께 제공
- 연산자 값 검증
  - 허용값: `>=`, `<=`, `>`, `<`, `==`
- 범위 값 검증
  - 퍼센트는 0 이상
  - `tuning_range_percent.min <= tuning_range_percent.max`
- 시간 값 검증
  - `sustain_seconds`, `repeat_window_seconds`, `baseline.capture.duration_seconds`는 0보다 큰 수

## 10. JSON 로더 적용 규칙(구현 기준)

- 로딩 실패 시 기본값으로 침묵 대체하지 않고 명시적 예외를 발생시킨다.
- 스키마 검증 실패 시 어떤 키가 왜 실패했는지 경로 포함 메시지로 남긴다.
- 판정 로직은 아래 우선순위를 고정한다.
  - 1순위: `threshold` 또는 `threshold_percent`
  - 2순위: `tuning_range_percent`는 운영자 조정 UI/로그 참고용
- 로더는 JSON 원본을 수정하지 않고, 검증 완료된 읽기 전용 설정 객체를 반환한다.
- 환경별 튜닝이 필요하면 JSON 파일을 분리하고 런타임 병합 규칙을 문서화한다.

## 11. 참조 표기 규칙

- 경로 표기는 상대 경로를 기본으로 사용한다.
  - 같은 디렉토리: `./file.md`
  - 상위 디렉토리: `../folder/file.md`
- 경로 구분자는 항상 `/`를 사용하고, `\`는 사용하지 않는다.
- 드라이브 문자(`C:\`, `D:\`)나 절대 경로 표기는 문서에 사용하지 않는다.
- 파일을 가리키는 경로는 가능한 한 `<a href="...">...</a>` 형태의 링크로 표기한다.
- 디렉토리만 언급할 때도 상대 경로 표기를 유지한다.
  - 예: `.github/rules/ui/`
- JSON 참조 링크의 `href`는 파일 경로만 사용한다.
  - 예: <a href="./posture_definition_criteria.json">./posture_definition_criteria.json</a>
- 라인 번호 앵커(`#L10`)는 유지보수 시 깨지기 쉬우므로 사용하지 않는다.
- 링크 텍스트는 항상 키 경로를 사용한다.
  - 예: `posture_types.recline.primary_conditions.cheek_distance_baseline_change_percent.threshold_percent`
- 수치 기준을 설명할 때는 상위 묶음 키가 아니라 실제 수치 키를 우선 참조한다.
  - 권장: `...threshold`, `...threshold_percent`, `...sustain_seconds`, `...duration_seconds`
  - 비권장: `...primary_conditions`, `...posture_types`만 단독 표기
- 값이 배열/객체인 경우에도 텍스트에는 최소 1단계 이상 하위 키를 포함해 의미를 명확히 한다.
- 문서 내에서 동일 대상을 여러 번 참조해도 표기 형식(`파일 링크 + 키 경로 텍스트`)은 동일하게 유지한다.
