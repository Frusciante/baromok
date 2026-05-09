# Phase 5-1단계 구현 계획: 설정값 실제 적용

**작성일**: 2026-05-09  
**단계**: Phase 5 (검증/최적화) - Step 1  
**예상 기간**: 3-4시간

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
설정 화면에서 저장한 사용자 설정값이 실제 애플리케이션 동작에 반영되도록 구현

### 범위

| 항목 | 현재 상태 | 변경 후 | 우선순위 |
|------|----------|--------|---------|
| **알림 간격** | 고정 (30초) | 설정값 적용 | ⭐⭐⭐ |
| **팝업 위치** | 고정 (중앙) | 동적 (중앙/우측 하단) | ⭐⭐⭐ |
| **팝업 자동 닫기 시간** | 고정 (3초) | 설정값 적용 | ⭐⭐⭐ |
| **소리 활성화** | 설정만 저장 | 실제 구현은 2단계 | ⭐ |
| **자동 시작** | 미구현 | 3단계에서 구현 | ⭐ |

---

## 현재 상태

### 설정값 저장/로드
✅ **완료**:
- `SettingsConfig` 클래스 (`src/config.py`)
- `SettingsScreen` UI 구현
- JSON 파일 저장/로드
- `baromokApp._save_settings()` 메서드

❌ **미완료**:
- 설정값이 실제 동작에 반영 안 됨

### 현재 고정값 사용 위치

| 파일 | 기능 | 고정값 |
|------|------|--------|
| `src/ui/app.py` | 알림 쿨다운 | `alert_cooldown_seconds = 3.0` |
| `src/ui/app.py` | 팝업 타임아웃 | `self.alert_hide_timer.start(3000)` |
| `src/ui/app.py` | 팝업 위치 | `self.alert_popup.move(...)` (중앙 고정) |

---

## 상세 구현 계획

### 1. 알림 간격 설정값 적용 (1시간)

**파일**: `src/ui/app.py`

**변경 사항**:
```python
# 현재
self.alert_cooldown_seconds = float(
    self.config.get_app_setting("alert_cooldown_seconds", 3.0)
)

# 변경 후: 설정값에서 읽기
@property
def alert_cooldown_seconds(self):
    return self.settings_config.notification_interval
```

**구체적 변경**:
- `__init__()`: `self.alert_cooldown_seconds` 제거 (대신 프로퍼티로)
- `_handle_state_transition()`: 쿨다운 체크 시 프로퍼티 사용
- `_save_settings()`: 설정 저장 후 `self._update_notification_settings()` 호출

**신규 메서드**:
```python
def _update_notification_settings(self):
    """알림 설정 업데이트"""
    # 필요시 추가 로직
    logger.info("알림 설정 업데이트: 간격=%ds", self.settings_config.notification_interval)
```

### 2. 팝업 위치 동적 설정 (1.5시간)

**파일**: `src/ui/app.py`

**현재 코드 (추정)**:
```python
def _show_alert_popup(self, title: str, message: str):
    # 팝업 생성 및 중앙에 위치
    self.alert_popup = AlertPopup(title, message)
    screen = self.qt_app.primaryScreen()
    screen_rect = screen.geometry()
    x = (screen_rect.width() - self.alert_popup.width()) // 2
    y = (screen_rect.height() - self.alert_popup.height()) // 2
    self.alert_popup.move(x, y)
```

**변경 후**:
```python
def _show_alert_popup(self, title: str, message: str):
    self.alert_popup = AlertPopup(title, message)
    screen = self.qt_app.primaryScreen()
    screen_rect = screen.geometry()
    
    if self.settings_config.popup_position == "center":
        # 화면 중앙
        x = (screen_rect.width() - self.alert_popup.width()) // 2
        y = (screen_rect.height() - self.alert_popup.height()) // 2
    else:  # "bottom_right"
        # 우측 하단 (여백 20px)
        x = screen_rect.width() - self.alert_popup.width() - 20
        y = screen_rect.height() - self.alert_popup.height() - 20
    
    self.alert_popup.move(x, y)
```

**신규 메서드**:
```python
def _get_popup_position(self) -> tuple:
    """팝업 위치 계산"""
    screen = self.qt_app.primaryScreen()
    screen_rect = screen.geometry()
    
    if self.settings_config.popup_position == "center":
        x = (screen_rect.width() - self.alert_popup.width()) // 2
        y = (screen_rect.height() - self.alert_popup.height()) // 2
    else:
        margin = 20
        x = screen_rect.width() - self.alert_popup.width() - margin
        y = screen_rect.height() - self.alert_popup.height() - margin
    
    return (x, y)
```

### 3. 팝업 자동 닫기 시간 적용 (1시간)

**파일**: `src/ui/app.py`

**현재 코드**:
```python
def _show_alert_popup(self, title: str, message: str):
    # ...
    self.alert_hide_timer.start(3000)  # 고정 3초
```

