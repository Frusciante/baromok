# 구현 계획서

## 작업명
- 감지 종료/이전 역할 분리 및 설정 저장 단일화

## 목표
- 종료 버튼은 세션을 완전히 종료하되 Hub 화면으로 강제 이동하지 않는다.
- 이전(헤더 뒤로가기) 동작은 감지 화면 이탈만 수행하고 세션 종료와 분리한다.
- config.json 저장 경로를 앱 단일 경로로 통일하고 dirty 기반 저장 정책을 적용한다.

## 변경 범위
- src/ui/screens/detection_screen.py
- src/ui/app.py
- src/ui/screens/settings_screen.py

## 세부 계획
1. 감지 종료/이전 분리
- DetectionScreen의 종료 처리에서 앱 신호만 발생시키고, 종료 후 UI 상태를 표시하는 on_detection_stopped 메서드를 추가한다.
- baromokApp._stop_detection에서 세션 종료와 카메라 stop_capture를 수행하고, switch_screen(1)을 제거한다.
- 기존 헤더 뒤로가기는 감지 이탈(일시정지) 동작으로 유지한다.

2. 설정 저장 단일화
- 앱에 settings dirty 플래그와 저장 메서드를 추가한다.
- 설정 변경은 앱 메모리(self.settings_config)만 갱신하고, 저장은 앱의 단일 저장 메서드에서 수행한다.
- SettingsScreen 진입 시 앱의 최신 설정을 위젯에 재동기화한다.
- baseline 권장 감도 적용 경로도 단일 저장 메서드 사용으로 통합한다.
- 앱 종료 시 무조건 저장하지 않고 dirty일 때만 저장한다.

3. 안정화
- detection_screen.py의 머지 충돌 마커를 정리한다.

## 검증 계획
- 감지 중 종료 클릭 시: 세션 종료 + 화면 유지 + 종료 상태 문구 표시
- 감지 중 뒤로가기 클릭 시: 화면 이탈만 수행되고 세션 종료는 발생하지 않음
- baseline 권장 감도 적용 후 설정 화면 진입 시 위젯 값 동기화
- 설정 변경 후 설정 화면 이탈/앱 종료 시 dirty 저장 정책 동작 확인
