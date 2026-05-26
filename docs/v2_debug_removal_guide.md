# V2 디버그 모듈 제거 가이드

V2 자세 감지 로직의 디버그 관련 파일을 운영 빌드에서 제거하는 절차.

---

## 삭제 대상 파일

| 경로 | 역할 |
|------|------|
| `src/core/v2_debug.py` | V2DebugRecorder 클래스 |
| `scripts/v2_live_debug.py` | 라이브 webcam 디버그 |
| `scripts/v2_replay_debug.py` | 저장 데이터 리플레이 디버그 |
| `scripts/test_v2_with_real_data.py` | 정확도 통합 테스트 |
| `debug_logs/v2_runtime/` | 디버그 출력물 폴더 |

---

## 제거 후에도 동작이 보장되는 이유

V2 핵심 모듈은 디버그 모듈을 import 하지 않는다:

```bash
# 의존성 검증 — 아래 명령은 결과 비어있어야 함 (V2 core 가 v2_debug 를 참조 안 함)
grep -r "v2_debug" src/core/calibration_v2.py src/core/judgment_engine_v2.py
```

`JudgmentEngineV2` 의 `on_frame` 파라미터는 `Optional` 이며 기본값은 `None`.
운영 코드에서 `on_frame=None` 으로 두면 콜백 호출 자체가 발생하지 않는다.

---

## 제거 명령 (PowerShell 한 줄)

```powershell
Remove-Item -Force src/core/v2_debug.py, scripts/v2_live_debug.py, scripts/v2_replay_debug.py, scripts/test_v2_with_real_data.py
Remove-Item -Force -Recurse debug_logs/v2_runtime -ErrorAction SilentlyContinue
```

---

## 제거 후 검증

```powershell
# V2 core 가 import 되는지
py -3 -c "from src.core.calibration_v2 import CalibrationV2Manager; from src.core.judgment_engine_v2 import JudgmentEngineV2; print('V2 core OK')"
```

위 명령이 OK 메시지를 출력하면 정상.

---

## 운영 코드에서 V2 사용 예시 (디버그 없음)

```python
from src.config import ConfigManager
from src.core.calibration_v2 import CalibrationV2Manager
from src.core.judgment_engine_v2 import JudgmentEngineV2

config = ConfigManager()
cal_mgr = CalibrationV2Manager(config)
cal_mgr.load()  # baseline_v2.json 로드

# on_frame=None (기본값) — 콜백 오버헤드 0
engine = JudgmentEngineV2(config, cal_mgr, sensitivity="medium")

result = engine.judge(indicators)
# result.detected_posture, result.confidence, result.frame_state ...
```
