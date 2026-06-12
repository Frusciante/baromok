# Baseline 시스템 문서

## 개요

**Baseline**은 사용자의 기본 자세 특성을 학습하는 보정 데이터 세트입니다. 시스템은 개인별 신체 비율(어깨 너비, 얼굴 간격 등)을 수집하여 자세 판정 시 개인화된 기준을 제공합니다.

## 핵심 개념

### Baseline 수집 워크플로우

1. **사용자가 "감지 시작" 시도**
2. **시스템이 저장된 Baseline 검증**
   - 파일 존재 여부 확인
   - 5가지 유효성 검사 수행
3. **Baseline 없음 시 사용자 리다이렉트**
   - 메시지: "저장된 Baseline 파일을 찾을 수 없습니다."
   - 사용자 확인 → Baseline 캡처 화면으로 이동
4. **3단계 Baseline 수집**
   - 각 단계: 몸을 옆으로 기울임, 정면 자세, 반대쪽 기울임
   - 총 약 1분 소요
5. **프레임 검증**
   - 최소 120 프레임 이상 수집 필요
   - 미충족 시 재수집 안내
6. **Baseline 저장**
   - `data/baseline.json` 에 저장
   - RANSAC 모델 샘플 데이터 포함

### 파일 구조

```
data/baseline.json
├── timestamp: 수집 시간 (ISO 8601 형식)
├── collection_duration_seconds: 수집 소요 시간
├── frame_count: 수집된 프레임 수
└── metrics: 수집된 지표 딕셔너리
    ├── cheek_distance: 얼굴 간격 (정규화값)
    ├── shoulder_width: 어깨 너비 (정규화값)
    ├── shoulder_tilt_deg: 어깨 기울임 각도
    ├── neck_offset: 목 오프셋
    ├── eye_line_tilt: 눈선 기울임
    ├── eye_distance: 눈 간격
    ├── chin_occlusion: 턱 폐색도
    ├── ransac_x_samples: RANSAC X 샘플 (배열)
    ├── ransac_y_samples: RANSAC Y 샘플 (배열)
    └── ransac_s_samples: RANSAC 상태 샘플 (배열)
```

## Baseline 유효성 검증 (5단계)

### Tier 1: 구조 검증
**목적**: 파일이 올바른 JSON 형식이고 필수 키가 존재하는지 확인

- ✓ `data/baseline.json` 파일 존재
- ✓ JSON 파싱 가능
- ✓ `baseline_metrics` 객체 존재
- ✓ `metrics` 딕셔너리 존재
- ✓ 필수 키 존재: `cheek_distance`, `shoulder_width`

**실패 시**: 파일을 다시 캡처하세요

### Tier 2: 프레임 수 검증
**목적**: 충분한 데이터 샘플이 수집되었는지 확인

- ✓ `frame_count` ≥ `minimum_valid_frame_count` (기본값: **120**)

**실패 시**: Baseline을 더 오래 수집하거나 다시 캡처하세요

**참고**: 앱에서 ~40초(1200 프레임 @ 30fps) 수집 시 ~120프레임이 저장됨

### Tier 3: RANSAC 모델 검증
**목적**: 자세별 거리 및 높이 관계가 학습되었는지 확인

- ✓ **기본 모델**: 어깨 너비와 광대 거리 간의 관계 학습 (`ransac_x_samples`, `ransac_y_samples`)
- ✓ **높이 모델**: 거리 대리 지표(어깨/눈)와 머리 높이 간의 관계 학습 (`ransac_hx_samples`, `ransac_hy_samples`)
- ✓ RANSAC 모델 적합 가능
- ✓ 인라이어 수 ≥ **10** (회귀 관계가 신뢰성 있음)

**RANSAC이란**: 자세와 지표 간의 선형 관계를 학습하며, 보정 중 발생하는 불필요한 움직임을 이상치로 제거하여 정확한 기준 모델을 도출합니다.

**실패 시**: Baseline을 다시 캡처하세요. 자세 변화가 너무 크거나 랜드마크 감지 오류 가능성

### Tier 4: 메트릭 값 유효성
**목적**: 수집된 지표가 물리적으로 타당한지 확인

- ✓ 모든 값이 유한 (NaN, Inf 아님)
- ✓ 정규화 지표 범위: **0 < value ≤ 1**
- ✓ 각 지표가 신체 비율을 정확히 반영

**범위 초과 시나리오**:
- `cheek_distance > 1`: 얼굴이 이미지 영역을 초과
- `shoulder_width > 1`: 어깨 폭이 이미지 폭 초과
- `cheek_distance ≤ 0`: 음수 또는 0값 (불가능)

**실패 시**: 카메라 각도 조정 후 다시 캡처하세요

### Tier 5: 타임스탬프 신선도 & 편차 검증
**목적**: 오래된 또는 이상한 Baseline이 감지되는지 확인

- ⚠️ **경고 레벨**: 타임스탬프가 **30일 초과**
  - 사람의 체형이 변할 수 있으므로 주기적 재캡처 권장
- ⚠️ **경고 레벨**: 어깨 너비 기울임 편차 > **0.2**
  - 좌우 대칭이 맞지 않음 (자세 불안정)

**로그 예시**:
```
[WARNING] Baseline 타임스탐프 신선도 경고: 45일 경과
[WARNING] Baseline 어깨 기울임 편차 경고: 0.25 > 0.2
```

**조치**: 경고 시 언제든 "Baseline 재캡처" 메뉴에서 새로 수집 가능

## 사용자 메시지

