"""
실제 앱 실행 테스트 - 자세 감지 시 소리 확인

실행 방법:
1. 카메라 앞에 서기
2. 나쁜 자세(거북목, 기댄자세) 만들기
3. 팝업이 나타나고 소리가 재생되는지 확인
"""

import sys
from src.ui.app import baromokApp

if __name__ == "__main__":
    print("=" * 70)
    print("바로목 앱 실행 - 소리 테스트")
    print("=" * 70)
    print("\n[테스트 방법]")
    print("1. 카메라 앞에 서기")
    print("2. 나쁜 자세(거북목, 기댄자세) 만들기")
    print("3. 팝업이 나타나고 '삐' 하는 소리가 나는지 확인")
    print("4. 쿨다운(3초) 이후에 다시 자세가 나빠지면 소리 재생")
    print("5. Ctrl+C로 앱 종료")
    print("=" * 70 + "\n")

    app = baromokApp()
    sys.exit(app.run())
