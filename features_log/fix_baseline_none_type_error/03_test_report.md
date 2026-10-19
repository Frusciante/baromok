# 자세 측정 시 None 지표 예외 처리 테스트 계획 및 결과 보고서

## 1. 테스트 계획

### 1.1 개요
본 테스트는 `src/core/baseline_manager.py`의 RANSAC 모델 적합 연산 중 발생할 수 있는 지표 `None` 누락 예외의 정상 스킵 기능과 코드 충돌(Crash) 방지 효과를 검증하는 것을 목적으로 합니다.

### 1.2 테스트 대상
- [baseline_manager.py](file:///D:/2026-1/CD/baromok/src/core/baseline_manager.py)
  - `finish_baseline_collection` (RANSAC 피팅 시 지표 필터링 및 적합)
  - `_compute_baseline_metrics` (최종 메트릭용 샘플 수집)

### 1.3 테스트 방법
- 테스트 스크립트 실행: `$env:PYTHONPATH="."; .\venv\Scripts\python.exe test/test_phase7_shoulder_cheek_model.py`

### 1.4 테스트 케이스
| ID | 테스트 항목 | 설명 | 기대 결과 |
|---|---|---|---|
| TC-1 | 정상 RANSAC 적합 검증 | 모든 프레임에 유효한 자세 지표(어깨 너비, 뺨 거리 등)가 포함된 경우 피팅 완료 처리 검증 | 3개 RANSAC 모델 피팅 완료 및 `True` 반환 |
| TC-2 | None 지표 예외 스킵 검증 | 일부 프레임에 지표를 `None`으로 전달하더라도, 예외가 발생하지 않고 이를 정상적으로 스킵한 후 남은 유효 데이터로 모델을 적합시키는지 검증 | `TypeError` 발생 없이 남은 15개 샘플로 피팅 완료 및 `True` 반환 |

---

## 2. 테스트 수행 결과

### 2.1 수행 로그 요약
- **수행 환경**: Windows 11 / Python 3.12 (venv 가상환경)
- **수행 일시**: 2026-07-07 00:38:44 KST
- **결과 요약**: 2/2 테스트 케이스 전원 통과 (Passed)

#### 상세 로그
```text
[INFO] BaselineManager 초기화 완료 (data_dir: data_test)
[INFO] Baseline 수집 시작
[INFO] Baseline 수집 완료: 15 프레임 (설정 샘플 단계: 5, 최소 필요 10)
[INFO] Shoulder-Cheek 모델 피팅 완료 (15 샘플)
[INFO] 디버그 플롯 저장 완료: data_test\debug_plots\shoulder_cheek\fit_20260707_003846.png
[INFO] Shoulder-Height 모델 피팅 완료 (15 샘플)
[INFO] 디버그 플롯 저장 완료: data_test\debug_plots\shoulder_height\fit_20260707_003846.png
[INFO] Eye-Height 모델 피팅 완료 (15 샘플)
[INFO] 디버그 플롯 저장 완료: data_test\debug_plots\eye_height\fit_20260707_003846.png
[INFO] Baseline 메트릭 계산 및 저장 완료
✓ Test 1 통과

[INFO] BaselineManager 초기화 완료 (data_dir: data_test)
[INFO] Baseline 수집 시작
[INFO] Baseline 수집 완료: 20 프레임 (설정 샘플 단계: 5, 최소 필요 10)
[INFO] Shoulder-Cheek 모델 피팅 완료 (15 샘플)
[INFO] 디버그 플롯 저장 완료: data_test\debug_plots\shoulder_cheek\fit_20260707_003846.png
[INFO] Shoulder-Height 모델 피팅 완료 (15 샘플)
[INFO] 디버그 플롯 저장 완료: data_test\debug_plots\shoulder_height\fit_20260707_003846.png
[INFO] Eye-Height 모델 피팅 완료 (15 샘플)
[INFO] 디버그 플롯 저장 완료: data_test\debug_plots\eye_height\fit_20260707_003846.png
[INFO] Baseline 메트릭 계산 및 저장 완료
✓ Test 2 통과 (None 지표 예외 처리 정상 작동)

============================================================
Phase 7: Shoulder-Cheek Model Verification (Debug)
============================================================
Result: 2/2 Tests Passed
============================================================
```

### 2.2 결론 및 안정성 평가
- 수집된 데이터에 어깨 너비나 얼굴 관련 지표가 누락(`None`)되어 있는 최악의 상황에서도, `TypeError`를 발생시키지 않고 정상적으로 필터링하여 RANSAC 피팅 및 메트릭 산출을 완료하는 것을 확인하였습니다.
- 이로써 측정 시 인물이 프레임을 벗어나거나 인식이 일시 중단되더라도 프로그램이 크래시되지 않는 강력한 내성을 확인하였습니다.
