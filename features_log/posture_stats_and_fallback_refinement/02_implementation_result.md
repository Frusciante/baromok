# 통계 유지율 정규화, 어깨 미감지 폴백, 기댄 자세 방어 및 화면 얼굴 가까움 분리 결과서

## 1. 구현 요약
1. 통계 화면에서 바른 자세 유지율이 100%를 초과(219%)하던 버그의 근본 원인(분자·분모 시간 기준 불일치, 재측정 진입 시 세션 미종료, `warmup` 프레임 유입)을 모두 수정하고 기존 `data/sessions.db`의 세션 데이터를 재계산하여 정상화하였다.
2. 기준 자세 수집 시 어깨가 미감지되거나 프레임이 부족해도 실패 처리하지 않고 어깨 미사용 모델(`Eye-Height`, 홍채 화면 거리)만으로 동작하도록 개선하였다.
3. 어깨 기울기 단독으로는 거북목이나 기댄 자세가 일률적으로 바른 자세로 가드되지 않도록 수정하고, **얼굴 주변에 손이 감지된 상태(`hand_near_face` 또는 `chin_occlusion > 0.25`)에서만 어깨 기울기를 확인**하여 턱 괸 자세 판정 및 기댄 자세 오판 방어에 사용하도록 수정하였다.
4. 홍채 기반 눈-화면 거리 측정 알고리즘을 거북목(`forward_head`)에서 **화면 얼굴 가까움(`eye_close`)** 전용 판정 워커(`EyeCloseWorker`)로 분리하고, 알림 메시지를 `"얼굴과 화면 사이 거리가 가깝습니다. 뒤로 물러나시거나 노트북 거리를 조정해주세요."`로 반영하였다.

## 2. 수정 파일 목록
- `src/core/session_manager.py`: `warmup`/`baseline` 프레임 제외, 세션 총 시간(`dur`) 기준 상태별 시간 정규화, `end_session` 시간 동기화
- `src/ui/screens/statistics_screen.py`: `DateAggregator`에서 상태별 시간 합 기준 집계 및 `0~100%` 클램핑
- `src/ui/screens/detection_screen.py`: 비감지(`warmup`) 프레임 무시 및 어깨 모델 비활성 시 UI 표시 보완
- `src/ui/app.py`: 기준 자세 설정 화면 진입 시 진행 중인 감지 세션 정상 종료 처리
- `src/core/baseline_manager.py`: 어깨 지표 및 `Shoulder-Cheek` 모델 필수 조건 완화, 모델 초기화 보완
- `src/core/judge_workers.py`:
  - `ForwardHeadWorker`: 어깨-광대 비율 편차(`Shoulder-Cheek` 모델) 전용으로 분리
  - `EyeCloseWorker`: 홍채 기반 눈-화면 거리(`eye_screen_distance_cm`, `eye_close_warning`)를 사용하는 `화면 얼굴 가까움`(`eye_close`) 전용 워커 신설 및 `PostureJudgeManager` 등록
  - `ForwardHeadWorker._is_guarded`, `ReclineWorker._is_guarded`: 단독 어깨 기울기 가드 제거
  - `ReclineWorker.handle_indicators`: 얼굴 주변에 손이 감지(`hand_near_face` 또는 `chin_occlusion > 0.25`)된 경우에만 어깨 선 기울기(`max_shoulder_tilt`)를 확인하여 기댄 자세 판정 억제
  - `ChinRestWorker.handle_indicators`: 얼굴 주변에 손이 감지된 경우 어깨 기울기 점수(`sh_score`)를 분자에 반영
- `src/core/judgment_engine.py`, `src/core/state_machine.py`: `eye_close` 및 `chin_rest_estimated` 활성/확정 시 `recline` 상호 배제 추가
- `src/ui/widgets/settings_widgets.py`, `src/ui/widgets/chart_widgets.py`: 거리 설정 슬라이더 라벨(`화면 얼굴 가까움 거리`) 및 통계 차트 항목(`화면 얼굴 가까움`) 반영
- `data/posture_definition_criteria.json`: `posture_types.eye_close` 표시 라벨(`"화면 얼굴 가까움"`) 및 알림 문구(`"얼굴과 화면 사이 거리가 가깝습니다. 뒤로 물러나시거나 노트북 거리를 조정해주세요."`) 반영
- `.github/rules/operation/posture_system_summary.md`, `.github/rules/posture_definition.md`: 변경된 알고리즘 및 방어 규칙 문서 동기화

## 3. 검증 결과
- **화면 얼굴 가까움(`eye_close`) 분리 및 메시지 검증**:
  - 화면 거리가 임계값(`45.0cm`) 이하일 때 `ForwardHeadWorker`가 아닌 `EyeCloseWorker`(`eye_close`)가 트리거되며, 표시 이름 `"화면 얼굴 가까움"` 및 알림 메시지 `"얼굴과 화면 사이 거리가 가깝습니다. 뒤로 물러나시거나 노트북 거리를 조정해주세요."`가 정상 반환됨을 확인.
- **턱 괸 자세(얼굴 주변 손 감지 + 어깨 기울기) 방어 검증**:
  - 손 미근접 + 어깨 기울어짐(`7.5°` >= `6.0°`) + 기댄 자세: 어깨 기울기로 인해 바른 자세로 무시되지 않고 `Recline` 정상 감지 확인
  - 손 근접(`hand_near_face=True`) + 어깨 기울어짐(`7.5°` >= `6.0°`): `Recline` `0.0` 억제 및 `chin_rest_estimated` 우세 판정 확인
