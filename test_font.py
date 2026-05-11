#!/usr/bin/env python3
"""시스템 폰트 확인"""

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication
import sys

# QApplication 필수
app = QApplication(sys.argv)

# 설치된 폰트 확인
families = QFontDatabase.families()

print("시스템에 설치된 한글 폰트:")
for font in families:
    if 'noto' in font.lower() or 'sans' in font.lower() or '고딕' in font or 'arial' in font.lower():
        print(f"  - {font}")

# Noto Sans CJK KR 테스트
font = QFont("Noto Sans CJK KR")
print(f"\nNoto Sans CJK KR 로드: {font.family()}")

# Malgun Gothic 테스트  
font2 = QFont("Malgun Gothic")
print(f"Malgun Gothic 로드: {font2.family()}")

# Segoe UI 테스트
font3 = QFont("Segoe UI")
print(f"Segoe UI 로드: {font3.family()}")
