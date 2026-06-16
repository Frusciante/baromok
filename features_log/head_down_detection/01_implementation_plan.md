# 고개 숙임(Head Down) 감지 기능 구현 계획

## 1. 개요 (Objective)
베이스라인 수집 시 사용자의 평균 얼굴 상하 기울기(Pitch 각도)를 계산하여 저장하고, 실시간 감지 시 이 베이스라인 각도와 비교하여 고개를 숙인 자세를 판정하는 기능을 구현합니다.

## 2. 주요 변경 파일 및 컨텍스트
- **`src/core/landmark_extractor.py`**: 이마(Forehead, 10번) 랜드마크 추출 로직 추가 및 Z좌표 보존
- **`src/core/indicator_calculator.py`**: `face_pitch_deg` (얼굴 상하 기울기 각도) 지표 계산 로직 추가
- **`src/core/baseline_manager.py`**: 베이스라인 수집 항목에 `face_pitch_deg` 추가 및 `baseline.json`에 저장
- **`src/core/judgment_engine.py`**: `HEAD_DOWN` 자세 타입 추가
- **`src/core/judge_workers.py`**: `HeadDownWorker` 신규 클래스 구현 및 매니저 등록
- **`data/posture_definition_criteria.json`**: `head_down` 자세의 감도, 임계값, 경고 메시지 등 설정 추가

## 3. 세부 구현 단계 (Implementation Steps)

### 단계 1: 랜드마크 확장 및 지표 계산
1. `src/core/landmark_extractor.py`의 `get_relevant_landmarks`에 이마 포인트(10번) 추출 추가.
   - `forehead` 키로 3D 좌표 (x, y, z) 보존.
2. `src/core/indicator_calculator.py`에서 `PostureIndicators` 데이터 클래스에 `face_pitch_deg: float = 0.0` 속성 추가.
3. `calculate_all_indicators` 메서드에서 이마와 턱의 y, z 좌표 차이를 이용해 `face_pitch_deg = np.degrees(np.arctan2(delta_z, delta_y))` 계산.

### 단계 2: 베이스라인 평균 각도 저장
1. `src/core/baseline_manager.py`의 `_compute_baseline_metrics` 메서드의 `indicator_names` 리스트에 `face_pitch_deg` 추가.

### 단계 3: 판정 엔진 및 워커 구현
1. `src/core/judgment_engine.py`의 `PostureType` Enum에 `HEAD_DOWN = "head_down"` 추가.
2. `src/core/judge_workers.py`에 `HeadDownWorker(BaseJudgeWorker)` 클래스 구현.
3. `PostureJudgeManager`의 `_initialize_workers`에 `HeadDownWorker` 등록.

### 단계 4: 설정 파일 업데이트
1. `data/posture_definition_criteria.json` 수정.
   - `baseline.metrics`에 `"face_pitch_deg"` 추가.
   - `posture_types` 영역에 `"head_down"` 객체 신설.
   - `frame_scoring.sensitivities` 및 `likelihood_weights`에 `head_down` 항목 추가.
