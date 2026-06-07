# Manual UI Acceptance Test Checklist

목표: 감지 종료/이전 버튼 분리 및 설정 단일 원천화가 올바르게 동작하는지 수동으로 검증한다.

환경 준비:
- 최신 `wooseong` 브랜치로 체크아웃하고 로컬에서 `git pull` 및 `git status` 확인
- 가상환경 활성화: `source venv/Scripts/activate` (Windows PowerShell: `.& venv\Scripts\Activate.ps1`)
- 앱 실행: `python main.py`

시나리오 1: 이전(일시탈출) 동작
- 1. Hub에서 감지 시작
- 2. 감지 화면에서 `설정`으로 이동 (뒤로 버튼 사용 아님) 또는 헤더의 이전 버튼 사용
- 기대: 세션은 유지되거나 일시정지 상태가 되며, 감지 화면 복귀 시 `on_detection_started()`가 호출되어 카메라가 재개됨

시나리오 2: 종료 버튼 동작
- 1. Hub에서 감지 시작
- 2. 감지 화면에서 `종료` 버튼 클릭
- 기대: 세션이 완전히 종료되며 카메라는 `stop_capture()`로 정리됨, 화면은 Hub로 이동하지 않고 Detection 화면 내에 "세션 종료됨" 상태와 `다시 시작`/`결과 보기` 버튼이 표시됨
- 3. `다시 시작` 클릭 -> 기대: 감지 재시작(카메라 재시작 및 타이머)
- 4. `결과 보기` 클릭 -> 기대: 통계/결과 화면으로 전환

시나리오 3: baseline 권장값 적용과 Settings 동기화
- 1. Baseline 수행(또는 테스트로 권장값 적용 트리거)
- 2. 앱에서 권장 감도 계산 후 `SettingsConfig`에 저장 및 `_refresh_settings_screen_values()` 호출
- 기대: `Settings` 화면을 열었을 때 모든 위젯이 최신 권장 감도 값을 반영함

시나리오 4: 설정 덮어쓰기 방지 (Dirty 정책)
- 1. 앱 시작 후 `Settings` 화면에서 아무 변경도 하지 않음
- 2. Baseline이 권장값을 저장함
- 3. Settings 화면이 (자동으로) 최신값으로 보이는지 확인
- 4. Settings에서 값을 변경하지 않고 앱 종료 -> 기대: `data/config.json`은 변경되지 않음(또는 마지막 저장된 값과 동일)
- 5. Settings에서 값을 변경 -> `저장` 또는 백 버튼으로 나감 -> 기대: 변경 시 `data/config.json`이 업데이트됨

검증 팁:
- 로그 확인: `logs/` 또는 콘솔 로그에서 `_settings_dirty` 변경 및 `_persist_settings_if_dirty` 호출 여부 확인
- 파일 변경 검사: `git status --porcelain` 또는 `git diff data/config.json`로 저장 여부 확인

테스트 결과 기록: 각 시나리오에 대해 Pass/Fail 및 관찰된 동작 기록

---

작성자: 자동 생성
날짜: TODO
