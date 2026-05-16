# Prototype Integration Summary

이 문서는 `baromok_prototype/`에 있던 알고리즘을 현재 애플리케이션에 어떻게 통합했는지 요약합니다.

## 핵심 통합 포인트

- `baromok_prototype/posture_monitor_app/monitor.py`의 계산 아이디어(OneEuroFilter, EMA, RANSAC 기반 2차 모델, 점수화 공식을)가 `src`의 핵심 모듈로 통합되어 있습니다.
  - 좌표/지표 필터: `src/utils/helpers.py`의 `OneEuroFilter`, `EMAFilter`
  - 랜드마크 추출: `src/core/landmark_extractor.py` (MediaPipe Tasks)
  - 지표 계산: `src/core/indicator_calculator.py`
  - Baseline / RANSAC 관리: `src/core/baseline_manager.py` (`RansacQuadraticModel` 사용)
  - 판정 로직: `src/core/judgment_engine.py` (프로토타입 가중치 및 점수식을 반영)

## UI 적응

- prototype의 CLI 전용 UI(START/RESET 버튼 등)는 직접 복사하지 않았습니다.
- PyQt 기반의 `BaselineScreen`에서 다단계 캘리브레이션 플로우(이동 대기 + 데이터 수집)를 구현하여 사용자가 이동 및 정지를 안내받도록 구성했습니다.
- 단계 수와 각 단계별 시간 설정은 <a href="../.github/rules/operation/posture_definition_criteria.json">baseline.capture</a>를 참조하십시오.
- 캘리브레이션 중 프레임 수집은 `BaselineManager`로 전달되며, 수집 완료 후 RANSAC 모델을 학습합니다.

## 재사용 가능한 계산 모듈

- 프로토타입의 핵심 계산(비율 예측, 점수화, 필터링)은 이미 아래 모듈로 분리되어 있어 그대로 재사용 가능합니다:
  - `src/utils/helpers.py` (필터, RANSAC 모델 래퍼)
  - `src/core/indicator_calculator.py` (거리/각도/점수용 입력 지표 계산)
  - `src/core/judgment_engine.py` (점수화 및 판정)
  - `src/core/baseline_manager.py` (샘플 수집, RANSAC 모델 핸들링, baseline 저장/로딩)

## 권장 추가 작업 (선택)

- `baromok_prototype/monitor.py`의 `_fit_quadratic_ransac`에서 사용하는 RANSAC 세부 파라미터(`residual_threshold`, `z_ransac_threshold` 등)를 `src/config.py`로 노출하여 사용자 설정으로 바꾸기.
- `baromok_prototype/algorithm_reference.md`의 수식과 파라미터를 `docs/` 하위로 옮겨 프로젝트 문서와 버전 관리를 통합하기.

## 실행 및 테스트 팁

- 기존 실행: `python main.py` (UI에서 캘리브레이션 → 감지 흐름 사용)
- 프로토타입 원본을 로컬에서 별도 실행하려면 `baromok_prototype/README.md`의 지침을 참고하세요.

