# 랜드마크 인식 기준 완화 및 설정 분리 구현 계획서

## 1. 개요
현재 `src/core/landmark_extractor.py`에 하드코딩된 MediaPipe 랜드마크 인식 임계값(0.7)이 너무 엄격하여 고개를 약간만 들어도 얼굴 인식이 끊기는 문제가 발생하고 있습니다. 이를 해결하기 위해 인식 기준을 완화하고, 관련 설정값을 외부 JSON 파일(`posture_definition_criteria.json`)로 분리하여 관리 효율성을 높입니다.

## 2. 변경 대상 및 범위
- **기준 파일**: `.github/rules/operation/posture_definition_criteria.json`
  - MediaPipe 모델별 임계값 설정을 위한 `mediapipe` 키 추가.
- **설정 관리**: `src/config.py`
  - 추가된 `mediapipe` 설정을 로드할 수 있도록 `ConfigManager` 및 관련 로직 업데이트.
- **핵심 로직**: `src/core/landmark_extractor.py`
  - 하드코딩된 `0.7` 값을 제거하고 `ConfigManager`를 통해 동적으로 임계값을 로드하도록 수정.
  - 인식 기준 완화 (0.7 -> 0.5 또는 0.6 예정).
- **문서화**: 
  - `.github/operation-implementation-checklist.md` 업데이트.
  - `.github/rules/operation/posture_definition_criteria_documentation.md` 업데이트 (필요 시).

## 3. 상세 구현 계획

### 3.1 JSON 설정 추가 (`posture_definition_criteria.json`)
```json
{
  "mediapipe": {
    "face": {
      "min_detection_confidence": 0.5,
      "min_presence_confidence": 0.5
    },
    "pose": {
      "min_detection_confidence": 0.5,
      "min_presence_confidence": 0.5
    },
    "hand": {
      "min_detection_confidence": 0.5,
      "min_presence_confidence": 0.5
    }
  }
}
```

### 3.2 설정 관리자 수정 (`src/config.py`)
- `ConfigManager`에 `get_mediapipe_config()` 메서드 추가.

### 3.3 랜드마크 추출기 수정 (`src/core/landmark_extractor.py`)
- `LandmarkExtractor.__init__`에서 `ConfigManager`를 주입받거나 내부에서 참조하여 설정 로드.
- `_initialize_models` 메서드에서 설정된 임계값 사용.

## 4. 기대 효과
- 고개 들기 등 각도 변화 시에도 안정적인 얼굴 인식 유지.
- 필터링(One Euro Filter, EMA)이 이미 존재하므로 완화에 따른 노이즈는 충분히 억제 가능.
- 하드코딩 제거를 통해 향후 튜닝 및 관리 용이성 확보.

## 5. 검증 계획
- **정상 작동 확인**: 얼굴 인식이 끊기던 각도에서 인식이 유지되는지 확인.
- **노이즈 영향 확인**: 인식 기준 완화로 인해 랜드마크가 심하게 튀지 않는지(필터링이 잘 작동하는지) 확인.
- **설정 로드 확인**: JSON 파일 수정 시 실제 프로그램에 반영되는지 확인.
