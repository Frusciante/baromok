# Phase 5-4단계 테스트 계획 및 결과: 통합 검증

**작성일**: 2026-05-09  
**단계**: Phase 5 (검증/최적화) - Step 4

---

## 테스트 계획

### Test 1: Baseline 완료 후 자동 시작 분기
- `auto_start_detection=False`일 때 Hub로 이동하는지 확인
- `auto_start_detection=True`일 때 감지가 자동 시작되는지 확인

### Test 2: 감지 시작 흐름
- 상태 머신 초기화
- 세션 시작
- 카메라 워커 시작
- Detection 화면 전환

### Test 3: 경고 팝업/알림음 흐름
- 팝업 표시
- 알림음 호출
- 팝업 자동 닫기 타이머 적용
- 팝업 위치 반영

### Test 4: 감지 중지 흐름
- 카메라 워커 중지
- 세션 종료
- Hub 화면 복귀

### Test 5: 설정 저장/로드 round-trip
- 임시 JSON 파일 저장
- 다시 로드하여 값 일치 확인

---

## 테스트 결과

### 실행 환경
- OS: Windows
- Python: 3.12.3
- Qt: offscreen 모드

### 실행 방법
- `baromokApp` 인스턴스 생성
- 핵심 메서드를 spy 함수로 교체
- 각 흐름을 직접 호출하여 결과 확인

### 실제 결과

| # | 테스트 | 결과 |
|---|-------|------|
| 1 | Baseline 완료 후 자동 시작 분기 | PASS |
| 2 | 감지 시작 흐름 | PASS |
| 3 | 경고 팝업/알림음 흐름 | PASS |
| 4 | 감지 중지 흐름 | PASS |
| 5 | 설정 저장/로드 round-trip | PASS |

### 상세 결과

```text
baseline_false_switch=[1]
baseline_false_start_session=0
baseline_true_switch=[4]
baseline_true_reset=1
baseline_true_start_session=1
baseline_true_camera_start=1
alert_visible=True
alert_timer_active=True
alert_timer_ms=4000
alert_sound_calls=[55]
alert_position=(639, 120)
alert_hide_calls=1
stop_camera_stop=1
stop_end_session=1
stop_switch=[4, 1]
stop_hide_calls=2
settings_roundtrip=True
settings_roundtrip_values={'notification_interval': 45, 'sound_volume': 25, 'popup_auto_close': False, 'auto_start_detection': True}
```

---

## 결론

### 구현 상태
✅ 완료

### 검증 상태
- 통합 흐름: PASS
- 경고 표시/음성: PASS
- 설정 저장/로드: PASS

### 최종 판단
Phase 5에서 적용한 설정값 연동이 실제 앱 흐름 전체에서 안정적으로 작동한다.

---

## 2026-05-10 추가 검증 계획 및 결과 (설정/통계 화면 복구)

### 테스트 계획

### Test A: 설정 화면 위젯 렌더링 및 상호작용
- 설정 화면에서 카테고리 전환 버튼(알림/소리/팝업/자동 시작)이 정상 전환되는지 확인
- 각 카테고리에서 토글/슬라이더/라디오 위젯이 노출되는지 확인

### Test B: 설정 저장 및 재시작 유지
- 설정값 변경 후 확인 버튼으로 저장
- 앱 재실행 후 변경값이 유지되는지 확인

### Test C: 통계 화면 차트 렌더링
- 통계 화면 진입 시 placeholder가 아닌 실제 차트가 표시되는지 확인
- 세션 데이터 존재 시 라인 데이터가 반영되는지 확인

### Test D: 팝업 위치 값 정합성
- `popup_position=center` 설정 시 중앙 표시 확인
- `popup_position=top` 설정 시 상단 표시 확인

---

### 실행 결과

| # | 테스트 | 결과 | 비고 |
|---|-------|------|------|
| A | 설정 화면 위젯 렌더링 및 상호작용 | PASS(코드/심볼 확인) | `QStackedWidget`, 설정 위젯 연결 코드 HEAD 반영 확인 |
| B | 설정 저장 및 재시작 유지 | 미수행 | 실제 UI 상호작용 기반 수동 확인 필요 |
| C | 통계 화면 차트 렌더링 | PASS(코드/심볼 확인) | `StatisticsLineChart` 연결 코드 HEAD 반영 확인 |
| D | 팝업 위치 값 정합성 | PARTIAL | 값 체계(`center/top`) 정합화 완료, 실제 위치 수동 확인 필요 |

### 근거
- 앱 실행 확인: `python main.py` 종료 코드 `0`
- 코드 반영 확인: `git show HEAD:src/ui/screens/__init__.py`에서 아래 심볼 확인
	- `NotificationSettingsWidget`
	- `SoundSettingsWidget`
	- `PopupSettingsWidget`
	- `AutoStartSettingsWidget`
	- `StatisticsLineChart`
	- `QStackedWidget`
- 데이터 생성 확인
	- `data/baseline.json`
	- `data/sessions/session_d3f31c73-c303-4040-bb86-123f753ddd8a.json`

---

### 추가 결론
- 이번 복구의 핵심인 "설정 화면 위젯 연결"과 "통계 차트 연결"은 코드 기준으로 반영 완료 상태다.
- 저장 유지(B)와 실제 팝업 좌표(D)는 UI 조작 기반 수동 검증 1회가 필요하다.
- 통계 화면은 현재 세션별 유지율 막대, 평균선, 최신 세션 강조, 날짜 라벨을 포함한 집계 카드 형태로 표시된다.

---

## 문서 마감

### 마감 상태
- 조건부 마감 (코드 반영 검증 완료, UI 수동 검증 대기)

### 마감 판단 근거
- 복구 대상 코드가 HEAD 기준으로 반영되어 있고, 앱 실행 명령(`python main.py`)이 정상 종료됨
- 데이터 파일 생성(`baseline/session`)으로 기본 실행 흐름은 확인됨

### 잔여 리스크
- 설정 저장 후 재시작 유지(B) 미검증
- 팝업 위치 center/top 실제 좌표(D) 미검증

### 재오픈 조건
- 수동 검증(B, D) 수행 후 결과를 본 문서에 PASS/FAIL로 갱신할 때
- 실사용 중 설정 반영/팝업 위치 관련 이슈가 재발할 때

### 현재 최종 판단
- 본 문서는 2026-05-10 기준으로 "조건부 마감" 처리한다.