**변경 후**:
```python
def _show_alert_popup(self, title: str, message: str):
    # ...
    if self.settings_config.popup_auto_close:
        timeout_ms = int(self.settings_config.popup_auto_close_time * 1000)
        self.alert_hide_timer.start(timeout_ms)
    else:
        self.alert_hide_timer.stop()  # 자동 닫기 비활성화
```

**신규 메서드**:
```python
def _get_popup_timeout(self) -> int:
    """팝업 타임아웃 계산 (ms)"""
    if self.settings_config.popup_auto_close:
        return int(self.settings_config.popup_auto_close_time * 1000)
    else:
        return 0  # 타이머 시작 안 함
```

### 4. 설정값 업데이트 후 반영 (0.5시간)

**파일**: `src/ui/app.py`

**변경 사항**:
```python
def _save_settings(self, settings_dict: dict):
    """설정 저장"""
    try:
        # 설정값 업데이트
        for key, value in settings_dict.items():
            if hasattr(self.settings_config, key):
                setattr(self.settings_config, key, value)
        
        # JSON 파일에 저장
        self.settings_config.save_to_json("data/config.json")
        
        # 👇 신규: 설정값 즉시 반영
        self._apply_settings()
        
        logger.info("설정 저장 및 적용 완료: %s", settings_dict)
    except Exception as e:
        logger.error("설정 저장 실패: %s", e)

def _apply_settings(self):
    """설정값 즉시 적용"""
    logger.info("설정값 적용:")
    logger.info("  - 알림 간격: %ds", self.settings_config.notification_interval)
    logger.info("  - 팝업 위치: %s", self.settings_config.popup_position)
    logger.info("  - 팝업 자동 닫기: %s (%ds)", 
                self.settings_config.popup_auto_close,
                self.settings_config.popup_auto_close_time)
```

---

## 데이터 흐름

### 설정값 저장 → 적용 흐름

```
SettingsScreen
    ↓ (settings_saved_signal 발생)
baromokApp._save_settings()
    ↓ (설정값 객체에 저장)
SettingsConfig (메모리)
    ↓ (JSON 파일에 저장)
data/config.json
    ↓ (즉시 반영)
baromokApp._apply_settings()
    ├─ 알림 쿨다운 업데이트 ✓
    ├─ 팝업 위치 업데이트 ✓
    └─ 팝업 타임아웃 업데이트 ✓
```

### 런타임 적용 예시

```
[사용자가 설정 변경]
  ↓
설정값 저장 (JSON)
  ↓
다음 경고 발생 시:
  • alert_cooldown_seconds = self.settings_config.notification_interval 사용
  • 팝업 위치 = self.settings_config.popup_position 기준 계산
  • 팝업 타이머 = self.settings_config.popup_auto_close_time 사용
```

---

## 검증 전략

### 정적 검증
- [ ] 코드 오류 없음 (`get_errors`)
- [ ] 타입 힌팅 정상
- [ ] import 문제 없음

### 단위 테스트
- [ ] `SettingsConfig.notification_interval` 프로퍼티 동작
- [ ] 팝업 위치 계산 함수 검증
- [ ] 타이머 값 계산 검증

### 기능 테스트
1. **초기 실행**:
   - [ ] 기본 설정값으로 시작
   - [ ] JSON 파일 없으면 기본값 사용

2. **설정 변경**:
   - [ ] 알림 간격 변경 → 다음 경고에 반영
   - [ ] 팝업 위치 변경 → 다음 팝업에 반영
   - [ ] 팝업 시간 변경 → 다음 팝업에 반영

3. **설정 재로드**:
   - [ ] 앱 재시작 후 설정값 유지

### 통합 테스트
- [ ] 감지 중 설정 변경 후 계속 감지
- [ ] 경고 발생 후 팝업 위치/시간 설정값 반영 확인

---

## 예상 변경 파일

| 파일 | 변경 라인 | 설명 |
|------|----------|------|
| `src/ui/app.py` | ~50-100 | 설정값 적용 메서드, 프로퍼티 추가 |

---

## 위험 요소 및 대응

| 위험 | 심각도 | 대응 |
|------|--------|------|
| 런타임 중 설정 변경 시 이전 타이머 정지 안 함 | 🟡 중간 | 타이머 정지 후 재시작 |
| 팝업 좌표 음수 값 가능성 | 🟡 중간 | min() 함수로 최소값 제한 |
| 설정값 범위 벗어남 (예: 1초 미만) | 🟢 낮음 | `max()` 함수로 최소값 보장 |

---

## 다음 단계

1. ✅ 구현 계획서 작성 (현재)
2. 👉 사용자 확인/수정
3. 구현 진행
4. 코드 검증
5. 기능 테스트
6. 결과 문서 작성
