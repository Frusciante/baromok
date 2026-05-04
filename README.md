# 바로목 (Barorok) - 나쁜 자세 측정 시스템

MediaPipe 기반 실시간 상체 자세 분석 및 PyQt UI를 활용한 데스크톱 애플리케이션

## 프로젝트 개요

웹캠을 통해 사용자의 상체 자세를 실시간으로 측정하고, MediaPipe를 활용한 자동 분석 결과를 PyQt 기반 UI로 시각화하며, 나쁜 자세 감지 시 경고를 제공합니다.

### 주요 기능

- **실시간 자세 분석**: 웹캠 프리뷰에서 얼굴/어깨 랜드마크 추출 및 자세 지표 계산
- **Baseline 기반 판정**: 초기 바른자세 촬영 후 변화량 추적
- **다양한 자세 감지**:
  - 의자에 누운 자세(기댄 자세)
  - 거북목 자세
  - 다리 꼰 자세(어깨 비대칭)
  - 턱 괸 자세(추정)
- **사용자 친화적 UI**: 초기 촬영, 메인 허브, 설정, 통계, 감지 진행, 경고 등 6개 화면
- **상태 머신**: NORMAL → WARNING → BAD_POSTURE 상태 전이
- **경고 및 알림**: 소리, 팝업 알림 (사용자 커스터마이징 가능)

## 기술 스택

| 항목 | 버전 |
|-----|-----|
| Python | 3.9+ |
| MediaPipe | 0.10.33 |
| OpenCV | 4.8.1.78 |
| PyQt | 6.7.0 |
| NumPy | 1.24.3 |

## 설치

### 1. 저장소 클론
```bash
git clone <repository-url>
cd baromok
```

### 2. Python 가상 환경 생성 (권장)
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. MediaPipe 모델 파일 다운로드 (선택)
필요한 모델 파일(`.task`)을 `assets/models/` 디렉토리에 다운로드하세요.
- `pose_landmarker.task` - 포즈 감지
- `face_landmarker.task` - 얼굴 랜드마크
- (기타 필요한 모델)

## 사용 방법

### 1. 애플리케이션 실행
```bash
python main.py
```

### 2. 기본 자세 촬영
- 애플리케이션 시작 후 "초기 바른자세 촬영" 화면에서 바른 자세로 앉아 있습니다.
- "촬영" 버튼을 누르고 5초간 기준 자세를 유지합니다.
- 기준 자세가 저장되면 메인 허브 화면으로 전환됩니다.

### 3. 감지 시작
- "바로목 감지 시작" 버튼을 누르면 실시간 자세 분석이 시작됩니다.
- 사용 시간, 현재 자세 상태, 웹캠 프리뷰가 화면에 표시됩니다.

### 4. 설정 조정
- "환경 설정"에서 알림 방식, 소리 크기, 팝업 위치를 커스터마이징할 수 있습니다.

### 5. 통계 확인
- "나의 통계"에서 최근 세션의 자세 유지율 추이를 확인할 수 있습니다.

## 프로젝트 구조

```
baromok/
├── src/
│   ├── core/                    # 자세 분석 엔진
│   │   ├── posture_engine.py
│   │   ├── landmark_extractor.py
│   │   ├── indicator_calculator.py
│   │   ├── baseline_manager.py
│   │   ├── judgment_engine.py
│   │   └── state_machine.py
│   ├── ui/                      # PyQt UI
│   │   ├── main_window.py
│   │   ├── screens/             # 화면 모듈
│   │   ├── widgets/             # 커스텀 위젯
│   │   └── styles/              # 테마 및 스타일
│   ├── utils/                   # 유틸리티
│   │   ├── logger.py
│   │   └── helpers.py
│   └── config.py                # 설정 관리
├── assets/
│   ├── models/                  # MediaPipe .task 파일
│   ├── images/                  # 아이콘/일러스트
│   └── sounds/                  # 경고음 (선택)
├── .github/
│   └── rules/                   # 자세 정의 및 규칙
├── requirements.txt             # 의존성
├── main.py                      # 진입점
└── README.md
```

## 설정 파일

### `posture_definition_criteria.json`
자세 판정 기준, 임계값, 가중치는 `.github/rules/operation/posture_definition_criteria.json`에서 관리됩니다.

### `.env` (선택)
애플리케이션 설정을 `.env` 파일로 커스터마이징할 수 있습니다:
```
CAMERA_INDEX=0
CAMERA_FPS=30
ENABLE_SOUND_ALERT=true
ENABLE_POPUP_ALERT=true
ALERT_SOUND_VOLUME=70
```

## 개발 및 기여

### 문서
- [자세 정의서](.github/rules/posture_definition.md)
- [자세 측정 운영 규칙](.github/rules/operation/posture_operation.md)
- [UI 규칙](.github/rules/ui/posture_ui.md)
- [구현 계획서](.github/rules/features_log/posture_measurement_system/01_implementation_plan.md)

### 개발 지침
- Python 버전: 3.9 이상
- 코드 스타일: PEP 8
- 로깅: `src/utils/logger.py` 사용
- 설정: `src/config.py`에서 관리

## 알려진 문제 및 제한사항

- 현재 정면 카메라 전용 (측면 카메라 미지원)
- Windows 10+ 환경에서 테스트됨
- 웹캠 권한이 필요합니다

## 향후 계획

- [ ] 모바일 버전 (Android/iOS)
- [ ] 클라우드 기반 통계 저장
- [ ] AI 기반 자세 교정 피드백
- [ ] 다중 사용자 지원

## 라이센스

[라이센스 정보 추가 예정]

## 문의 및 피드백

이슈 및 피드백은 GitHub Issues에 등록해주세요.

---

**버전**: 0.1.0  
**최종 업데이트**: 2026-04-29
