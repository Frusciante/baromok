# Phase 5-3단계 테스트 계획 및 결과: 자동 감지 시작

**작성일**: 2026-05-09  
**단계**: Phase 5 (검증/최적화) - Step 3

---

## 테스트 계획

### Test 1: auto_start_detection=False 기본 동작

**목적**: Baseline 완료 후 기존처럼 Hub로 이동하는지 확인

**예상 결과**:
- `switch_screen(1)` 호출
- `_start_detection()` 미호출

### Test 2: auto_start_detection=True 자동 시작 동작

**목적**: Baseline 완료 후 자동으로 감지가 시작되는지 확인

**예상 결과**:
- `_start_detection()` 호출
- `switch_screen(1)` 미호출

### Test 3: signal wiring 확인

**목적**: `baseline_captured_signal`이 새 핸들러를 통해 분기하는지 확인

**예상 결과**:
- `baseline_captured_signal.emit()` 후에도 Test 2와 동일한 분기 결과

---

## 테스트 결과

### 실행 환경
- OS: Windows
- Python: 3.12.3
- Qt: offscreen 모드

### 실행 방법
- `baromokApp` 인스턴스 생성
- `app._start_detection`과 `app.switch_screen`을 더미 함수로 대체
- `app._handle_baseline_captured()` 직접 호출
- `app.baseline_screen.baseline_captured_signal.emit()`로 연결 검증

### 실제 결과

| # | 테스트 | 결과 |
|---|-------|------|
| 1 | auto_start_detection=False | PASS: `false_screen_calls=[1]`, `false_start_calls=0` |
| 2 | auto_start_detection=True | PASS: `true_start_calls=1`, `true_screen_calls=[]` |
| 3 | signal wiring 확인 | PASS: `signal_start_calls=1`, `signal_screen_calls=[]` |

### 상세 결과

```text
false_start_calls=0
false_screen_calls=[1]
true_start_calls=1
true_screen_calls=[]
signal_start_calls=1
signal_screen_calls=[]
```

---

## 결론

### 구현 상태
✅ 완료

### 검증 상태
- 구문 검증: PASS
- 기능 검증: PASS
- signal 연결 검증: PASS

### 최종 판단
`auto_start_detection` 설정값이 Baseline 완료 시점에 실제 동작으로 반영된다.
