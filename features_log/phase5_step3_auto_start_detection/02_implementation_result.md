# Phase 5-3단계 구현 결과: 자동 감지 시작

**작성일**: 2026-05-09  
**단계**: Phase 5 (검증/최적화) - Step 3

---

## 구현 완료 항목

### ✅ Baseline 완료 후 자동 감지 시작 분기 추가
**파일**: `src/ui/app.py`

#### 변경 사항
1. `baseline_captured_signal` 연결 대상을 람다에서 새 핸들러로 변경
2. `_handle_baseline_captured()` 메서드 추가
3. `auto_start_detection` 값에 따라 다음 동작 분기

#### 핵심 로직
```python
def _handle_baseline_captured(self):
    """Baseline 완료 후 다음 동작 처리"""
    if self.settings_config.auto_start_detection:
        logger.info("자동 감지 시작 설정 활성화: 바로 감지 시작")
        self._start_detection()
    else:
        self.switch_screen(1)  # HubScreen으로 이동
```

---

## 동작 요약

### auto_start_detection = True
- Baseline 촬영 완료 직후 감지 시작
- Hub 화면을 거치지 않음
- `_start_detection()` 재사용으로 기존 감지 초기화 흐름 유지

### auto_start_detection = False
- 기존과 동일하게 Hub 화면으로 이동
- 수동 감지 시작 버튼 사용 가능

---

## 검증된 효과

- `SettingsConfig.auto_start_detection`이 런타임에서 바로 반영됨
- Baseline 완료 시 자동/수동 흐름이 명확하게 분기됨
- 기존 수동 시작 동작은 변경하지 않음

---

## 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/ui/app.py` | Baseline 완료 핸들러 추가, signal 연결 변경 |

---

## 참고

이 단계는 설정 저장값이 실제 동작으로 연결되는 마지막 핵심 보완 중 하나이며, Phase 5-2의 알림음 구현과 함께 사용자 개입 없이 감지 시작을 제어할 수 있게 만들었다.
