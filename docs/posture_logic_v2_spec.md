# 바로목 자세 감지 로직 V2 기획안

**문서 버전:** 2.0
**작성일:** 2026-05-25
**담당:** 알고리즘 팀원 (일요일까지 구현 목표)
**비교 대상:** V1 (광대 너비 / 어깨 너비 비율) → V2 (얼굴 지표 Δ% + 표준편차 기반 개인화)

---

## 1. V2 설계 철학

### 1.1 V1의 한계
- **고정 임계값**: 사용자 신체 비율 차이를 반영 못 함 (cheek_distance neutral 절대값이 사용자 간 ±29% 차이)
- **단일 비율**: 광대/어깨 만으로는 자세 유형 구분 어려움
- **어깨 의존**: 극단 각도(<100° 또는 >110°)에서 어깨 검출 불안정 → 판정 실패

### 1.2 V2 핵심 원칙
1. **얼굴 중심 지표 우선** — 어깨가 잡히면 보조로 활용, 안 잡혀도 판정 가능
2. **Δ% 기반 판정** — 절대값이 아닌 개인 baseline 대비 변화율
3. **neutral 1회 캘리브로 자동 임계값 도출** — UX 부담 V1과 동일
4. **표준편차 기반 임계값** — 사용자 흔들림 범위를 벗어나면 자세 변경 판정

### 1.3 UX 측면 (V1 대비)
- 캘리브레이션 절차: **변화 없음** (neutral 자세 1회 수집)
- 사용자에게는 V1과 같은 흐름, 알고리즘만 개선

---

## 2. 사용 지표 정의

### 2.1 주요 지표 (Primary)

| 지표 | 정의 | 정규화 | 주요 용도 |
|------|------|--------|----------|
| `cheek_distance` | 양 광대 사이 거리 | 프레임 너비 | 머리-카메라 거리 변화 |
| `eye_distance` | 양 눈 사이 거리 | 프레임 너비 | 머리-카메라 거리 변화 (보조) |
| `cheek_eye_ratio` | cheek_distance / eye_distance | 비율 | 각도 안정 지표 |
| `face_center_y` | 얼굴 중심 세로 좌표 | 프레임 높이 (0=상단, 1=하단) | 머리 상하 위치 |
| `eye_line_tilt` | 양 눈선의 기울기 (도) | - | **head_tilt 핵심 지표** |
| `eye_symmetry_ratio` | 좌우 눈 크기 대칭도 | 비율 | 비대칭 자세 검출 |
| `cheek_symmetry_ratio` | 좌우 광대 대칭도 | 비율 | 비대칭 자세 검출 |

### 2.2 보조 지표 (Auxiliary, 조건부 사용)

| 지표 | 조건 | 활용 |
|------|------|------|
| `shoulder_width` | 어깨 검출률 ≥ 70% (최근 5초) | forward_head_only vs full 구분, recline 보조 |
| `shoulder_tilt_deg` | 어깨 검출률 ≥ 70% | head_tilt 보조 검증, chin_rest 신호 |
| `chin_occlusion` | 모든 경우 | chin_rest 검출 |
| `hand_face_score` | 모든 경우 | chin_rest 검출 (손-얼굴 거리 + 폐색) |
| `chin_alignment_offset` | 모든 경우 | 자세 미세 보정 |

→ **어깨 지표는 검출 신뢰도에 따라 동적 활용**. 안 잡히면 얼굴 지표만으로 판정.

### 2.3 폐기 지표
- ❌ `vh_ratio` — 다중 사용자 검증에서 부호 반대 발생, 일부 사용자(U3)는 측정 자체 실패

---

## 3. 자세별 판정 로직

### 3.1 감지 대상 자세

| 자세 | 표시 라벨 | 주요 지표 | 보조 지표 |
|------|----------|----------|----------|
| `neutral` | 바른 자세 | (캘리브레이션 baseline) | - |
| `forward_head_only` | 거북목 경향 | `cheek_distance ↑`, `eye_distance ↑` | `face_center_y` 살짝 ↑ |
| `forward_head_full` | 몸 기울어진 거북목 의심 | `cheek_distance ↑↑`, **`shoulder_width ↑`** | `face_center_y ↑` |
| `recline` | 기댄 자세 의심 | `cheek_distance ↑↑`, `face_center_y ↓ or ↑` | `eye_line_tilt`, `shoulder_width ↓` |
| `head_tilt` | 고개 기울임 의심 | **`eye_line_tilt` 절대값 변화** | `cheek_symmetry_ratio ↓`, `shoulder_tilt_deg` |
| `chin_rest` | 턱 괸 자세 의심 | `hand_face_score ↑`, `eye_line_tilt`, `shoulder_tilt_deg` | `cheek_symmetry_ratio ↓` |

