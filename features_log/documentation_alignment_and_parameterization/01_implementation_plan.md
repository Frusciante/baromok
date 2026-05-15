# 문서화 및 파라미터화 (Documentation Alignment & Parameterization)

**상태**: ⏳ 진행 중

## 1. 개요
프로젝트의 운영 규칙과 기술 사양을 일원화하고, 모든 하드코딩된 수치를 JSON 설정으로 이전하여 시스템의 유지보수성과 유연성을 확보한다.

## 2. 주요 작업 내용
### 2.1 문서 통합 및 현지화
- [x] `posture_system_summary.md`를 프로젝트 문서 스타일로 재작성 및 한국어화
- [x] `common.md`에 핵심 기술 원칙 통합
- [x] `GEMINI.md`, `README.md`, `posture_definition.md` 등 프로젝트 전반의 문서 동기화

### 2.2 하드코딩 수치 제거 (Parameterization)
- [x] 모든 마크다운 문서에서 구체적인 수치(초, %, 단계 등) 제거 및 JSON 참조로 대체
- [x] `posture_definition_criteria.json`을 단일 소스(Single Source of Truth)로 고도화
- [x] 파이썬 코드(`JudgmentEngine`, `IndicatorCalculator`, `BaselineScreen`)에서 하드코딩된 상수를 JSON 로딩 값으로 대체

### 2.3 20단계 RANSAC 캘리브레이션 정렬
- [x] 기술 사양(Summary)에 맞게 20단계 수집 사이클로 코드 및 문서 정렬
- [x] MOVE(5초) / BURST(1초) 타이밍 적용

## 3. 구현 세부 계획
### Step 1: 문서 구조 정립
- `posture_system_summary.md`에 네비게이션 헤더 및 목차 추가
- `common.md`에 알고리즘 핵심 원칙 섹션 추가

### Step 2: JSON 스키마 확장
- `baseline.capture` 하위 키 확장 (`wait_seconds`, `collect_seconds`, `expected_samples`, `minimum_valid_frames`)
- `frame_scoring` 하위 키 확장 (`likelihood_weights`, `ratio_scale_k`, `drift_gate_k`, `score_normalization_max`, `hand_face_weights`)

### Step 3: 코드 반영
- `BaselineScreen.py`: JSON 기반 동적 UI 로직 구현
- `JudgmentEngine.py`: 파라미터화된 판정 로직 반영
- `IndicatorCalculator.py`: 가중치 기반 지표 계산 반영

## 4. 검증 계획
- [ ] JSON 설정 변경 시 UI 문구 및 타이머가 정상적으로 업데이트되는지 확인
- [ ] 20단계 캘리브레이션 프로세스가 누락 없이 진행되는지 확인
- [ ] 하드코딩된 숫자가 문서에 남아 있는지 전수 검사
