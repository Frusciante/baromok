# 나쁜 자세 측정 시스템(바로록) - 구현 계획서 v0.1

## 문서 정보
- 기능명: 나쁜 자세 측정 시스템(바로록) - MediaPipe 기반 상체 자세 분석 및 PyQt UI
- 작성일: 2026-04-29
- 참조: `.github/copilot-instructions.md`, 자세 정의서, 운영 규칙, UI 규칙, 체크리스트

## 1. 기능 개요

### 1.1 프로젝트 목표
웹캠을 통해 사용자의 상체 자세를 실시간으로 측정하고, MediaPipe 기반 자동 분석 결과를 PyQt UI로 시각화하며, 나쁜 자세 감지 시 경고를 제공하는 데스크톱 애플리케이션을 구현한다.

### 1.2 주요 특징
- **실시간 자세 분석**: 웹캠 프리뷰에서 얼굴/어깨 랜드마크 추출 및 자세 지표 계산
- **Baseline 기반 판정**: 초기 바른자세 촬영 후 변화량 추적
- **상태 머신**: NORMAL → WARNING → BAD_POSTURE 상태 전이
- **사용자 친화적 UI**: 6개 화면(초기 촬영, 메인 허브, 설정, 통계, 감지 진행, 경고)
- **다양한 자세 감지**:
  - 의자에 누운 자세(기댄 자세)
  - 거북목 자세
  - 다리 꼰 자세(어깨 비대칭)
  - 턱 괸 자세(추정)

---

## 2. 구현 단계 및 산출물

### Phase 1: 프로젝트 기본 구조 설정 (1단계)
**목표**: 프로젝트 폴더 구조, 의존성 관리, 설정파일 준비

**산출물**:
- `src/` 폴더 구조 (core, ui, utils)
- `requirements.txt` 또는 `pyproject.toml`
- `config.py` - 상수/설정 관리
- `posture_definition_criteria.json` 로더 준비
- `.env` 템플릿 (선택)

**상세 작업**:
- [x] 폴더 구조 설계
  - `src/core/` - 자세 분석 엔진
  - `src/ui/` - PyQt 화면 및 레이아웃
  - `src/utils/` - 헬퍼 함수 및 로거
  - `assets/` - 이미지/모델 파일
  - `.github/rules/operation/` - 판정 기준 JSON
- [x] 의존성 정의
  - `opencv-python` (웹캠 입력)
  - `mediapipe==0.10.33` (자세 감지)
  - `PyQt6` (UI)
  - `numpy` (계산)
  - `pydantic` (설정 검증)
- [ ] 설정 관리 시스템
  - 판정 기준 JSON 로더
  - 애플리케이션 설정 (알림 방식, 소리, 팝업 위치 등)

**담당자**: 초기 설정
**예상 기간**: 1-2시간

---

### Phase 2: 자세 분석 엔진 (2단계)
**목표**: MediaPipe 통합, 지표 계산, 판정 로직 구현

**산출물**:
- `src/core/posture_engine.py` - 핵심 자세 분석 엔진
- `src/core/landmark_extractor.py` - MediaPipe 기반 랜드마크 추출
- `src/core/indicator_calculator.py` - 지표 계산 (cheek_distance, face_shoulder_ratio 등)
- `src/core/baseline_manager.py` - baseline 수집/저장/비교
- `src/core/judgment_engine.py` - 자세 판정 로직
- `src/core/state_machine.py` - 상태 머신 (NORMAL, WARNING, BAD_POSTURE)

**상세 작업**:
- [ ] **랜드마크 추출** (landmark_extractor.py)
  - MediaPipe holistic 대신 task 파일 사용
  - 필요 모델: pose, face_detection, hand (또는 face_landmarks)
  - 랜드마크 좌표, 신뢰도 반환
  - 프레임 단위 처리

- [ ] **지표 계산** (indicator_calculator.py)
  - `cheek_distance`: 양쪽 광대뼈 간 거리
  - `eye_distance`: 양쪽 눈 간 거리
  - `face_shoulder_ratio`: cheek_distance / shoulder_width
  - `shoulder_tilt_deg`: 좌우 어깨 기울기
  - `neck_offset`: 목과 어깨 정렬 오차
  - `eye_line_tilt`: 눈 수평선 기울기
  - `chin_occlusion`: 턱 가림 여부
  - `hand_near_face`: 손-얼굴 근접도
  - 노이즈 필터 (이동평균/중앙값)

- [ ] **Baseline 관리** (baseline_manager.py)
  - baseline 수집: `baseline.capture.duration_seconds` (5초) 적용
  - 수집 중 평균/중앙값 계산
  - baseline 저장 (파일 또는 메모리)
  - baseline 대비 변화량(%) 계산

