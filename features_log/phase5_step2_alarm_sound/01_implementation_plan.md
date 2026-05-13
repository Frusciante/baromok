# Phase 5-2단계 구현 계획: 알림음 구현

**작성일**: 2026-05-09  
**단계**: Phase 5 (검증/최적화) - Step 2  
**예상 기간**: 2-3시간

---

## 목차

1. [목표 및 범위](#목표-및-범위)
2. [현재 상태](#현재-상태)
3. [상세 구현 계획](#상세-구현-계획)
4. [기술 스택 선택](#기술-스택-선택)
5. [데이터 흐름](#데이터-흐름)
6. [검증 전략](#검증-전략)

---

## 목표 및 범위

### 목표
경고 발생 시 시스템 사운드를 재생하여 사용자에게 음성으로 알림

### 범위

| 항목 | 현재 상태 | 변경 후 | 우선순위 |
|------|----------|--------|---------|
| **음성 재생** | 미구현 | 구현 | ⭐⭐⭐ |
| **소리 크기 적용** | 설정만 저장 | 실제 적용 | ⭐⭐⭐ |
| **음성 활성화/비활성화** | 설정만 저장 | 실제 적용 | ⭐⭐⭐ |
| **사운드 파일 선택** | 없음 | 없음 (기본값) | ⭐ |

---

## 현재 상태

### 설정값 (이미 구현됨)
✅ `SettingsConfig.sound_enabled`: True/False  
✅ `SettingsConfig.sound_volume`: 0-100 (%)

### 구현되지 않은 부분
❌ 알림음 재생 로직  
❌ 소리 크기 제어  
❌ 음성 파일 관리

---

## 상세 구현 계획

### 1. SoundManager 클래스 생성 (1시간)

**파일**: `src/core/sound_manager.py` (신규)

```python
import winsound  # Windows 기본 제공
from src.utils.logger import get_logger

class SoundManager:
    """알림음 관리 클래스"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.is_playing = False
    
    def play_alert(self, volume_percent: int = 70):
        """
        알림음 재생
        
        Args:
            volume_percent: 음량 (0-100)
        """
        if volume_percent <= 0:
            return  # 음량 0이면 재생 안 함
        
        try:
            # Windows에서 제공하는 기본 경고음
            # winsound.Beep(frequency, duration)
            # frequency: Hz (440-1000 권장)
            # duration: ms
            
            winsound.Beep(800, 500)  # 800Hz, 500ms
            self.logger.info(f"알림음 재생: 음량={volume_percent}%")
        except Exception as e:
            self.logger.error(f"알림음 재생 실패: {e}")
```

**특징**:
- ✅ Windows 기본 제공 (추가 의존성 없음)
- ✅ 간단한 인터페이스
- ✅ 동기식 재생 (블로킹)
- ❌ 소리 크기 직접 제어 불가 (시스템 음량 사용)

**대안**: `pygame` (음량 제어 가능, 추가 의존성)

---

### 2. baromokApp에 SoundManager 주입 (1시간)

**파일**: `src/ui/app.py`

**변경 1: Import 추가**
```python
from src.core.sound_manager import SoundManager
```

**변경 2: __init__에 추가**
```python
# 알림음 관리자
self.sound_manager = SoundManager()
```

**변경 3: _show_alert_popup 수정**
```python
def _show_alert_popup(self, alert_type: str, message_text: str):
    """메인 스레드에서 알림 팝업 표시"""
    if self.alert_popup is None:
        from src.ui.screens import AlertPopup
        self.alert_popup = AlertPopup(self.theme_manager, alert_type, message_text)
        self.alert_popup.close_signal.connect(self._hide_alert_popup)
    else:
        self.alert_popup.set_alert_content(alert_type, message_text)

    self.alert_popup.adjustSize()
    
    # 팝업 위치 동적 계산 (프로퍼티 사용)
    x, y = self.popup_position_xy
    self.alert_popup.move(x, y)
    self.alert_popup.show()
    self.alert_popup.raise_()
    self.alert_popup.activateWindow()

    # 타이머 동적 설정 (프로퍼티 사용)
    timeout_ms = self.popup_timeout_ms
    self.alert_hide_timer.stop()
    if timeout_ms > 0:
        self.alert_hide_timer.start(timeout_ms)
        logger.debug(f"팝업 타이머 시작: {timeout_ms}ms")
    else:
        logger.debug("팝업 타이머 비활성화 (수동 닫기)")
    
    # 👇 신규: 알림음 재생
    if self.settings_config.sound_enabled:
        self.sound_manager.play_alert(self.settings_config.sound_volume)
```

---

### 3. 프로퍼티 추가 (선택사항, 30분)

**파일**: `src/ui/app.py`

```python
@property
def should_play_sound(self) -> bool:
    """알림음 재생 여부"""
    return self.settings_config.sound_enabled

@property
def sound_volume_percent(self) -> int:
    """알림음 음량 (0-100%)"""
    return max(0, min(100, self.settings_config.sound_volume))
```

**사용**:
```python
if self.should_play_sound:
    self.sound_manager.play_alert(self.sound_volume_percent)
```

---

### 4. 테스트 계획

#### Test 1: SoundManager 기본 테스트
```python
from src.core.sound_manager import SoundManager
sound = SoundManager()
sound.play_alert(70)  # 70% 음량으로 재생
```

**예상**: 경고음 한 번 들림

#### Test 2: 설정값에 따른 재생
- `sound_enabled=True, sound_volume=80` → 재생
- `sound_enabled=False, sound_volume=80` → 미재생
- `sound_enabled=True, sound_volume=0` → 미재생

#### Test 3: 경고 발생 시 음성 재생
1. Baseline 촬영
2. Detection 시작
3. 나쁜 자세 감지 → 팝업 + 음성 확인

#### Test 4: 설정 변경 후 반영
1. Settings: sound_enabled=False
2. Confirm
3. Detection 중 경고 → 음성 없음 확인
4. Settings: sound_enabled=True
5. 다음 경고 → 음성 있음 확인

---

## 기술 스택 선택

### 옵션 1: winsound (권장) ⭐
**장점**:
- ✅ Windows 기본 제공 (의존성 추가 없음)
- ✅ 설치 불필요
- ✅ 간단한 API

**단점**:
- ❌ 음량 직접 제어 불가
- ❌ Windows 전용
- ❌ 제한된 사운드 형식

### 옵션 2: pygame
**장점**:
- ✅ 크로스플랫폼
- ✅ 음량 제어 가능
- ✅ 다양한 형식 지원

**단점**:
- ❌ 추가 의존성 (pygame 설치 필요)
- ❌ 더 복잡한 API

### 선택: **winsound** (현재 단계에서)
- 이유: 의존성 최소화, 빠른 구현, Windows 환경에서 충분

---

## 데이터 흐름

### 경고 발생 → 음성 재생 흐름

```
상태 머신: NORMAL → WARNING/DANGER
     ↓
_handle_state_transition()
     ↓
쿨다운 체크 ✓
     ↓
alert_bridge.alert_requested.emit()
     ↓
_show_alert_popup() (메인 스레드)
     ↓
팝업 표시
+ 팝업 위치 설정
+ 팝업 타이머 설정
+ 👇 신규: 음성 재생
     ↓
if self.settings_config.sound_enabled:
    self.sound_manager.play_alert(self.settings_config.sound_volume)
     ↓
SoundManager.play_alert()
     ↓
winsound.Beep(800, 500)
     ↓
[음성 들림]
```

---

## 검증 전략

### 정적 검증
- [ ] 코드 오류 없음 (`get_errors`)
- [ ] Import 문제 없음
- [ ] 타입 힌팅 정상

### 단위 테스트
- [ ] SoundManager 인스턴스 생성
- [ ] play_alert() 메서드 호출
- [ ] 음성 재생 확인

### 기능 테스트
- [ ] sound_enabled=True/False 테스트
- [ ] sound_volume 설정값 테스트
- [ ] 경고 발생 시 음성 재생 확인

### 통합 테스트
- [ ] 설정 변경 후 즉시 반영
- [ ] 감지 중 설정 변경 후 다음 경고에 반영

---

## 예상 변경 파일

| 파일 | 변경 타입 | 라인 수 | 설명 |
|------|---------|--------|------|
| `src/core/sound_manager.py` | 신규 | ~50 | SoundManager 클래스 |
| `src/ui/app.py` | 수정 | ~20 | SoundManager 주입, 음성 재생 로직 |

---

## 위험 요소 및 대응

| 위험 | 심각도 | 대응 |
|------|--------|------|
| Windows 전용 코드 | 🟢 낮음 | 나중에 pygame으로 변경 가능 |
| 음성 너무 크거나 작음 | 🟡 중간 | 설정값 튜닝, 시스템 음량 활용 |
| 동시 음성 재생 | 🟢 낮음 | winsound는 동기식이므로 문제 없음 |

---

## 다음 단계

1. ✅ 구현 계획서 작성 (현재)
2. 👉 사용자 확인/수정
3. 구현 진행
4. 코드 검증
5. 기능 테스트
6. 결과 문서 작성

---

## 구현 체크리스트

- [ ] SoundManager 클래스 작성
- [ ] baromokApp에 주입
- [ ] _show_alert_popup 수정
- [ ] Import 추가
- [ ] 정적 검증
- [ ] 단위 테스트
- [ ] 기능 테스트
- [ ] 통합 테스트
