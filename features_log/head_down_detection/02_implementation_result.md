# 고개 숙임(Head Down) 감지 기능 구현 결과

## 1. 구현 내용 (Implementation Summary)
베이스라인 대비 얼굴의 상하 기울기(Pitch) 변화를 감지하여 '고개 숙임' 자세를 판정하는 기능을 성공적으로 구현하였습니다.

### 주요 변경 사항
- **랜드마크 추출 (`src/core/landmark_extractor.py`)**:
  - 이마(Forehead, 10번) 랜드마크 추출 추가.
  - 턱(Chin) 및 이마 포인트의 3D Z좌표(깊이)를 정규화 과정에서 보존하도록 수정.
- **지표 계산 (`src/core/indicator_calculator.py`)**:
  - `face_pitch_deg` 지표 추가: 이마와 턱의 YZ 평면 상의 각도를 `arctan2(delta_z, delta_y)`로 계산.
  - EMA 필터를 적용하여 수치 안정화.
- **베이스라인 관리 (`src/core/baseline_manager.py`)**:
  - 베이스라인 수집 시 `face_pitch_deg`의 중앙값을 계산하여 저장.
- **판정 엔진 및 워커 (`src/core/judgment_engine.py`, `src/core/judge_workers.py`)**:
  - `PostureType.HEAD_DOWN` 정의 추가.
  - `HeadDownWorker` 구현: 베이스라인 각도 대비 현재 각도 차이가 임계값(기본 15도)을 초과하면 감지.
  - 멀티스레드 판정 매니저에 등록.
- **설정 파일 (`data/posture_definition_criteria.json`)**:
  - `head_down` 자세의 감도(0.1), 임계값(15도), 경고 메시지 등 설정 추가.

## 2. 테스트 결과 (Test Results)
- **단위 테스트**: 수학적 계산 로직 검증 결과, 정면(0도), 고개 숙임(양수), 고개 들기(음수)가 올바르게 계산됨을 확인.
- **설정 로드**: 앱 구동 시 `head_down` 설정이 정상적으로 로드되고 워커가 기동됨을 로그를 통해 확인 가능.

## 3. 향후 과제
- 실제 사용 환경에서 조명이나 카메라 각도에 따른 Z축 좌표의 민감도를 모니터링하여 임계값(15도) 및 마진(5도)을 미세 조정할 필요가 있음.
