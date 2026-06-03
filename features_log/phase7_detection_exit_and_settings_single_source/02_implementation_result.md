# 구현 결과

## 요약
- 감지 화면의 종료 동작에서 Hub 강제 이동을 제거하고, 감지 화면 내부 종료 상태 표시로 변경했다.
- 설정 저장 경로를 앱 단일 저장 메서드로 통일하고 dirty 플래그 정책을 적용했다.
- 설정 화면 진입 시 최신 설정을 위젯에 재동기화하도록 변경했다.

## 변경 사항 상세

### 1) 종료 버튼과 이전 동작 분리
- 파일: src/ui/screens/detection_screen.py
  - session 종료 상태 플래그(is_session_stopped) 추가
  - 종료 버튼 인스턴스(self.stop_btn)로 관리
  - 종료 후 UI 상태 전환 메서드(on_detection_stopped) 추가
  - 감지 시작 메서드(on_detection_started)에서 종료 상태 해제 및 버튼/라벨 상태 초기화
  - 종료 상태에서는 프레임 업데이트를 무시하도록 처리
  - 머지 충돌 마커 제거 및 _update_posture_status 병합 정리

- 파일: src/ui/app.py
  - _stop_detection에서 switch_screen(1) 제거
  - 종료 시 camera pause 대신 stop_capture 사용
  - 종료 후 DetectionScreen.on_detection_stopped 호출로 화면 내부 상태 변경

### 2) config.json 저장 주체 단일화
- 파일: src/ui/app.py
  - _settings_dirty 플래그 도입
  - _persist_settings_if_dirty(force, reason) 메서드 추가
  - _refresh_settings_screen_values 메서드 추가
  - switch_screen에서 설정 화면 이탈 시 dirty 저장
  - switch_screen에서 설정 화면 진입 시 최신 설정값 재동기화
  - baseline 권장 감도 반영 경로에서 직접 파일 저장 제거, 단일 저장 메서드 사용으로 통합
  - 앱 종료 시 무조건 저장 제거, dirty일 때만 저장
  - _on_settings_widget_changed에서 메모리 반영 + 즉시 적용 + dirty 표기
  - _reset_settings / _save_settings도 단일 저장 경로 사용으로 통일

- 파일: src/ui/screens/settings_screen.py
  - update_settings(settings_dict) 메서드 추가
  - 앱이 전달한 최신 설정을 위젯에 신호 차단(blockSignals) 상태로 반영하도록 구현

## 기대 효과
- 종료 버튼을 눌러도 자동으로 Hub 이동하지 않아, 종료와 화면 이동의 역할이 분리된다.
- 설정값 원본은 앱의 SettingsConfig로 일원화되고, 저장은 단일 메서드에서만 수행되어 값 되돌림 가능성이 줄어든다.
- baseline 권장 감도 반영 후 설정 화면 위젯 불일치 문제가 줄어든다.
