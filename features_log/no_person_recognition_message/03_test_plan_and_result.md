# 테스트 계획 및 결과: 사용자 미탐지 문구 표시

**작성일**: 2026-05-13  
**대상**: 초기 자세 감지 / 메인 감지 공통

---

## 테스트 계획

### Test 1: 초기 자세 촬영 화면 미탐지 문구
- `indicators=None` 프레임에서 `인식이 어렵습니다` 문구가 표시되는지 확인
- 유효 지표 프레임으로 전환되면 문구가 사라지는지 확인

### Test 2: 초기 자세 촬영 워밍업 경계
- 워밍업 구간에서도 `indicators=None`이면 문구가 유지되는지 확인

### Test 3: 메인 감지 화면 미탐지 문구
- `indicators=None` 프레임에서 `인식이 어렵습니다` 문구가 표시되는지 확인
- 유효 지표 프레임으로 전환되면 문구가 사라지는지 확인

### Test 4: 런타임 임포트 확인
- 수정된 UI 모듈이 정상적으로 import 되는지 확인
- 새 문구 상수가 로딩되는지 확인

---

## 테스트 결과

### 실행 환경
- OS: Windows
- Python: 3.12.3
- Qt: `offscreen`

### 실행 방법
- `QApplication`을 offscreen으로 생성
- `BaselineScreen`과 `DetectionScreen`을 더미 객체로 생성
- `indicators=None` / 유효 `PostureIndicators`를 직접 주입
- 라벨 텍스트 상태를 비교

### 실제 결과

| # | 테스트 | 결과 |
|---|-------|------|
| 1 | 초기 자세 촬영 화면 미탐지 문구 | PASS |
| 2 | 초기 자세 촬영 워밍업 경계 | PASS |
| 3 | 메인 감지 화면 미탐지 문구 | PASS |
| 4 | 런타임 임포트 확인 | PASS |

### 상세 결과

```text
baseline_missing_text=True
baseline_present_text=True
detection_missing_text=True
detection_present_text=True
import_message=인식이 어렵습니다
```

### 보조 검증
- `python -m py_compile src/ui/screens/__init__.py` 통과
- `from src.ui.screens import RECOGNITION_DIFFICULT_MESSAGE` import 통과

---

## 결론

### 구현 상태
✅ 완료

### 검증 상태
- 초기 자세 촬영 화면: PASS
- 메인 감지 화면: PASS
- 모듈 임포트: PASS

### 최종 판단
사용자 미탐지 시 `인식이 어렵습니다` 문구가 초기 자세 감지와 메인 감지 양쪽에서 모두 동작한다.