### 3.2 자세 충돌 처리 정책

여러 자세가 동시에 임계값을 넘는 경우:
- **baseline에서 가장 멀어진(deviation_score 최대) 자세 하나만** 표시
- 사용자가 가장 시급하게 인지해야 할 자세에 집중

```
deviation_score = sum(
    abs(Δ% of each primary indicator) * indicator_weight
) / number_of_indicators
```

### 3.3 판정 알고리즘 (의사 코드)

```python
def classify_posture(current, baseline, thresholds, sensitivity):
    """
    current:     현재 프레임 지표
    baseline:    neutral 캘리브레이션 (평균 + 표준편차)
    thresholds:  baseline에서 자동 도출된 사용자별 임계값
    sensitivity: 사용자 설정 (low / medium / high)
    """

    # ── Step 1: 각 자세 candidate score 계산 ──
    candidates = {}

    # chin_rest 검사 (기존 V1 로직 유지 — 가중치 기반)
    chin_score = compute_chin_rest_score(current, baseline)  # hand 0.30, eye 0.35, shoulder 0.20, neck 0.15
    if chin_score > thresholds.chin_rest:
        candidates["chin_rest"] = chin_score

    # head_tilt 검사 (eye_line_tilt 절대값 기준)
    if abs(current.eye_line_tilt - baseline.eye_line_tilt.mean) > thresholds.head_tilt_deg:
        candidates["head_tilt"] = compute_deviation_score(current, baseline, ["eye_line_tilt", "cheek_symmetry_ratio"])

    # forward_head_full 검사 (어깨 사용 가능 시만)
    if shoulder_detection_rate(5sec) >= 0.7:
        cheek_d = pct_change(current.cheek_distance, baseline.cheek_distance.mean)
        shoulder_d = pct_change(current.shoulder_width, baseline.shoulder_width.mean)
        if cheek_d > thresholds.forward_cheek and shoulder_d > thresholds.forward_shoulder:
            candidates["forward_head_full"] = compute_deviation_score(current, baseline, ["cheek_distance", "shoulder_width", "face_center_y"])

    # recline 검사
    cheek_d = pct_change(current.cheek_distance, baseline.cheek_distance.mean)
    if cheek_d > thresholds.recline_cheek:
        candidates["recline"] = compute_deviation_score(current, baseline, ["cheek_distance", "face_center_y"])

    # forward_head_only 검사
    if cheek_d > thresholds.forward_cheek:
        candidates["forward_head_only"] = compute_deviation_score(current, baseline, ["cheek_distance", "eye_distance"])

    # ── Step 2: Guards 적용 (오탐 방지) ──
    candidates = apply_guards(candidates, current, baseline)

    # ── Step 3: 가장 baseline에서 멀어진 자세 1개 선택 ──
    if not candidates:
        return ("neutral", 1.0)

    best_posture = max(candidates, key=candidates.get)
    confidence = compute_confidence(candidates[best_posture], thresholds[best_posture], sensitivity)
    return (best_posture, confidence)


def compute_confidence(deviation_score, threshold, sensitivity):
    """임계값 대비 얼마나 멀리 벗어났는지 = 신뢰도"""
    ratio = deviation_score / threshold  # 1.0이면 임계값 정확히 도달

    # 민감도 설정에 따른 confidence 기준 조정
    sensitivity_floor = {
        "high":   0.3,   # 예민 — 작은 변화도 감지
        "medium": 0.5,   # 보통
        "low":    0.7,   # 둔감 — 큰 변화만 감지
    }[sensitivity]

    confidence = min((ratio - 1.0) / 3.0 + 0.5, 1.0)  # ratio=1→0.5, ratio=4→1.0
    if confidence < sensitivity_floor:
        return 0.0  # 알림 안 띄움
    return confidence
```

### 3.4 Guards 시스템 (자세별 오탐 방지)

