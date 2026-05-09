# Phase 5 계획: 검증 및 최적화

**작성일**: 2026-05-09  
**단계**: Phase 5 (검증/최적화/배포 준비)  
**예상 기간**: 10-15시간

---

## 목차

1. [현황 요약](#현황-요약)
2. [Phase 5 목표](#phase-5-목표)
3. [작업 항목](#작업-항목)
4. [우선순위](#우선순위)
5. [일정 및 리소스](#일정-및-리소스)

---

## 현황 요약

### ✅ Phase 4 완료 (2026-05-09)

| 구성요소 | 상태 | 파일 |
|---------|------|------|
| 엔진 (Phase 1-2) | ✅ 완료 | `src/core/` (8개) |
| UI 기본 (Phase 3) | ✅ 완료 | `src/ui/screens/`, `src/ui/styles/` |
| UI 통합 (Phase 4 초) | ✅ 완료 | `src/ui/app.py`, 카메라 워커, 세션 관리 |
| 설정 화면 (Phase 4 후) | ✅ 완료 | `src/ui/widgets/settings_widgets.py` |
| 통계 차트 (Phase 4 후) | ✅ 완료 | `src/ui/widgets/chart_widgets.py` |

### ⚠️ 알려진 이슈

| 이슈 | 심각도 | 설명 |
|------|--------|------|
| 설정값 미적용 | 🟡 중간 | 설정값이 저장되지만 실제 동작에 미반영 |
| 알림음 미구현 | 🟡 중간 | 설정에는 있으나 재생 로직 없음 |
| 팝업 위치 고정 | 🟡 중간 | 설정에 있어도 항상 중앙에만 표시 |
| 성능 (카메라) | 🟢 낮음 | 30 FPS 유지되나 고해상도 시 최적화 필요 |
| 문서 부족 | 🟢 낮음 | 사용자 가이드/개발자 문서 없음 |

---

## Phase 5 목표

### 1차 목표 (필수)
- ✅ **설정값 실제 적용**: 사용자가 설정한 값이 앱 동작에 반영
- ✅ **통합 테스트**: 전체 워크플로우 정상 작동 확인
- ✅ **버그 수정**: 알려진 이슈 해결

### 2차 목표 (선택)
- 성능 최적화
- 사용자 매뉴얼 작성
- 배포/패키징 준비

---

## 작업 항목

### 1. 설정값 실제 적용 (3-4시간)

#### 1.1 알림 설정 연동
**파일**: `src/ui/app.py`, `src/core/state_machine.py`

```python
# 변경 전: 고정값으로 알림 발생
if event.to_state == "bad_posture":
    alert_requested.emit("나쁜 자세 감지", "바른 자세로 유지하세요")

# 변경 후: 설정값 확인 후 알림 발생
if self.settings_config.notification_enabled:
    if event.to_state == "bad_posture":
        if time.time() - self._last_alert_time > self.settings_config.notification_interval:
            alert_requested.emit(...)
```

**작업 항목**:
- `BarorokApp._save_settings()` 수정: 설정값을 상태 머신/카메라에 전달
- `StateMachine` 생성자에 `settings_config` 주입
- 알림 간격 설정값 적용

#### 1.2 팝업 위치 동적 설정
**파일**: `src/ui/app.py`

```python
# 현재: 고정 위치
self.alert_popup = AlertPopup()
self.alert_popup.move(...)  # 항상 중앙

# 변경: 설정값에 따라 위치 결정
if self.settings_config.popup_position == "center":
    # 화면 중앙
else:
    # 우측 하단
```

#### 1.3 팝업 자동 닫기 시간 적용
**파일**: `src/ui/app.py`

```python
# 현재: 고정 3초
self.alert_hide_timer.start(3000)

# 변경: 설정값 사용
timeout_ms = self.settings_config.popup_auto_close_time * 1000
self.alert_hide_timer.start(timeout_ms)
```

### 2. 알림음 구현 (2-3시간)

**파일**: `src/core/sound_manager.py` (새 파일)

```python
class SoundManager:
    """알림음 관리"""
    
    def __init__(self, volume: int = 70):
        self.volume = volume
        # pygame or winsound 사용
    
    def play_alert(self):
        """알림음 재생"""
```

**구현 옵션**:
1. `winsound` (Windows 기본, 단순한 비프음)
2. `pygame` (추가 의존성, 고품질 음성)
3. 시스템 사운드 재생

**작업 항목**:
- SoundManager 클래스 구현
- BarorokApp에 주입
- 알림 발생 시 `play_alert()` 호출
- 소리 크기 설정값 적용

### 3. 자동 시작 기능 (1-2시간)

**파일**: `src/ui/app.py`

```python
def _start_detection(self):
    """감지 시작"""
    # Baseline 이미 설정되어 있고, auto_start_detection이 True면
    if self.baseline_manager.has_baseline() and self.settings_config.auto_start_detection:
        # 자동으로 감지 시작
        self._start_detection_impl()
```

### 4. 통합 테스트 및 검증 (2-3시간)

**테스트 시나리오**:
1. **Baseline 촬영** → Baseline 저장 확인
2. **감지 시작** → 상태 머신 초기화 확인
3. **자세 감지** → 상태 전이 확인
4. **경고 발생** → 알림 팝업 표시, 경고음 재생
5. **감지 중지** → 세션 저장 확인
6. **통계 확인** → 차트 플로팅 확인
7. **설정 변경** → 설정값 저장/로드 확인

**검증 항목**:
- ✅ 모든 화면 전환 정상
- ✅ 설정값 저장/로드
- ✅ 실시간 자세 감지
- ✅ 경고 알림 및 소리
- ✅ 세션 데이터 저장
- ✅ 통계 차트 표시

### 5. 버그 수정 (1-2시간)

**알려진 버그**:
- [ ] 화면 전환 시 차트 렌더링 지연
- [ ] 빠른 상태 전이 시 경고 중복
- [ ] 카메라 해제 시 에러

### 6. 문서화 (1-2시간)

**작성 문서**:
1. **사용자 매뉴얼** (`docs/USER_GUIDE.md`)
   - 설치 및 시작
   - 기본 사용법
   - 설정 가이드
   - 트러블슈팅

2. **개발자 가이드** (`docs/DEVELOPER_GUIDE.md`)
   - 아키텍처 개요
   - 주요 컴포넌트 설명
   - 확장 방법
   - 테스트 방법

3. **API 문서** (`docs/API.md`)
   - 주요 클래스/메서드
   - 신호/슬롯 매핑
   - 데이터 구조

---

## 우선순위

### 1순위 (필수)
- [ ] 설정값 실제 적용
- [ ] 통합 테스트
- [ ] 버그 수정

### 2순위 (권장)
- [ ] 알림음 구현
- [ ] 자동 시작 기능
- [ ] 문서화

### 3순위 (선택)
- [ ] 성능 최적화
- [ ] 고급 기능 추가 (예: 데이터 내보내기)

---

## 일정 및 리소스

### 예상 일정

| 항목 | 시간 | 상태 |
|------|------|------|
| 1. 설정값 실제 적용 | 3-4h | 🔲 미시작 |
| 2. 알림음 구현 | 2-3h | 🔲 미시작 |
| 3. 자동 시작 기능 | 1-2h | 🔲 미시작 |
| 4. 통합 테스트 | 2-3h | 🔲 미시작 |
| 5. 버그 수정 | 1-2h | 🔲 미시작 |
| 6. 문서화 | 1-2h | 🔲 미시작 |
| **합계** | **10-16h** | |

### 리소스 요구사항
- Python 3.9+
- PyQt6, MediaPipe, OpenCV
- `winsound` (Windows 기본 포함) 또는 `pygame` (선택)

---

## 다음 단계

1. **우선순위 확정**: 위 작업 중 진행할 항목 선택
2. **구현 순서 결정**: 순차 또는 병렬 진행
3. **테스트 계획 수립**: 각 기능별 테스트 시나리오 작성
4. **배포 전략**: 버전 관리, 릴리스 노트 작성

---

## 참고 사항

- Phase 4는 5월 9일 완료/푸시 (`wooseong` 브랜치)
- 다음 메인 브랜치 병합 전에 Phase 5 완료 권장
- 향후 Phase 6 (고급 기능) 계획 가능
