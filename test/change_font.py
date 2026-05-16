import os

files_to_update = [
    "src/ui/main_window.py",
    "src/ui/styles/theme.py",
    "src/ui/screens/__init__.py",
    "src/ui/widgets/settings_widgets.py",
    "src/ui/screens.py.bak",
]

for file_path in files_to_update:
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        updated_content = content.replace("Segoe UI", "Noto Sans CJK KR")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

        print(f"✓ {file_path}: 변경 완료")
    else:
        print(f"✗ {file_path}: 파일 없음")

print("\n모든 파일의 폰트 변경이 완료되었습니다.")
