# Phase 5-3단계 구현 계획: 자동 감지 시작

**작성일**: 2026-05-09  
**단계**: Phase 5 (검증/최적화) - Step 3  
**예상 기간**: 1-2시간

---

## 목차

1. [목표 및 범위](#목표-및-범위)
2. [현재 상태](#현재-상태)
3. [상세 구현 계획](#상세-구현-계획)
4. [데이터 흐름](#데이터-흐름)
5. [검증 전략](#검증-전략)

---

## 목표 및 범위

### 목표
Baseline 촬영이 완료되면 설정값에 따라 Hub를 거치지 않고 자동으로 감지를 시작

### 범위

| 항목 | 현재 상태 | 변경 후 | 우선순위 |
|------|----------|--------|---------|
| **Baseline 완료 후 자동 시작** | 미구현 | 구현 | ⭐⭐⭐ |
| **설정값 auto_start_detection 반영** | 저장만 됨 | 실제 동작에 반영 | ⭐⭐⭐ |
| **기존 수동 시작 흐름 유지** | 유지 | 유지 | ⭐⭐⭐ |

---

## 현재 상태

### 설정값 (이미 구현됨)
✅ `SettingsConfig.auto_start_detection`: True/False  
✅ SettingsScreen의 자동 시작 토글  
✅ `_save_settings()`를 통한 JSON 저장

### 현재 동작
- Baseline 촬영 완료 시 무조건 Hub 화면으로 이동
- Hub에서 사용자가 직접 "감지 시작" 버튼을 눌러야 감지 시작

---

## 상세 구현 계획

### 1. Baseline 완료 처리 분기 추가

**파일**: `src/ui/app.py`

현재 연결:
```python
self.baseline_screen.baseline_captured_signal.connect(
    lambda: self.switch_screen(1)  # Hub로 이동
)
```

변경 방향:
```python
self.baseline_screen.baseline_captured_signal.connect(
    self._handle_baseline_captured
)
```

새 메서드:
```python
def _handle_baseline_captured(self):
    """Baseline 완료 후 다음 동작 처리"""
    if self.settings_config.auto_start_detection:
        logger.info("자동 감지 시작 설정 활성화: 바로 감지 시작")
        self._start_detection()
    else:
        self.switch_screen(1)  # Hub
```

### 2. 설정값 즉시 반영 유지

- `_save_settings()`는 이미 `self.settings_config`를 업데이트함
- 따라서 설정 변경 후 다음 Baseline 완료 시 즉시 반영 가능
- 별도 캐싱 없이 런타임 값 참조

### 3. 수동 시작 흐름 유지

- `auto_start_detection=False`면 기존과 동일하게 Hub로 이동
- Hub의 "감지 시작" 버튼은 그대로 사용 가능

---

## 데이터 흐름

### auto_start_detection=True
```
Baseline 촬영 완료
  ↓
baseline_captured_signal
  ↓
_handle_baseline_captured()
  ↓
self.settings_config.auto_start_detection == True
  ↓
self._start_detection()
  ↓
상태 머신 초기화 + 세션 시작 + 카메라 시작
  ↓
Detection 화면 전환
```

### auto_start_detection=False
```
Baseline 촬영 완료
  ↓
baseline_captured_signal
  ↓
_handle_baseline_captured()
  ↓
self.settings_config.auto_start_detection == False
  ↓
self.switch_screen(1)
  ↓
Hub 화면 유지
```

---

## 검증 전략

### 정적 검증
- [ ] `_handle_baseline_captured()` 메서드 추가 확인
- [ ] signal 연결이 새 메서드를 가리키는지 확인
- [ ] 구문 오류 없음

### 기능 검증
- [ ] auto_start_detection=True → Baseline 완료 후 자동 감지 시작
- [ ] auto_start_detection=False → 기존처럼 Hub 이동
- [ ] 설정 변경 후 다음 Baseline에 즉시 반영

### 부작용 검증
- [ ] 수동 시작 버튼 정상 동작 유지
- [ ] 감지 중지 로직 영향 없음

---

## 예상 변경 파일

| 파일 | 변경 타입 | 설명 |
|------|---------|------|
| `src/ui/app.py` | 수정 | Baseline 완료 분기, 새 핸들러 추가 |
| `features_log/phase5_step3_auto_start_detection/02_implementation_result.md` | 신규 | 구현 결과 문서 |
| `features_log/phase5_step3_auto_start_detection/03_test_plan_and_result.md` | 신규 | 테스트 계획/결과 문서 |

---

## 위험 요소 및 대응

| 위험 | 심각도 | 대응 |
|------|--------|------|
| Baseline 직후 바로 감지 시작으로 UI 전환이 빠름 | 🟢 낮음 | 기존 `_start_detection()` 흐름 재사용 |
| 설정값 변경 반영 누락 | 🟢 낮음 | `self.settings_config`를 런타임 참조 |
| 수동/자동 흐름 충돌 | 🟢 낮음 | 분기만 추가하고 기존 경로 유지 |

---

## 다음 단계

1. ✅ 구현 계획서 작성
2. 👉 구현 진행
3. 정적 검증
4. 기능 테스트
5. 결과 문서 작성
6. Git 커밋

---

## 구현 체크리스트

- [ ] baseline 완료 핸들러 추가
- [ ] signal 연결 변경
- [ ] 구문 검증
- [ ] 자동 시작 동작 확인
- [ ] 수동 시작 동작 확인
- [ ] 결과 문서 작성
