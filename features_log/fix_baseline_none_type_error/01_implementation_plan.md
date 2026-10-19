# 자세 측정 시 None 지표로 인한 TypeError 해결 구현 계획서

## 1. 개요
현재 바른 자세(Baseline) 측정 중이나 자세 재측정 시에, 카메라 프레임으로부터 수집되는 일부 지표(`shoulder_width`, `cheek_distance`, `head_height`, `eye_distance` 등)가 순간적으로 측정 실패하여 `None` 값으로 저장될 수 있습니다. 
이때 수집을 완료하는 과정(`finish_baseline_collection` 및 `_compute_baseline_metrics`)에서 RANSAC 모델 피팅을 위해 유효 데이터를 걸러내는 조건식(`getattr(frame, "...", 0) > 0`)이 실행됩니다. `getattr`은 속성값이 명시적으로 `None`일 때 기본값 `0`이 아닌 `None`을 그대로 반환하므로, 결국 `None > 0` 비교가 수행되어 `TypeError: '>' not supported between instances of 'NoneType' and 'int'` 에러가 발생합니다.
이 계획서는 이를 방지하기 위해 `None` 처리를 안전하게 검증하는 예외 처리를 추가하고 안정성을 확보하는 내용을 담고 있습니다.

## 2. 변경 대상 및 범위
- **핵심 로직**: `src/core/baseline_manager.py`
  - `BaselineManager.__init__`에서 `data_dir` 인자가 `str` 문자열로 전달될 경우에도 `Path`로 안전하게 변환하여 `mkdir()`이 정상 작동하도록 수정 (안정성 증대 및 테스트 코드 호환).
  - `finish_baseline_collection` 내의 RANSAC 모델 피팅(Shoulder-Cheek, Shoulder-Height, Eye-Height) 3개 조건문에서 각 지표가 `None`이 아님을 먼저 검증하도록 수정.
  - `_compute_baseline_metrics` 내의 메트릭 생성부 3개 조건문에서도 동일하게 각 지표가 `None`이 아님을 먼저 검증하도록 수정.
- **문서화**:
  - `.github/operation-implementation-checklist.md` 업데이트 (동작 구현 체크리스트에 안정성 관련 반영).

## 3. 상세 구현 계획

### 3.1 `src/core/baseline_manager.py` 수정

#### 1) 생성자 수정 (안전하게 `Path` 변환)
```python
    def __init__(self, config: ConfigManager, data_dir: Optional[Path] = None):
        self.config = config
        self.data_dir = Path(data_dir) if data_dir is not None else DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
```

#### 2) `finish_baseline_collection` 조건식 변경
```python
        # 1. Shoulder-Cheek 모델 피팅
        sc_x, sc_y, s_indices = [], [], []
        for frame in self.collection_frames:
            sw = getattr(frame, "shoulder_width", None)
            cd = getattr(frame, "cheek_distance", None)
            if sw is not None and sw > 0 and cd is not None and cd > 0:
                sc_x.append(sw)
                sc_y.append(cd)
                s_indices.append(getattr(frame, "step_index", 0))
```
*(Shoulder-Height 및 Eye-Height 피팅 조건식도 동일하게 `None` 체크를 수행하도록 변경)*

#### 3) `_compute_baseline_metrics` 조건식 변경
```python
        # 1. Shoulder-Cheek 샘플
        sc_x, sc_y, s_samples = [], [], []
        for frame in self.collection_frames:
            sw = getattr(frame, "shoulder_width", None)
            cd = getattr(frame, "cheek_distance", None)
            if sw is not None and sw > 0 and cd is not None and cd > 0:
                sc_x.append(sw)
                sc_y.append(cd)
                s_samples.append(getattr(frame, "step_index", 0))
```
*(Shoulder-Height 및 Eye-Height 샘플 수집 조건식도 동일하게 `None` 체크를 수행하도록 변경)*

## 4. 기대 효과
- 랜드마크 추출 실패 등의 원인으로 어깨 너비나 얼굴 관련 지표가 순간적으로 `None` 값을 가지더라도, 프로그램이 Crash되지 않고 정상적으로 나머지 유효 데이터만 선별하여 자세 수집을 완수할 수 있습니다.
- 특히 자세 재측정 시에 빈번하게 발생하던 예외가 근본적으로 해결됩니다.

## 5. 검증 계획
- **자동화 테스트 검증**: `python -m test.test_phase7_shoulder_cheek_model`을 가상환경에서 실행하여 기존 RANSAC 적합 로직에 문제가 없는지 1차 확인합니다.
- **예외 시나리오 검증**: 테스트 코드에 지표가 `None`인 비정상 프레임을 명시적으로 삽입하고, `finish_baseline_collection`이 정상 작동(에러 없이 예외 데이터를 스킵하고 진행)하는지 검증합니다.
