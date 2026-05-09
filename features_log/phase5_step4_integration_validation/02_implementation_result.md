# Phase 5-4단계 구현 결과: 통합 검증

**작성일**: 2026-05-09  
**단계**: Phase 5 (검증/최적화) - Step 4

---

## 구현 완료 항목

### ✅ 통합 검증 환경 구성
- `baromokApp` 인스턴스를 offscreen 모드로 실행
- 핵심 컴포넌트를 spy 함수로 대체하여 호출 순서와 결과를 확인
- 실제 카메라/세션/사운드 재생 없이 흐름만 검증

### ✅ 검증한 흐름
1. Baseline 완료 후 자동 시작/수동 이동 분기
2. 감지 시작 시 상태 초기화 및 세션 시작
3. 감지 중지 시 세션 종료 및 화면 복귀
4. 경고 팝업 표시 및 알림음 호출
5. 설정 저장/로드 round-trip

---

## 핵심 검증 결과

### 1. Baseline 완료 후 흐름
- `auto_start_detection=False`
  - `switch_screen(1)` 호출 확인
  - `_start_detection()` 미호출 확인
- `auto_start_detection=True`
  - `_start_detection()` 호출 확인
  - `switch_screen(4)`로 감지 화면 전환 확인

### 2. 감지 시작 흐름
- `state_machine.reset()` 1회 호출
- `session_manager.start_session()` 1회 호출
- `camera_worker.start()` 1회 호출
- `switch_screen(4)` 호출 확인

### 3. 경고 팝업 흐름
- 팝업 표시 확인
- 타이머 4000ms 활성화 확인
- `sound_manager.play_alert(55)` 호출 확인
- 팝업 위치가 상단 설정에 맞게 반영됨 확인

### 4. 감지 중지 흐름
- `camera_worker.stop_capture()` 1회 호출
- `session_manager.end_session()` 1회 호출
- `switch_screen(1)` 호출 확인
- 팝업 숨김 호출 확인

### 5. 설정 저장/로드 흐름
- `SettingsConfig.save_to_json()` 후 `load_from_json()` round-trip 성공
- 저장한 값들이 동일하게 복원됨 확인

---

## 대표 결과값

```text
baseline_false_switch=[1]
baseline_true_switch=[4]
baseline_true_reset=1
baseline_true_start_session=1
baseline_true_camera_start=1
alert_visible=True
alert_timer_active=True
alert_timer_ms=4000
alert_sound_calls=[55]
alert_position=(639, 120)
stop_camera_stop=1
stop_end_session=1
stop_switch=[4, 1]
settings_roundtrip=True
```

---

## 결론

### 구현 상태
✅ 완료

### 검증 상태
- Baseline 분기: PASS
- 감지 시작/중지: PASS
- 경고 팝업/알림음: PASS
- 설정 저장/로드: PASS

### 최종 판단
Phase 5-1, 5-2, 5-3에서 연결한 설정값과 동작이 통합 흐름에서도 충돌 없이 동작한다.
