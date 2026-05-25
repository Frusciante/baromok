#!/usr/bin/env python3
"""
바로목 자세 측정 가이드 스크립트
처음 측정하는 사용자용 — 안내 → 실험 실행 → zip 패키징까지 자동 처리
"""

import subprocess
import sys
import zipfile
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────────────────
BANNER = """
╔══════════════════════════════════════════════════════╗
║          바로목 자세 데이터 측정 가이드               ║
╚══════════════════════════════════════════════════════╝
"""

SETUP_CHECKLIST = """
[측정 전 체크리스트]

  1. 노트북 화면 각도를 고정하세요
     → 평소 사용하는 각도 그대로 유지 (바꾸지 마세요)
     → 각도계 앱으로 측정하거나 대략 몇 도인지 기억해두세요

  2. 카메라가 얼굴 전체를 비추는지 확인하세요
     → 이마 꼭대기 ~ 어깨가 모두 보여야 합니다
     → 너무 가깝거나 너무 멀지 않게 (얼굴이 화면의 약 1/3 차지)

  3. 조명이 고른지 확인하세요
     → 역광(창문이 뒤에 있는 경우) 피해주세요

  4. 측정 중에는 말하거나 크게 움직이지 마세요

  5. 각 자세는 15초씩, 총 3가지 자세를 측정합니다:
       - neutral          : 평소 바른 자세
       - forward_head_only: 목만 앞으로 내미는 자세
       - recline          : 등받이에 기대는 자세
"""

POSTURE_GUIDE = {
    "neutral": """
  [자세 1/3] neutral — 평소 바른 자세
  ────────────────────────────────────
  ✔ 등을 등받이에 붙이고 척추를 곧게 세웁니다
  ✔ 양 어깨는 수평, 턱은 살짝 당겨 화면 정면을 봅니다
  ✔ 이 자세가 기준(baseline)이 되므로 가장 자연스러운 상태로 앉으세요
""",
    "forward_head_only": """
  [자세 2/3] forward_head_only — 목만 앞으로
  ────────────────────────────────────────────
  ✔ 엉덩이와 등은 등받이에 그대로 붙여둡니다 (몸은 움직이지 않음)
  ✔ 목만 앞으로 쭉 빼서 머리를 화면 쪽으로 내밉니다
  ✔ 시선은 화면 정면을 유지합니다 (아래를 보지 않음)
  ✗ 상체까지 앞으로 기울이지 마세요
""",
    "recline": """
  [자세 3/3] recline — 등받이에 기댄 자세
  ─────────────────────────────────────────
  ✔ 의자에 깊숙이 기대어 상체와 머리를 살짝 뒤로 젖힙니다
  ✔ 자연스럽게 화면 위쪽을 바라보는 각도가 됩니다
  ✔ 과도하게 뒤로 눕지 않아도 됩니다 (살짝 기대는 정도)
""",
}


def ask_screen_angle() -> str:
    print("\n[화면 각도 입력]")
    print("  노트북 화면 각도를 입력하세요 (모르면 그냥 Enter → '107deg' 로 기록됩니다)")
    print("  예시: 103, 107, 112, 95 등 숫자만 입력해도 됩니다")
    val = input("  각도: ").strip()
    if not val:
        angle_tag = "107deg"
    else:
        # 숫자만 입력한 경우 'deg' 붙이기
        digits = val.replace("deg", "").replace("°", "").strip()
        angle_tag = f"{digits}deg"
    print(f"  → '{angle_tag}' 로 기록됩니다\n")
    return angle_tag


def run_experiment(angle_tag: str) -> Path:
    """posture_variance_experiment.py 실행 후 생성된 출력 디렉토리 반환"""
    script = PROJECT_ROOT / "scripts" / "posture_variance_experiment.py"
    cmd = [
        sys.executable, str(script),
        "--postures", "neutral", "forward_head_only", "recline",
        "--duration", "15",
        "--screen-angle", angle_tag,
    ]

    print("\n[자세 미리보기]")
    for posture in ["neutral", "forward_head_only", "recline"]:
        print(POSTURE_GUIDE[posture])

    print("=" * 56)
    print("  실험을 시작합니다. 각 자세마다 안내가 다시 표시됩니다.")
    print("=" * 56)
    input("\n  준비되면 Enter를 눌러 실험을 시작하세요...")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print("\n[오류] 실험 스크립트 실행 중 오류가 발생했습니다.")
        sys.exit(1)

    # 가장 최근에 생성된 실험 디렉토리 찾기
    exp_base = PROJECT_ROOT / "debug_logs" / "posture_experiment"
    dirs = sorted(
        [d for d in exp_base.iterdir() if d.is_dir() and angle_tag in d.name],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not dirs:
        print("[오류] 출력 디렉토리를 찾을 수 없습니다.")
        sys.exit(1)
    return dirs[0]


def package_zip(out_dir: Path) -> Path:
    """출력 디렉토리를 zip으로 패키징"""
    zip_path = PROJECT_ROOT / f"{out_dir.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in out_dir.iterdir():
            zf.write(f, f.name)
    return zip_path


def main():
    print(BANNER)
    print(SETUP_CHECKLIST)
    input("  체크리스트 확인 후 Enter를 눌러 시작하세요...")

    angle_tag = ask_screen_angle()
    out_dir = run_experiment(angle_tag)

    print("\n[패키징 중...]")
    zip_path = package_zip(out_dir)

    print(f"""
{'=' * 56}
  측정 완료!

  결과 파일: {zip_path.name}
  위치: {zip_path}

  이 zip 파일을 팀원에게 전달해주세요.
{'=' * 56}
""")


if __name__ == "__main__":
    main()