각 자세 candidate에 대해 다른 자세 신호가 너무 강하면 제외:

| 자세 | Guards |
|------|--------|
| `forward_head_only` | `abs(eye_line_tilt) < 12°` (없어야 함), `cheek_symmetry_ratio` 변화 < 15% |
| `forward_head_full` | `cheek_symmetry_ratio` 변화 < 15%, `shoulder_tilt_deg < 10°` |
| `recline` | `abs(eye_line_tilt) < 12°`, `shoulder_tilt_deg < 10°`, `cheek_symmetry_ratio` 변화 < 15% |
| `head_tilt` | (가드 없음 — eye_line_tilt가 주 신호) |
| `chin_rest` | (기존 V1 로직 — hand_face_score 기반) |

---

## 4. 캘리브레이션 절차

### 4.1 단순화된 1단계 캘리브레이션

**V1과 동일한 UX** — 사용자는 neutral 자세 1회만 수집

```
[감지 시작]
   ↓
[저장된 baseline_v2 있나?]
   ↓ No                       ↓ Yes
[캘리브레이션 화면]      [유효성 검증 → 사용]
   ↓
[3초 대기 → 10초 측정] (총 13초)
   ↓
[유효성 검증]
   ↓
[자동 임계값 도출 → baseline_v2.json 저장]
   ↓
[감지 시작]
```

### 4.2 수집 파라미터

| 항목 | 값 | 비고 |
|------|-----|------|
| `wait_seconds` | 3.0 | 사용자가 자세 잡을 시간 |
| `collect_seconds` | 10.0 | 안정적 평균/표준편차 도출용 |
| `minimum_valid_frames` | 100 | 검증 기준 |
| `expected_samples` | 100~300 | FPS 따라 |

### 4.3 캘리브레이션 데이터 유효성 검증

| 검증 항목 | 조건 | 실패 시 동작 |
|-----------|------|--------------|
| 프레임 수 | ≥ 100 | "조명/카메라 확인" 안내 후 재측정 |
| 얼굴 검출률 | ≥ 90% | 동일 |
| 지표 안정성 | CV < 0.1 | "측정 중 움직임 줄여주세요" |
| 어깨 검출률 | (정보 기록만, 70% 미만이면 보조 지표 비활성화) | - |

### 4.4 임계값 자동 도출 공식 (방법 2 + 방법 3 결합)

```python
# 방법 2: 표준편차 기반 (사용자 흔들림 범위 초과 판정)
# 방법 3: 최소 변화량 보장 (안전장치)

threshold = max(
    neutral_mean + 3 * neutral_std,      # 흔들림 범위 3σ
    neutral_mean * 1.05                  # 최소 5% 변화 보장
)

# Δ% 형태로 변환 후 사용
threshold_delta_pct = (threshold - neutral_mean) / neutral_mean * 100
```

**적용 지표별:**
- `cheek_distance` → forward / recline / forward_full 공통 임계값
- `eye_distance` → forward 보조 검증
- `shoulder_width` → forward_full 검증 (어깨 가용 시)
- `eye_line_tilt` → head_tilt 임계값 (기본 ±5°, 최소 baseline std × 3)

---

## 5. 데이터 파일 구조

### 5.1 baseline_v2.json

```json
{
  "version": "v2.0",
  "timestamp": "2026-05-25T20:30:00Z",
  "collection_duration_seconds": 10.0,
  "frame_count": 150,
  "shoulder_detection_rate": 0.95,
  "calibration_quality": "good",

  "neutral": {
    "cheek_distance":      { "mean": 0.1923, "std": 0.0008 },
    "eye_distance":        { "mean": 0.1221, "std": 0.0004 },
    "cheek_eye_ratio":     { "mean": 1.5764, "std": 0.0022 },
    "face_center_y":       { "mean": 0.5858, "std": 0.0004 },
    "eye_line_tilt":       { "mean": -1.92,  "std": 0.46 },
    "eye_symmetry_ratio":  { "mean": 0.1005, "std": 0.0038 },
    "cheek_symmetry_ratio":{ "mean": 0.0769, "std": 0.0023 },
    "shoulder_width":      { "mean": 0.3809, "std": 0.0006, "available": true },
    "shoulder_tilt_deg":   { "mean": -2.99,  "std": 0.51,  "available": true }
  },

  "auto_thresholds": {
    "forward_cheek_delta_pct": 5.0,
    "recline_cheek_delta_pct": 8.0,
    "forward_shoulder_delta_pct": 5.0,
    "head_tilt_deg_abs": 5.0,
    "chin_rest_score_threshold": 0.5
  }
}
```

