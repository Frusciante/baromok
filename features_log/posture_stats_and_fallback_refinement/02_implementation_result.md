# 통계 유지율 정규화, 어깨 미감지 폴백 모델 전환 및 기댄 자세 방어 로직 개선 결과서

## 1. 구현 요약
1. 통계 화면에서 바른 자세 유지율이 100%를 초과(219%)하던 버그의 근본 원인(분자·분모 시간 기준 불일치, 재측정 진입 시 세션 미종료, `warmup` 프레임 유입)을 모두 수정하고 기존 `data/sessions.db`의 세션 데이터를 재계산하여 정상화하였다.
2. 기준 자세 수집 시 어깨가 미감지되거나 프레임이 부족해도 실패 처리하지 않고 어깨 미사용 모델(`Eye-Height`, 홍채 화면 거리)만으로 동작하도록 개선하였다.
3. 어깨 기울기 단독으로는 거북목이나 기댄 자세가 일률적으로 바른 자세로 가드되지 않도록 수정하고, **얼굴 주변에 손이 감지된 상태(`hand_near_face` 또는 `chin_occlusion > 0.25`)에서만 어깨 기울기를 확인**하여 턱 괸 자세 판정 및 기댄 자세 오판 방어에 사용하도록 수정하였다.

## 2. 수정 파일 목록
- `src/core/session_manager.py`: `warmup`/`baseline` 프레임 제외, 세션 총 시간(`dur`) 기준 상태별 시간 정규화, `end_session` 시간 동기화
- `src/ui/screens/statistics_screen.py`: `DateAggregator`에서 상태별 시간 합 기준 집계 및 `0~100%` 클램핑
- `src/ui/screens/detection_screen.py`: 비감지(`warmup`) 프레임 무시 및 어깨 모델 비활성 시 UI 표시 보완
- `src/ui/app.py`: 기준 자세 설정 화면 진입 시 진행 중인 감지 세션 정상 종료 처리
- `src/core/baseline_manager.py`: 어깨 지표 및 `Shoulder-Cheek` 모델 필수 조건 완화, 모델 초기화 보완
- `src/core/judge_workers.py`:
  - `ForwardHeadWorker`, `ReclineWorker`에 어깨 모델 적합 여부 확인 후 미적합/미감지 시 비어깨 모델 사용
  - `ForwardHeadWorker._is_guarded`, `ReclineWorker._is_guarded`에서 단독 어깨 기울기 가드 제거
  - `ReclineWorker.handle_indicators`에서 얼굴 주변에 손이 감지(`hand_near_face` 또는 `chin_occlusion > 0.25`)된 경우에만 어깨 선 기울기(`max_shoulder_tilt`)를 확인하여 기댄 자세 판정 억제
  - `ChinRestWorker.handle_indicators`에서 얼굴 주변에 손이 감지된 경우 어깨 기울기 점수(`sh_score`)를 분자에 반영
- `src/core/judgment_engine.py`: `chin_rest_estimated` 활성/확정 시 `recline` 상호 배제 추가
- `data/posture_definition_criteria.json`: `posture_types.recline.guards.max_shoulder_tilt` 기준 반영 (`6.0`)
- `.github/rules/operation/posture_system_summary.md`, `.github/rules/posture_definition.md`: 변경된 알고리즘 및 방어 규칙 문서 동기화

## 3. 검증 결과
- **통계 유지율 검증**: `data/sessions.db` 내 108개 종료 세션 재계산 완료. 기존 `219.1%`로 표시되던 `10/26` 세션이 `55.9%`(`121.24초 / 217초`)로 정상화되었으며 모든 세션이 `0~100%` 범위 내에서 일치함을 확인.
- **어깨 미감지 폴백 검증**: `shoulder_width=None`인 35프레임 기준 자세 수집 시 `finish_baseline_collection() == True`, `is_baseline_valid() == True` 통과 및 `Eye-Height`·홍채 거리 모델 기반 정상 판정 확인.
- **턱 괸 자세(얼굴 주변 손 감지 + 어깨 기울기) 방어 검증**:
  - 손 미근접 + 어깨 기울어짐(`7.5°` >= `6.0°`) + 기댄 자세: 어깨 기울기로 인해 바른 자세로 무시되지 않고 `Recline` 정상 감지 확인
  - 손 근접(`hand_near_face=True`) + 어깨 기울어짐(`7.5°` >= `6.0°`): `Recline` `0.0` 억제 및 `chin_rest_estimated` 우세 판정 확인