- [ ] **자세 판정** (judgment_engine.py)
  - `recline` (의자에 누운 자세)
    - 조건: cheek_distance 감소, face_shoulder_ratio 감소
    - 임계값: `posture_types.recline.primary_conditions`
    - 지속시간: `posture_types.recline.sustain_seconds`
  - `forward_head` (거북목)
    - 조건: cheek_distance 증가, face_shoulder_ratio 증가
    - 임계값: 관련 threshold
    - 지속시간: 해당 sustain_seconds
  - `crossed_leg_estimated` (다리 꼰 자세 추정)
    - 조건: shoulder_tilt_deg 증가
    - 반복 창: `repeat_window_seconds`
    - 지속시간: `sustain_seconds`
  - `chin_rest_estimated` (턱 괸 자세 추정)
    - 조건: chin_occlusion, hand_near_face
  - 프레임 점수 계산: `frame_scoring.likelihood_formulas`

- [ ] **상태 머신** (state_machine.py)
  - 상태: NORMAL, WARNING, BAD_POSTURE
  - 전이 규칙: `global_rules.state_machine.transitions`
  - 상태 변경 시 이벤트 발생 (UI 업데이트용)
  - 타이머 및 누적 로직

**담당자**: 자세 분석 엔진 개발
**예상 기간**: 8-12시간

---

### Phase 3: PyQt 기반 UI 구현 (3단계)
**목표**: 6개 화면 구현, 상태 표시, 실시간 자세 업데이트

**산출물**:
- `src/ui/main_window.py` - 메인 윈도우 및 화면 전환
- `src/ui/screens/baseline_screen.py` - 초기 바른자세 촬영 화면
- `src/ui/screens/hub_screen.py` - 메인 허브 화면
- `src/ui/screens/settings_screen.py` - 환경 설정 화면
- `src/ui/screens/statistics_screen.py` - 통계 화면
- `src/ui/screens/detection_screen.py` - 감지 진행 화면
- `src/ui/widgets/alert_popup.py` - 경고 팝업/토스트
- `src/ui/styles/theme.py` - PyQt 스타일시트 (보라/핑크 색상)

**상세 작업**:
- [ ] **기본 UI 구조**
  - QMainWindow 기반 메인 윈도우
  - QStackedWidget를 사용한 화면 전환
  - 상단 헤더(앱명, 최소화/닫기)
  - 하단 안내 문구 고정

- [ ] **초기 바른자세 촬영 화면**
  - 타이틀 배지
  - 웹캠 프리뷰 카드 (QLabel + OpenCV 프레임)
  - 촬영 전 체크리스트 (거리, 자세, 각도 등)
  - "촬영" 버튼 (baseline 수집 5초)
  - 진행 상황 표시 (카운트다운)

- [ ] **메인 허브 화면**
  - 중앙 일러스트 (또는 플레이스홀더)
  - "환경 설정" 버튼
  - "나의 통계" 버튼
  - "바로록 감지 시작" 버튼

- [ ] **환경 설정 화면**
  - 좌측 카테고리 버튼 (알림 설정, 소리, 팝업, 자동 시작)
  - 우측 설정값 UI
    - 알림 방식: 토글 (소리 알림/팝업 알림)
    - 소리 크기: 슬라이더 (0~100)
    - 팝업 위치: 라디오 버튼 (중앙/상단)
    - 자동 시작: 토글 (ON/OFF)
  - "확인" 버튼 (설정 저장)

- [ ] **통계 화면**
  - 타이틀 ("최근 10개 세션 바른자세 유지율")
  - 막대 차트 (날짜별 유지율)
  - 평균선 표시
  - 강조 막대 및 툴팁 (날짜, 유지율, 시간)

- [ ] **감지 진행 화면**
  - 상단 좌측: 상태 표시 (감지중/일시정지) 토글
  - 상단 우측: 환경 설정 바로가기
  - 중앙: 사용 시간 표시 + 웹캠 프리뷰
  - 중앙 하단: 현재 자세 상태 라벨 (바른 자세/경고/나쁜 자세)
  - 하단: "감지 일시정지", "감지 종료" 버튼

- [ ] **경고 UI**
  - 상단 배너형 경고
  - 카드형 토스트 (둥근 모서리, 반투명)
  - 중복 경고 억제 (쿨다운, 예: 3초)
  - 메시지 템플릿
    - 기본(폴백): "잘못된 자세가 감지되었습니다. 자세를 바르게 고쳐 앉아 주세요."
    - 자세별: "거북목/턱 괸 자세/어깨 비대칭" 등 구체 안내