### 5.2 실시간 이벤트 출력 (state machine 호환)

```json
{
  "timestamp": "2026-05-25T20:31:15Z",
  "frame_state": "BAD_POSTURE",
  "detected_posture": "forward_head_only",
  "display_label": "거북목 경향",
  "confidence": 0.87,
  "deviation_score": 0.62,
  "duration_in_state_s": 12.5,
  "deltas": {
    "cheek_distance_pct": 8.4,
    "face_center_y_pct": 3.2,
    "eye_line_tilt_delta": -1.8
  }
}
```

### 5.3 기존 baseline.json 호환성
- 기존 V1 `baseline.json`은 그대로 보존
- V2는 별도 파일 `baseline_v2.json` 사용
- V2 첫 실행 시 baseline_v2.json 없으면 캘리브레이션 화면 진입

---

## 6. 시스템 통합

### 6.1 상태 머신 호환

기존 시스템 상태 머신 (NORMAL → WARNING → BAD_POSTURE) 그대로 유지:

| confidence | 상태 |
|-----------|------|
| `< 0.45` | NORMAL |
| `0.45 ~ 0.60` | WARNING |
| `≥ 0.60` | BAD_POSTURE |

상태 전환 시간 (기존과 동일):
- `min_duration_sec`: 1.5
- `min_state_hold_sec`: 1.8

### 6.2 자세별 지속 시간 (sustain_seconds)

기존 시스템 기준 그대로 유지:

| 자세 | sustain_seconds |
|------|----------------|
| `forward_head_only` | 1.5 |
| `forward_head_full` | 1.5 |
| `recline` | 1.5 |
| `head_tilt` | 1.5 |
| `chin_rest` | 2.0 |

→ 임계값 넘은 상태가 위 시간만큼 지속돼야 "확정 자세"로 판정.

### 6.3 민감도(Sensitivity) 설정 연동

사용자가 UI에서 조정 가능한 민감도가 confidence 임계값을 조정:

| 민감도 | confidence 최저 표시 임계 |
|--------|--------------------------|
| 예민 (high) | 0.30 |
| 보통 (medium) | 0.50 |
| 둔감 (low) | 0.70 |

→ 민감도 "예민"이면 작은 변화도 알림. "둔감"이면 큰 변화만 알림.

### 6.4 MediaPipe 설정 (기존 유지)

```json
{
  "face": { "min_detection_confidence": 0.5, "min_presence_confidence": 0.5, "min_tracking_confidence": 0.5 },
  "pose": { "min_detection_confidence": 0.5, "min_presence_confidence": 0.5, "min_tracking_confidence": 0.5 },
  "hand": { "min_detection_confidence": 0.5, "min_presence_confidence": 0.5, "min_tracking_confidence": 0.5 }
}
```

### 6.5 필터 설정 (기존 유지)

```json
{
  "one_euro": { "min_cutoff": 0.05, "beta": 0.005 },
  "ema": { "alpha": 0.15 },
  "indicator_ema": { "alpha": 0.15 }
}
```

→ 랜드마크 및 지표 스무딩 그대로 유지.

---

## 7. 실험 데이터 기반 검증 (2026-05-25 기준)

### 7.1 3 사용자 측정 결과 (107deg 기준)

| 사용자 | forward_head_only Δ% | recline Δ% |
|--------|---------------------|-----------|
| U1 | +6.5% | +15.8% |
| U2 | +133.5% | +42.2% |
| U3 | +4.9% | +4.2% |

### 7.2 V1 → V2 개선 매핑

| 발견된 문제 | V1 대응 | V2 대응 |
|------------|---------|---------|
| 사용자별 cheek_distance 절대값 차이 (±29%) | 고정 비율 사용, 일반화 실패 | Δ% 기반 → 개인차 무관 |
| 사용자별 자세 수행 방식 차이 (Δ% 4~135%) | 단일 임계값으로 일반화 불가 | 표준편차 기반 자동 임계값 |
| vh_ratio 부호 반대 발생 | - | vh_ratio 완전 제거 |
| U3: 자세 간 변화량 너무 작음 (~5%) | 감지 불가 | "최소 5% 변화 보장" 안전장치 + 캘리브 검증 단계 경고 |
| 노트북 어깨 검출 불안정 | 어깨 의존 시 실패 | 어깨 검출률 70% 미만 시 자동 비활성화 |

