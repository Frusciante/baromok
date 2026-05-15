# Phase 7: 자세 측정 시스템 기술 사양 정렬 및 안정화 계획

## 1. 개요
`.github/rules/operation/posture_system_summary.md`에 정의된 기술 사양과 실제 구현 코드(`src/core/`) 간의 불일치를 해소하고, 발견된 버그를 수정하여 시스템의 기술적 완성도를 높인다.

## 2. 현황 분석 및 문제점
- **버그**: `JudgmentEngine` 클래스에서 `drift_gate_k` 변수가 `__init__`에서 초기화되지 않은 채 `judge_single_frame`에서 사용되고 있음 (AttributeError 위험).
- **공식 불일치**: `posture_system_summary.md`의 편차 계산식과 `JudgmentEngine`의 실제 정규화 점수 계산식(`sensitivity`, `scale_factor` 포함) 간의 설명 수준 차이 발생.
- **사양 미흡**: `posture_system_summary.md`에서 권장하는 "특정 라이브러리 부재 시 Fallback" 로직이 일부 모듈에만 적용되어 있음.
- **시각화 정렬**: `camera_worker.py`의 디버그 오버레이 항목이 기술 사양서의 설명과 100% 일치하도록 보강 필요.

## 3. 작업 항목

### 3.1 JudgmentEngine 안정화 (`src/core/judgment_engine.py`)
- `drift_gate_k` 초기화 로직 추가 (설정 파일 `posture_definition_criteria.json`에서 로드).
- `_judge_forward_head`, `_judge_recline` 등의 점수 계산 로직이 `posture_system_summary.md`의 "Depth Proxy" 및 "Dynamic Calibration" 철학을 정확히 반영하는지 재검토 및 주석 보강.

### 3.2 기술 사양서 동기화 (`.github/rules/operation/posture_system_summary.md`)
- 실제 코드의 고급 정규화 공식(`sensitivity`, `scale_factor` 포함)을 기술 사양서에 더 구체적으로 기술하여 에이전트가 오해하지 않도록 업데이트.
- `drift_gate`의 역할과 작동 방식(거리 이동 시 오탐 방지)에 대한 설명 보강.

### 3.3 Fallback 및 예외 처리 강화
- `baseline_manager.py` 등에서 RANSAC 학습 실패 시나리오에 대한 안전 장치(Default Ratio 사용 등)가 모든 경로에서 작동하는지 확인.

### 3.4 디버그 오버레이 고도화 (`src/core/camera_worker.py`)
- 기술 사양서에 명시된 "RANSAC 기대 곡선 대비 현재 편차(Delta)"를 시각적으로 더 명확하게 표시하도록 오버레이 텍스트 정리.

## 4. 작업 체크리스트
- [ ] `JudgmentEngine.__init__`에 `drift_gate_k` 로드 로직 추가
- [ ] `posture_system_summary.md` 수식 설명 업데이트
- [ ] `camera_worker.py` 디버그 텍스트 포맷 정렬
- [ ] 모든 거리/지표 계산의 해상도 독립성(Resolution Independence) 재검증

## 5. 다음 단계
- 구현 계획 승인 후 `02_implementation_result.md` 작성 및 코드 반영
- 통합 테스트(`test_phase6_algorithm_v1.py` 확장)를 통한 검증