### 감지 시작 시 Baseline 없음
```
제목: Baseline 필요
내용: 저장된 Baseline 파일을 찾을 수 없습니다.

Baseline 캡처 화면으로 이동하겠습니다.
'확인'을 누르면 Baseline 캡처 화면으로 이동합니다.

[확인] [취소]
```

### Baseline 검증 실패 상세 메시지 (향후)
```
1. "Baseline 파일이 손상되었습니다. 다시 캡처해주세요."
2. "수집된 프레임이 부족합니다 (현재: 87, 필요: 120)."
3. "Baseline RANSAC 모델이 학습되지 않았습니다."
4. "메트릭 값이 유효한 범위를 초과합니다."
5. "Baseline이 오래되었습니다 (35일). 재캡처를 권장합니다."
```

## 코드 구조

### BaselineManager (`src/core/baseline_manager.py`)

**주요 메서드**:

```python
def is_baseline_valid() -> bool:
    """5단계 Baseline 유효성 검증"""
    # Tier 1-5 검사 수행
    # 실패 시 각 단계별 로그 출력
    # True/False 반환

def load_baseline_from_file(filepath: str = None) -> bool:
    """baseline.json 파일 로드 및 RANSAC 모델 복원"""
    # 파일 읽기 → JSON 파싱
    # BaselineMetrics 객체 생성
    # RANSAC 샘플로부터 모델 복원
    # True/False 반환

def start_baseline_collection() -> None:
    """Baseline 수집 시작"""
    # 수집 상태 초기화
    # 프레임 카운터 리셋

def finish_baseline_collection() -> None:
    """Baseline 수집 완료 및 저장"""
    # 프레임 수 검증
    # save_baseline_to_file() 호출
    # 최종 검증 수행

def save_baseline_to_file() -> None:
    """baseline.json 파일에 저장"""
    # BaselineMetrics.to_dict() 호출
    # JSON 직렬화 및 파일 기록
```

### 앱 통합 (`src/ui/app.py`)

**_start_detection() 메서드**:
```python
def _start_detection(self):
    # 1. Baseline 유효성 검증
    baseline_ok = self.baseline_manager.is_baseline_valid()
    
    # 2. 파일 로드 시도
    if not baseline_ok:
        loaded = self.baseline_manager.load_baseline_from_file()
        if loaded:
            baseline_ok = self.baseline_manager.is_baseline_valid()
    
    # 3. 실패 시 사용자 확인 대화상자
    if not baseline_ok:
        msg = QMessageBox(...)
        msg.setText("저장된 Baseline 파일을 찾을 수 없습니다.\n\n"
                    "Baseline 캡처 화면으로 이동하겠습니다.\n"
                    "'확인'을 누르면 Baseline 캡처 화면으로 이동합니다.")
        ret = msg.exec()
        if ret == QMessageBox.StandardButton.Ok:
            self.switch_screen(0)  # Baseline 화면
        return
    
    # 4. Baseline 있으면 감지 시작
    self.camera_worker.start()
    self.switch_screen(4)  # Detection 화면
```

## 테스트 시나리오

### 시나리오 1: Baseline 없음
1. 앱 시작 (baseline.json 파일 없음)
2. "감지 시작" 클릭
3. **예상**: 검증 실패, 메시지 표시, 확인 시 Baseline 화면으로 이동

### 시나리오 2: Baseline 캡처
1. Baseline 화면에서 "시작" 클릭
2. 3단계 수집 진행 (~1분)
3. **예상**: 최소 120 프레임 수집, 파일 저장

### 시나리오 3: 유효한 Baseline으로 감지
1. 저장된 Baseline.json 존재
2. "감지 시작" 클릭
3. **예상**: 모든 검증 통과, Detection 화면으로 전환

### 시나리오 4: 손상된 Baseline
- 수정된 baseline.json (키 부재, 범위 초과 등)
- **예상**: 검증 실패, 적절한 단계 로그, 리다이렉트

## 트러블슈팅

### 문제: "Baseline 프레임 부족" 메시지
**원인**: 수집 중 프레임 드롭, 렌드마크 감지 실패

**해결**:
1. 조명 확인 (충분한 밝기)
2. 카메라 렌즈 청소
3. 천천히 자세 변경하며 재수집

### 문제: "RANSAC 모델 복원 실패"
**원인**: 이전 버전의 baseline.json, 샘플 데이터 부재

**해결**: 새로운 Baseline 캡처

### 문제: "메트릭 범위 초과"
**원인**: 카메라 각도 부적절, 신체 일부 미포함

**해결**: 
- 카메라를 팔길이 거리, 어깨 높이에 위치
- 얼굴과 어깨 전체가 보여야 함

## 성능 지표

| 지표 | 값 | 설명 |
|------|-----|------|
| 최소 프레임 수 | 120 | Baseline 저장 최소 기준 |
| 권장 수집 시간 | ~40초 | 사용자 편의를 위한 목표 |
| RANSAC 최소 인라이어 | 10 | 모델 신뢰성 기준 |
| Baseline 유효 기간 | 30일 | 체형 변화 고려 |
| 어깨 편차 임계값 | 0.2 | 자세 대칭성 검사 |

## 버전 히스토리

### v1.0 (2026-05-19)
- ✅ 5단계 Baseline 검증 시스템 구현
- ✅ 파일 없음 시 사용자 리다이렉트
- ✅ 상세 로깅 및 메시지
- ✅ RANSAC 모델 복원 및 검증

## 참고 자료

- MediaPipe Pose: 신체 랜드마크 감지
- RANSAC: 회귀 분석을 통한 자세-거리 관계 학습
- PyQt6 QMessageBox: 사용자 확인 대화상자
