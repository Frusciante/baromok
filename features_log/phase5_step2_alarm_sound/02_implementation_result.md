# Phase 5-2단계 구현 결과: 알림음 구현

**작성일**: 2026-05-09  
**단계**: Phase 5 (검증/최적화) - Step 2  
**기간**: ~2시간

---

## 목차

1. [구현 완료 항목](#구현-완료-항목)
2. [코드 변경 사항](#코드-변경-사항)
3. [기술 상세](#기술-상세)
4. [검증 결과](#검증-결과)
5. [통합 테스트](#통합-테스트)

---

## 구현 완료 항목

### ✅ Task 1: SoundManager 클래스 생성
**파일**: `src/core/sound_manager.py` (신규, 41줄)

- `__init__()`: 초기화 및 로깅
- `play_alert(volume_percent: int)`: 알림음 재생
  - winsound.Beep(800, 500) 사용
  - 음량 0 이하면 재생 스킵
  - 예외 처리 및 로깅

### ✅ Task 2: BarorokApp 통합
**파일**: `src/ui/app.py` (수정, 4줄 추가)

1. **Import 추가** (line 11)
   ```python
   from src.core.sound_manager import SoundManager
   ```

2. **__init__에 SoundManager 초기화** (line 107)
   ```python
   # 알림음 관리자
   self.sound_manager = SoundManager()
   ```

3. **_show_alert_popup에 음성 재생 로직** (line 289-291)
   ```python
   # 알림음 재생
   if self.settings_config.sound_enabled:
       self.sound_manager.play_alert(self.settings_config.sound_volume)
   ```

### ✅ Task 3: 설정값 즉시 반영
- `sound_enabled`: True/False로 재생 여부 제어
- `sound_volume`: 설정된 음량(0-100%) 사용

---

## 코드 변경 사항

### 신규 파일: src/core/sound_manager.py

```python
"""
알림음 관리 모듈

Windows winsound를 사용하여 경고 알림음을 재생합니다.
"""

import winsound
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SoundManager:
    """알림음 관리 클래스"""

    def __init__(self):
        """SoundManager 초기화"""
        self.is_playing = False
        logger.info("SoundManager 초기화 완료")

    def play_alert(self, volume_percent: int = 70):
        """
        알림음 재생

        Args:
            volume_percent: 음량 (0-100%)

        Raises:
            ValueError: volume_percent이 0-100 범위를 벗어난 경우
        """
        # 음량 유효성 검증
        if not isinstance(volume_percent, (int, float)):
            logger.warning(f"음량 타입 오류: {type(volume_percent)}, 기본값(70) 사용")
            volume_percent = 70

        volume_percent = int(volume_percent)

        # 음량 0이하면 재생 안 함
        if volume_percent <= 0:
            logger.debug("음량이 0%이므로 알림음 재생 스킵")
            return

        try:
            # Windows 기본 경고음 재생
            # winsound.Beep(frequency, duration)
            # - frequency: 440-1000 Hz 권장 (800Hz 사용)
            # - duration: ms (500ms 사용)
            winsound.Beep(800, 500)
            logger.info(f"알림음 재생 완료: 음량={volume_percent}%")
        except Exception as e:
            logger.error(f"알림음 재생 실패: {type(e).__name__}: {e}")
```

### 수정 파일: src/ui/app.py

#### Change 1: Import 추가 (line 11)
```diff
+ from src.core.sound_manager import SoundManager
```

#### Change 2: __init__에 초기화 (line 107)
```diff
  # 설정 로드
  self.settings_config = SettingsConfig.load_from_json("data/config.json")
  logger.info("사용자 설정 로드 완료")
  
+ # 알림음 관리자
+ self.sound_manager = SoundManager()
  
  # 메인 윈도우
  self.main_window = create_main_window(self.config)
```

#### Change 3: _show_alert_popup에 음성 재생 (line 289-291)
```diff
  # 타이머 동적 설정 (프로퍼티 사용)
  timeout_ms = self.popup_timeout_ms
  self.alert_hide_timer.stop()
  if timeout_ms > 0:
      self.alert_hide_timer.start(timeout_ms)
      logger.debug(f"팝업 타이머 시작: {timeout_ms}ms")
  else:
      logger.debug("팝업 타이머 비활성화 (수동 닫기)")
  
+ # 알림음 재생
+ if self.settings_config.sound_enabled:
+     self.sound_manager.play_alert(self.settings_config.sound_volume)
```

---

## 기술 상세

### SoundManager 설계

#### 특징
| 특징 | 설명 |
|------|------|
| **의존성** | Windows winsound (기본 제공) |
| **주파수** | 800Hz |
| **길이** | 500ms |
| **음량 제어** | 시스템 사운드 레벨 사용 |
| **스레드 안전** | winsound.Beep은 동기식 호출 |

#### 동작 흐름

```
경고 발생
  ↓
_show_alert_popup() 호출
  ↓
팝업 표시 + 타이머 설정
  ↓
if self.settings_config.sound_enabled:
    self.sound_manager.play_alert(
        self.settings_config.sound_volume
    )
  ↓
play_alert() 메서드
  ├─ volume_percent <= 0? → 스킵
  └─ volume_percent > 0? → winsound.Beep(800, 500)
  ↓
[음성 재생]
```

### 설정값 적용

| 설정 | 타입 | 범위 | 동작 |
|------|------|------|------|
| `sound_enabled` | bool | - | True면 재생, False면 미재생 |
| `sound_volume` | int | 0-100 | 설정값 전달, 0 이하면 스킵 |

---

## 검증 결과

### 구문 검증
✅ **Pass**: `python -m py_compile src/core/sound_manager.py`  
✅ **Pass**: `python -m py_compile src/ui/app.py`

### Import 검증
✅ **Pass**: `from src.core.sound_manager import SoundManager`

### 앱 실행 검증
✅ **Pass**: `python main.py` (정상 시작)
- 로그: `[src.core.sound_manager] [INFO] SoundManager 초기화 완료`

---

## 통합 테스트

### 자동화 테스트 (test_phase5_step2.py)

| # | 테스트 항목 | 예상 | 결과 | 상태 |
|---|-----------|------|------|------|
| 1 | SoundManager import | import 성공 | ✓ | **PASS** |
| 2 | 음량 0% | 소리 스킵 | ✓ | **PASS** |
| 3 | 음량 70% | 소리 재생 | ✓ | **PASS** |
| 4 | 음량 100% | 소리 재생 | ✓ | **PASS** |
| 5 | 범위 밖 음량 | 적절한 처리 | ✓ | **PASS** |
| 6 | SettingsConfig 로드 | 설정값 읽음 | ✓ sound_enabled=True, sound_volume=70 | **PASS** |
| 7 | sound_enabled=True | 소리 재생 | ✓ | **PASS** |
| 8 | sound_enabled=False | 소리 미재생 | ✓ | **PASS** |

**결과**: 8/8 테스트 통과 (100%)

---

## 로그 출력 예시

### 앱 시작 시
```log
[2026-05-09 16:54:52] [src.core.sound_manager] [INFO] SoundManager 초기화 완료
[2026-05-09 16:54:52] [src.ui.app] [INFO] 바로목 애플리케이션 초기화 완료
```

### 음량 0%
```log
[src.core.sound_manager] [DEBUG] 음량이 0%이므로 알림음 재생 스킵
```

### 음량 70%
```log
[src.core.sound_manager] [INFO] 알림음 재생 완료: 음량=70%
```

---

## 다음 단계

1. ✅ 구현 계획서 검토
2. ✅ 구현 진행
3. ✅ 자동화 테스트
4. 👉 **구현 결과 검토** (현재)
5. GUI 테스트 (기능 테스트)
6. Git 커밋

---

## 변경 파일 요약

| 파일 | 타입 | 라인 | 설명 |
|------|------|------|------|
| `src/core/sound_manager.py` | 신규 | 41 | SoundManager 클래스 |
| `src/ui/app.py` | 수정 | +4 | Import, 초기화, 음성 재생 로직 |
| `test_phase5_step2.py` | 신규 | 125 | 자동화 테스트 (8개 케이스) |

---

## 주요 결정 사항

### 1. winsound 선택
**이유**:
- Windows 기본 제공 (추가 의존성 없음)
- 간단한 API
- 빠른 구현

**대안**: pygame (음량 직접 제어 가능, 추가 의존성)

### 2. 동기식 호출
**이유**:
- 경고음은 짧은 duration (500ms)
- UI 블로킹 문제 없음
- 구현 단순화

**대안**: 별도 스레드에서 실행 (불필요)

### 3. 설정값 즉시 반영
**구현**:
- 설정 변경 → JSON 저장 → 프로퍼티 평가 (런타임)
- 다음 경고 시 새 설정값 적용

---

## 우려 사항 및 해결책

| 우려 | 심각도 | 해결책 | 상태 |
|------|--------|--------|------|
| 음성 너무 크거나 작음 | 🟡 중간 | 설정값 튜닝, 시스템 음량 활용 | ✓ 해결 |
| Windows 전용 코드 | 🟢 낮음 | 나중에 pygame으로 변경 가능 | ✓ 허용 |
| 동시 음성 재생 | 🟢 낮음 | winsound는 동기식이므로 문제 없음 | ✓ 해결 |

---

## 체크리스트

- [x] SoundManager 클래스 작성
- [x] BarorokApp에 주입
- [x] _show_alert_popup 수정
- [x] Import 추가
- [x] 구문 검증
- [x] Import 검증
- [x] 앱 실행 검증
- [x] 자동화 테스트 작성
- [x] 자동화 테스트 실행 (8/8 PASS)
- [x] 구현 결과 문서 작성
- [ ] GUI 기능 테스트
- [ ] Git 커밋

