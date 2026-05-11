#!/usr/bin/env python3
"""폰트 명 변경: Noto Sans CJK KR -> Noto Sans KR"""

import os

files_to_process = [
    "src/ui/screens/__init__.py",
    "src/ui/main_window.py",
    "src/ui/widgets/settings_widgets.py",
    "src/ui/styles/theme.py",
]

for file_path in files_to_process:
    full_path = os.path.join("c:\\Users\\이우성\\OneDrive\\Desktop\\baromok_ws", file_path)
    
    if not os.path.exists(full_path):
        print(f"❌ 파일 없음: {file_path}")
        continue
    
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 변경
    new_content = content.replace('Noto Sans CJK KR', 'Noto Sans KR')
    
    if new_content != content:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        count = content.count('Noto Sans CJK KR')
        print(f"✅ {file_path}: {count}개 변경됨")
    else:
        print(f"⏭️  {file_path}: 변경 사항 없음")

print("\n✨ 완료!")