- [ ] **스타일 및 접근성**
  - 테마 (보라/핑크 색상)
  - DPI 스케일 대응 (100/125/150%)
  - 폰트 스케일 조정
  - 키보드 포커스/탭 순서
  - 상태 색상 + 텍스트 라벨 병행

**담당자**: UI 개발
**예상 기간**: 10-15시간

---

### Phase 4: 엔진 ↔ UI 통합 (4단계)
**목표**: 실시간 자세 데이터 수집, UI 업데이트, 상태 동기화

**산출물**:
- `src/app.py` - 메인 애플리케이션 (QThread 기반 자세 분석 스레드)
- `src/signals.py` - PyQt Signal/Slot 정의 (프레임, 자세 상태, 알림 등)
- `src/session_manager.py` - 세션 관리 (사용 시간, 유지율, 통계 저장)

**상세 작업**:
- [ ] **백그라운드 자세 분석 스레드**
  - QThread 기반 별도 스레드
  - 웹캠 프레임 읽기 및 자세 분석
  - 상태 변경 시 Signal 발생 (frame_updated, posture_changed, warning_triggered 등)

- [ ] **신호 연결**
  - 자세 엔진 → UI 업데이트
  - 상태 변경 → 화면 전환/버튼 활성화
  - 경고 발생 → 팝업/배너 표시, 소리 재생

- [ ] **세션 관리**
  - 감지 시작/종료 타이밍
  - 자세별 유지 시간 누적
  - 유지율(%) 계산: (바른자세 시간 / 전체 시간) × 100
  - 세션 통계 저장 (날짜, 시간, 유지율)

- [ ] **설정 저장/복원**
  - JSON 기반 설정 파일
  - 애플리케이션 재시작 시 설정 복원
  - 자동 시작 옵션 (Windows 레지스트리 또는 스타트업 폴더)

**담당자**: 통합 개발
**예상 기간**: 6-8시간

---

### Phase 5: 검증 및 최적화 (5단계)
**목표**: 기능 테스트, 성능 최적화, 문서 동기화

**산출물**:
- 테스트 결과 보고서
- 성능 개선 사항 기록
- 문서 업데이트

**상세 작업**:
- [ ] **기능 테스트**
  - baseline 수집 및 저장 정확성
  - 자세 판정 기준 적용 확인 (임계값, 지속시간)
  - 상태 머신 전이 규칙 검증
  - 경고 반복 억제 확인
  - UI 화면 전환 및 버튼 동작

- [ ] **성능 및 안정성**
  - 프레임 처리 속도 (FPS 목표: 20~30)
  - CPU/메모리 사용률 모니터링
  - 웹캠 에러 처리 (미연결, 권한 거부 등)
  - 예외 상황 처리 (JSON 로딩 실패, MediaPipe 모델 로딩 실패)

- [ ] **접근성 및 사용성**
  - Windows DPI 스케일 대응 (100/125/150%)
  - 폰트 렌더링 (한글 포함)
  - 다양한 화면 해상도 테스트

- [ ] **문서 동기화**
  - 구현 결과 md 파일 작성
  - 코드 주석 및 docstring 작성
  - README.md 작성 (설치, 실행, 사용법)

**담당자**: QA/문서화
**예상 기간**: 4-6시간

---

## 3. 기술 스택 및 의존성

| 항목 | 버전 | 용도 |
|-----|-----|-----|
| Python | 3.9+ | 프로그래밍 언어 |
| MediaPipe | 0.10.33 | 자세/얼굴/손 랜드마크 추출 |
| OpenCV | 4.8+ | 웹캠 입력 및 프레임 처리 |
| PyQt | 6.x | UI 개발 |
| NumPy | 1.24+ | 수치 계산 |
| Pydantic | 2.x | 설정 검증 |
| pandas | 2.0+ | 통계 데이터 처리 (선택) |
| matplotlib/PyQtGraph | - | 차트 그리기 (선택) |

---

## 4. 파일 구조(예상)

