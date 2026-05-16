# 설정 화면 상세 컨트롤 구현 계획

**작성일**: 2026-05-09  
**단계**: Phase 4 후속 (UI 상세 완성)  
**예상 기간**: 4-6시간

---

## 목차

1. [목표 및 범위](#목표-및-범위)
2. [현재 상태](#현재-상태)
3. [구현 계획](#구현-계획)
4. [상세 구현 항목](#상세-구현-항목)
5. [데이터 구조](#데이터-구조)
6. [검증 전략](#검증-전략)

---

## 목표 및 범위

### 목표
- ✅ SettingsScreen의 카테고리별 상세 컨트롤 구현
- ✅ 설정 데이터의 저장 및 로드 기능 완성
- ✅ 각 설정 항목에 대한 UI/로직 연동

### 범위

| 카테고리 | 항목 | 컨트롤 타입 | 범위 |
|---------|------|-----------|------|
| **알림 설정** | 나쁜 자세 감지 알림 | 토글 | ON/OFF |
| | 알림 간격 | 슬라이더 | 5-60초 |
| **소리 설정** | 알림음 활성화 | 토글 | ON/OFF |
| | 소리 크기 | 슬라이더 | 0-100% |
| **팝업 설정** | 팝업 표시 위치 | 라디오 | 화면 중앙/우측 하단 |
| | 팝업 자동 닫기 | 토글 | ON/OFF |
| | 팝업 자동 닫기 시간 | 슬라이더 | 3-10초 |
| **자동 시작** | 프로그램 시작 시 감지 자동 시작 | 토글 | ON/OFF |

### 제외 사항
- 실제 알림음 재생은 Phase 5 범위
- 고급 커스터마이징(색상 선택 등)은 Phase 5 범위

---

## 현재 상태

### SettingsScreen 구조
```python
class SettingsScreen(QWidget):
    """환경 설정 화면"""
    - 좌측: 카테고리 버튼 (4개)
    - 우측: "[설정값 UI]\n(향후 구현)" placeholder
    - 하단: 확인 버튼
```

### 문제점
- 우측에 카테고리별 설정 UI가 미구현
- 설정 데이터 저장/로드 로직 미구현
- 각 컨트롤 간의 상태 연동 미구현

---

## 구현 계획

### 1단계: 설정 데이터 구조 정의 (20분)

**파일**: `src/config.py` 수정  
**내용**:
```python
class SettingsConfig:
    # 알림 설정
    notification_enabled: bool = True
    notification_interval: int = 30  # 초

    # 소리 설정
    sound_enabled: bool = True
    sound_volume: int = 70  # 0-100

    # 팝업 설정
    popup_position: str = "center"  # "center" | "bottom_right"
    popup_auto_close: bool = True
    popup_auto_close_time: int = 5  # 초

    # 자동 시작
    auto_start_detection: bool = False

    def to_dict(self) -> dict
    def from_dict(cls, data: dict) -> "SettingsConfig"
    def save_to_json(self, file_path: str)
    def load_from_json(file_path: str) -> "SettingsConfig"
```

### 2단계: 카테고리별 위젯 클래스 생성 (90분)

**파일**: `src/ui/widgets/settings_widgets.py` (새 파일)  
**내용**:
- `NotificationSettingsWidget`: 토글 + 슬라이더
- `SoundSettingsWidget`: 토글 + 슬라이더
- `PopupSettingsWidget`: 라디오 + 토글 + 슬라이더
- `AutoStartSettingsWidget`: 토글

각 위젯:
- ✅ 레이아웃 구성 (라벨 + 컨트롤)
- ✅ 상태 변경 시 시그널 발생
- ✅ 초기값 로드 및 반영

### 3단계: SettingsScreen 리팩터링 (90분)

**파일**: `src/ui/screens/__init__.py` (SettingsScreen 클래스 수정)  
**내용**:
- 우측 레이아웃을 `QStackedWidget`으로 변경
- 카테고리 클릭 시 해당 위젯으로 전환
- 설정값 변경 시 signal-slot으로 추적
- 확인 버튼 클릭 시 현재 카테고리의 설정 저장

### 4단계: 설정 데이터 저장/로드 (30분)

**파일**: `src/ui/app.py` 수정  
**내용**:
- 앱 시작 시 `config.json` 로드 (또는 기본값)
- SettingsScreen 생성 시 로드된 설정값 주입
- 확인 버튼 클릭 시 설정값 저장
- 저장 경로: `data/config.json`

### 5단계: 검증 및 테스트 (40분)

**검증 항목**:
- 각 위젯이 정상 렌더링되는가?
- 슬라이더/토글 값 변경이 반영되는가?
- 설정값이 JSON으로 저장/로드되는가?
- 카테고리 전환이 부드럽게 이루어지는가?

---

## 상세 구현 항목

### A. SettingsConfig 클래스

**위치**: `src/config.py`  
**추가 내용**:
```python
from dataclasses import dataclass, asdict
from pathlib import Path
import json

@dataclass
class SettingsConfig:
    # 알림 설정
    notification_enabled: bool = True
    notification_interval: int = 30

    # 소리 설정
    sound_enabled: bool = True
    sound_volume: int = 70

    # 팝업 설정
    popup_position: str = "center"
    popup_auto_close: bool = True
    popup_auto_close_time: int = 5

    # 자동 시작
    auto_start_detection: bool = False

    @classmethod
    def load_from_json(cls, file_path: str) -> "SettingsConfig":
        """JSON 파일에서 설정 로드"""
        if Path(file_path).exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(**data)
        return cls()

    def save_to_json(self, file_path: str) -> None:
        """JSON 파일에 설정 저장"""
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
```

### B. 카테고리별 위젯 클래스

**위치**: `src/ui/widgets/settings_widgets.py` (새 파일)

각 위젯은 다음 구조를 따릅니다:
- `__init__(theme_manager, initial_value)`: 초기값 설정
- `get_value()`: 현재 값 반환
- `set_value(value)`: 값 설정
- `value_changed_signal`: 값 변경 시 발생하는 signal

### C. SettingsScreen 리팩터링

**변경 사항**:
1. 우측 레이아웃을 `QStackedWidget` + `QVBoxLayout` 구조로 변경
2. 각 카테고리 위젯을 스택에 추가
3. 카테고리 버튼 클릭 시 `QStackedWidget.setCurrentIndex()` 호출
4. 확인 버튼 클릭 시 현재 활성 위젯의 값을 `settings_saved_signal`에 담아 발생

---

## 데이터 구조

### 설정 JSON 파일 (`data/config.json`)
```json
{
  "notification_enabled": true,
  "notification_interval": 30,
  "sound_enabled": true,
  "sound_volume": 70,
  "popup_position": "center",
  "popup_auto_close": true,
  "popup_auto_close_time": 5,
  "auto_start_detection": false
}
```

---

## 검증 전략

### 정적 검증
- `src/config.py`, `src/ui/widgets/settings_widgets.py`, `src/ui/screens/__init__.py` 오류 확인
- 타입 힌팅 및 import 검증

### 기능 검증
1. **초기 로드**: 앱 시작 시 기본 설정값이 화면에 표시되는가?
2. **카테고리 전환**: 좌측 버튼 클릭 시 우측 위젯이 변경되는가?
3. **값 변경**: 슬라이더/토글 조작이 UI에 반영되는가?
4. **저장**: 확인 버튼 클릭 시 `data/config.json`에 저장되는가?
5. **재로드**: 앱을 다시 시작하면 저장된 설정값이 반영되는가?

---

## 참고 사항

- 기존 테마 시스템(ThemeManager) 활용
- 신호/슬롯 기반 이벤트 처리
- Windows DPI 스케일링 대응
- 설정값 유효성 검사 필수