---

## 8. 구현 우선순위 (일요일까지)

### 🔴 Must Have (필수)
- [ ] `src/core/calibration_v2.py` — 1단계 캘리브레이션 수집 모듈
- [ ] `baseline_v2.json` 저장/로드/검증
- [ ] 자동 임계값 도출 로직 (`mean + 3*std` + 최소 5%)
- [ ] `classify_posture()` 함수 (5개 자세 모두 + Guards)
- [ ] 자세 충돌 시 deviation_score 최대값 선택
- [ ] 상태 머신 출력 (NORMAL/WARNING/BAD_POSTURE)
- [ ] 어깨 검출률 모니터링 (70% 미만 시 보조 지표 비활성화)
- [ ] confidence 계산 + 민감도 설정 연동

### 🟡 Should Have (가능하면)
- [ ] 캘리브레이션 UI 화면 (UX 팀과 협업)
- [ ] 실시간 이벤트 JSON 포맷 출력
- [ ] head_tilt, forward_head_full 정밀 튜닝

### 🟢 Nice to Have (시간 남으면)
- [ ] chin_rest 가중치 미세 조정
- [ ] 캘리브레이션 품질 점수 표시
- [ ] 디버그 모드 (각 자세 candidate score 시각화)

---

## 9. V1 vs V2 비교 테스트 계획

### 9.1 테스트 시나리오
- 5명 이상 참가자
- 각 참가자 × 5 자세 (neutral / forward_head_only / forward_head_full / recline / head_tilt)
- 각 자세 30초 측정

### 9.2 평가 지표

| 지표 | V1 (광대/어깨) | V2 (Δ% + std 기반) |
|------|---------------|--------------------|
| 자세별 정확도 | ? | ? |
| 검출 안정성 (CV) | ? | ? |
| 사용자별 일관성 | ? | ? |
| UX 부담 (캘리브 시간) | 13초 | 13초 (동일) |
| 어깨 검출 의존도 | 100% | 조건부 |
| 노트북 극단 각도(<100°, >110°) 작동 | ? | 작동 예상 |

→ **두 버전을 동일 데이터셋으로 테스트 후 최종 채택**

---

## 10. 알려진 한계 및 제외 사항

### 10.1 한계 (발표 시 명시)
1. **캘리브레이션 자세 정확도 의존**: 사용자가 neutral 자세를 부정확하게 잡으면 임계값 도출 오류
2. **자세 수행 방식 일관성**: 캘리브 시점과 실제 사용 시점의 자세가 일치해야 함
3. **U3 케이스 (자세 변화량 < 5%)**: "최소 5% 변화 보장"으로 일부 완화, 그래도 정밀도 제한적
4. **노트북 극단 각도 시 어깨 불가**: forward_head_only/full 구분 어려움 (얼굴 지표만 사용)

### 10.2 V2에서 제외된 자세
- **`yaw_turn` (고개 좌우 회전)** — 자세 불량이 아닌 정상 동작, 감지 대상에서 제외 (오탐 대조군으로만 실험에서 사용)
- **`crossed_leg_estimated` (다리 꼬기)** — 본 프로젝트 범위 제외

### 10.3 향후 과제
- 사용자 5명 이상 데이터로 임계값 보정 계수 튜닝
- ML 기반 분류기로의 확장 (현재 규칙 기반)
- slouching, looking_down 등 추가 자세

---

## 11. 참고 자료

- `scripts/posture_variance_experiment.py` — V2 검증용 측정 스크립트
- `scripts/_three_user_analysis.py` — 3 사용자 데이터 분석
- `debug_logs/posture_experiment/` — 실험 원본 데이터
- `.github/rules/operation/posture_definition_criteria.json` — 기존 V1 정의 (상태 머신, 민감도, 필터 설정 유지 기준)

---

**문의**: UI/기획 담당자
**다음 마일스톤**:
1. 일요일까지 V2 구현 완료
2. V1 (개선 버전) vs V2 비교 테스트
3. 더 정확한 버전 채택 → 발표 PPT 작성