```
baromok/
├── src/
│   ├── __init__.py
│   ├── app.py                          # 메인 애플리케이션
│   ├── signals.py                      # PyQt Signal/Slot
│   ├── session_manager.py              # 세션 관리
│   ├── config.py                       # 설정 관리
│   ├── core/
│   │   ├── __init__.py
│   │   ├── posture_engine.py           # 통합 자세 분석 엔진
│   │   ├── landmark_extractor.py       # 랜드마크 추출
│   │   ├── indicator_calculator.py     # 지표 계산
│   │   ├── baseline_manager.py         # baseline 관리
│   │   ├── judgment_engine.py          # 자세 판정
│   │   └── state_machine.py            # 상태 머신
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py              # 메인 윈도우
│   │   ├── screens/
│   │   │   ├── __init__.py
│   │   │   ├── baseline_screen.py
│   │   │   ├── hub_screen.py
│   │   │   ├── settings_screen.py
│   │   │   ├── statistics_screen.py
│   │   │   └── detection_screen.py
│   │   ├── widgets/
│   │   │   ├── __init__.py
│   │   │   ├── alert_popup.py
│   │   │   └── custom_widgets.py       # 커스텀 위젯
│   │   └── styles/
│   │       ├── __init__.py
│   │       └── theme.py                # 색상/스타일
│   └── utils/
│       ├── __init__.py
│       ├── logger.py                   # 로깅
│       └── helpers.py                  # 헬퍼 함수
├── assets/
│   ├── models/                         # MediaPipe .task 파일
│   ├── images/                         # 아이콘/일러스트
│   └── sounds/                         # 경고음 (선택)
├── .github/
│   └── rules/
│       ├── posture_definition.md
│       ├── operation/posture_operation.md
│       ├── operation/posture_definition_criteria.json
│       └── ui/posture_ui.md
├── requirements.txt                    # 의존성
├── main.py                             # 진입점
└── README.md
```

---

## 5. 주요 의사결정 사항

### 5.1 MediaPipe 모델 관리
- **선택**: task 파일 기반 (holistic, solutions 미사용)
- **이유**: 모듈화, 버전 고정, 의존성 명확화
- **구현**: 필요한 모델(pose, face_detection, hand 등)은 별도 로드

### 5.2 UI 화면 전환
- **선택**: QStackedWidget 기반
- **이유**: 상태에 따른 효율적 화면 전환, 메모리 관리

### 5.3 자세 분석 스레드
- **선택**: QThread 기반 백그라운드 처리
- **이유**: UI 응답성 유지, 실시간 분석

### 5.4 설정 저장
- **선택**: JSON 파일 기반 (로컬)
- **이유**: 간단한 구조, 사용자 환경 적응 가능

---

## 6. 위험요소 및 완화 전략

| 위험요소 | 가능성 | 영향 | 완화 전략 |
|--------|------|------|---------|
| MediaPipe 모델 로딩 실패 | 중 | 높음 | 예외 처리, 폴백 메커니즘, 명확한 에러 메시지 |
| 웹캠 권한 거부 (Windows) | 중 | 높음 | 권한 요청, 에러 다이얼로그 |
| 자세 판정 임계값 부정확 | 높음 | 중 | 사용자 피드백 기반 JSON 수정 가능하게 설계 |
| UI 레이아웃 DPI 문제 | 중 | 중 | DPI 테스트, QScalable 레이아웃 |
| 성능 저하 (CPU 사용률 높음) | 중 | 중 | 프레임 스킵, 해상도 조정, 멀티스레딩 최적화 |

---

## 7. 예상 일정

| 단계 | 예상 기간 | 완료 조건 |
|-----|---------|---------|
| Phase 1: 프로젝트 기본 구조 | 1-2시간 | 폴더 구조 완성, requirements.txt 작성 |
| Phase 2: 자세 분석 엔진 | 8-12시간 | 모든 지표 계산 및 판정 로직 검증 |
| Phase 3: PyQt UI | 10-15시간 | 6개 화면 완성, 스타일 적용 |
| Phase 4: 엔진↔UI 통합 | 6-8시간 | 실시간 자세 데이터 흐름 검증 |
| Phase 5: 검증 및 최적화 | 4-6시간 | 모든 기능 테스트 통과 |
| **총 예상 기간** | **29-43시간** | 프로젝트 완성 |

---

## 8. 검증 기준 (체크리스트 기반)

### 동작 체크리스트
- 기준 데이터(JSON) 로딩 ✓
- baseline 수집 및 지표 저장 ✓
- 모든 자세 판정 로직 적용 ✓
- 상태 머신 전이 규칙 구현 ✓
- MediaPipe task 파일 기반 모델 사용 ✓

### UI 체크리스트
- 공통 UI 품질 (DPI, 폰트, 포커스) ✓
- 6개 화면 완성 및 화면 전환 ✓
- 경고 UI (배너/토스트) 구현 ✓
- 메시지 정책 적용 ✓
- 상태 색상 + 텍스트 라벨 병행 ✓

---

## 9. 다음 단계

1. **본 계획서 검토 및 승인**: 사용자 피드백 수집, 수정 사항 반영
2. **Phase 1 실행**: 프로젝트 기본 구조 및 의존성 설정
3. **Phase 2~5 순차 진행**: 각 단계별 구현 → 검증 → 문서화
4. **통합 테스트**: 전체 기능 검증
5. **최종 배포**: README, 사용자 가이드 작성

---

**구현 준비 완료. 피드백을 기다립니다.**
