# 바로목 (baromok) - 나쁜 자세 측정 시스템

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
- **사용자 친화적 UI**: 초기 촬영, 메인 허브, 설정, 통계, 감지 진행과 경고 팝업으로 구성된 화면 흐름
- **상태 머신**: NORMAL → WARNING → BAD_POSTURE 상태 전이
- **경고 및 알림**: 소리, 팝업 알림 (사용자 커스터마이징 가능)

## 기술 스택

| 항목 | 버전 |
|-----|-----|
| Python | 최신 권장 버전 |
| MediaPipe | 설정 파일 참조 |
| OpenCV | 설정 파일 참조 |
| PyQt | 설정 파일 참조 |
| NumPy | 설정 파일 참조 |

## 설치

### 저장소 클론
```bash
git clone https://github.com/Frusciante/baromok.git
cd baromok
```

### 가상 환경 생성 (권장)
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

### 의존성 설치
```bash
pip install -r requirements.txt
```

### 모델 파일 다운로드
필요한 모델 파일(`.task`)을 지정된 디렉토리에 배치하십시오. 상세 목록은 프로젝트 구조를 참조하십시오.

## 사용 방법

### 애플리케이션 실행
```bash
python main.py
```

## 프로토타입 통합 정보

이 저장소에는 프로토타입 알고리즘이 통합되어 있습니다.

- **캘리브레이션**: 다단계 거리 분할 수집을 통해 지표 간 관계를 회귀 모델로 보정합니다. 설정은 <a href=".github/rules/operation/posture_definition_criteria.json">baseline.capture</a>를 참조하십시오.
- **필터링**: 지표 수준의 필터를 사용하여 노이즈를 억제합니다. 설정은 <a href=".github/rules/operation/posture_definition_criteria.json">filters</a>를 참조하십시오.
- **판단 로직**: 스코어링 및 시간 기반 상태 확인 로직이 통합되어 있습니다.

## 사용 흐름

### 거리 캘리브레이션 (Baseline 촬영)
- 애플리케이션 시작 후 캘리브레이션 화면이 나타납니다.
- "캘리브레이션 시작" 버튼을 누르면 다단계 데이터 수집이 진행됩니다.
- 단계별 대기 시간과 수집 횟수는 설정 파일을 따릅니다.
- 아주 가까운 거리부터 먼 거리까지 앞뒤로 움직이며 데이터를 제공해 주세요.
- 수집 중에는 자세를 유지해야 정확한 기준점이 생성됩니다.
- 성공적으로 완료되면 메인 화면으로 전환됩니다.

### 감지 시작 및 알림
- 감지 시작 버튼을 누르면 실시간 분석이 수행됩니다.
- 설정에서 알림 방식 및 감도를 조정할 수 있습니다.

## 프로젝트 구조

지정된 디렉토리 구조에 따라 핵심 엔진, UI, 유틸리티, 모델 및 규칙 파일이 관리됩니다.

## 설정 파일

자세 판정 기준 및 임계값은 아래 경로에서 관리됩니다.
- <a href=".github/rules/operation/posture_definition_criteria.json">.github/rules/operation/posture_definition_criteria.json</a>

## 개발 및 기여

### 관련 문서
- <a href=".github/rules/posture_definition.md">자세 정의서</a>
- <a href=".github/rules/operation/posture_operation.md">자세 측정 운영 규칙</a>
- <a href=".github/rules/operation/posture_system_summary.md">기술 설계 요약</a>

## 라이센스

[라이센스 정보 추가 예정]
