# 자세 측정 시 None 지표로 인한 TypeError 해결 구현 결과서

## 1. 개요
바른 자세(Baseline) 측정 및 자세 재측정 중, 순간적인 랜드마크 추출 실패로 인해 지표에 `None` 값이 삽입될 때 발생하던 `TypeError: '>' not supported between instances of 'NoneType' and 'int'` 문제를 해결하고 코드의 안정성을 확보하였습니다.

## 2. 변경 대상 및 범위
- **[baseline_manager.py](file:///D:/2026-1/CD/baromok/src/core/baseline_manager.py)**
  - `__init__` 생성자에서 `data_dir`의 타입이 `str`인 경우에도 예외 없이 `Path` 객체로 자동 변환하여 예기치 않은 디렉토리 생성 오류(`mkdir`)를 미연에 방지하였습니다.
  - `finish_baseline_collection` 내의 RANSAC 피팅 루프 3개에서 지표(어깨 너비, 뺨 거리, 머리 높이, 눈 거리)가 `None`인 경우 이를 무시하도록 안전한 null-check (`is not None`)를 강화하였습니다.
  - `_compute_baseline_metrics` 내의 RANSAC 샘플 수집부에서도 동일하게 안전한 null-check를 적용하였습니다.
- **[operation-implementation-checklist.md](file:///D:/2026-1/CD/baromok/.github/operation-implementation-checklist.md)**
  - 테스트 및 회귀 위험 점검에 대한 검증 사항을 완료 상태로 갱신하였습니다.

## 3. 상세 수정 내용

### 3.1 `src/core/baseline_manager.py` 수정 코드
- RANSAC 적합을 위해 프레임을 순회하는 조건식에서 `None` 체크를 명확히 하도록 하였습니다.
```python
        # 예시: Shoulder-Cheek 모델 피팅 시 필터링 로직
        for frame in self.collection_frames:
            sw = getattr(frame, "shoulder_width", None)
            cd = getattr(frame, "cheek_distance", None)
            if sw is not None and sw > 0 and cd is not None and cd > 0:
                sc_x.append(sw)
                sc_y.append(cd)
                s_indices.append(getattr(frame, "step_index", 0))
```
- Shoulder-Height 및 Eye-Height에 대해서도 동일하게 지표 유효성을 `is not None and > 0` 조건식으로 분리하여 안전성을 확보했습니다.

## 4. 검증 요약
- 테스트 코드 [test_phase7_shoulder_cheek_model.py](file:///D:/2026-1/CD/baromok/test/test_phase7_shoulder_cheek_model.py)를 최신 자세 측정 명세에 맞춰 리팩토링하고, `None` 지표를 강제로 주입한 비정상 프레임 수집 상황을 검증하는 테스트 케이스를 새로 추가하였습니다.
- 가상환경 실행 검증을 완료하였으며, 모든 테스트 케이스가 통과하는 것을 확인하였습니다.
