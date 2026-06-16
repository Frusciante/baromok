"""
Nuitka를 사용한 빌드 스크립트 (일반화 버전)
배포 방식(standalone/onefile)을 선택할 수 있습니다.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# === 프로젝트별 설정 ===
PROJECT_NAME = "Baromok"
COMPANY_NAME = "6thSense" 
VERSION = "1.0.0"
DESCRIPTION = "웹캠 자세 교정 프로그램"
ENTRY_POINT = "main.py"
# gui 파일이 따로 있다면 그 파일을 빌드해야 한다.
# 예를 들어, 커맨드 형식으로 실행하는 main.py가 존재한다면, 
# gui를 구현하는 파일 예를 들어 gui.py 등을 ENTRY_POINT로 설정하는게 좋다.
OUTPUT_NAME = "baromok.exe"
ICON_FILE = "assets/ui/바로목로고.png"  # 없으면 "" 형태로, 따옴표 안의 내용을 비워둔다.

# 포함할 모듈들
INCLUDE_MODULES = [
    "mediapipe", "numpy", "matplotlib", "PyQt6", "cv2", "PyQt6.sip", "pydantic", "pydantic_settings", "pandas", "sklearn", "dotenv"
    # 프로젝트별로 추가/수정
]

# 포함할 데이터 디렉토리들  
INCLUDE_DATA_DIRS = [
    "data=data", "assets=assets",
    # 프로젝트별로 추가/수정 (없으면 빈 리스트)
    #=의 경우, pyproject.toml에서 특정 디렉토리를 변수로 지정할 수 있음을 이용한 문법이다. 
]

# Nuitka 플러그인들
ENABLE_PLUGINS = [
    "pyqt6"
    # 필요한 플러그인 추가/수정
    # numpy는 플러그인이 지원중단 되었으므로 제외하는 것을 권장한다.
]

def choose_build_mode():
    """빌드 방식에 대한 선택"""
    global BUILD_MODE
    
    print("\n=== 배포 방식 선택 ===")
    print("1. standalone - 폴더 형태")
    print("2. onefile    - 단일 파일")
    
    while True:
        choice = input("\n어떤 방식으로 빌드하시겠습니까? ").strip()
        
        if choice == "1":
            BUILD_MODE = "standalone"
            print("특정 폴더에 빌드합니다.")
            break
        elif choice == "2":
            BUILD_MODE = "onefile"
            print("단일 파일로 빌드합니다.")
            break
        else:
            print("1 또는 2를 입력하십시오.")

def clean_build_folders():
    """이전 빌드 폴더 정리"""
    folders_to_clean = [
        'dist', 'build', 
        f'{OUTPUT_NAME.lower()}.build', 
        f'{OUTPUT_NAME.lower()}.dist', 
        f'{OUTPUT_NAME.lower()}.onefile-build'
    ]
    
    for folder in folders_to_clean:
        if os.path.exists(folder):
            print(f"이전 빌드 폴더 삭제 중: {folder}")
            shutil.rmtree(folder)

def build_project():
    """Nuitka로 프로젝트 빌드"""
    
    # 기본 Nuitka 명령어
    nuitka_cmd_args = [
        sys.executable, "-m", "nuitka",
        "--windows-console-mode=disable",  # Windows에서 콘솔 창 숨기기
        f"--company-name={COMPANY_NAME}",
        f"--product-name={PROJECT_NAME}",
        f"--file-version={VERSION}",
        f"--product-version={VERSION}",
        f"--file-description={DESCRIPTION}",
        f"--output-filename={OUTPUT_NAME}",
        "--assume-yes-for-downloads",  # 필요한 파일 자동 다운로드
        "--show-progress",  # 진행 상황 표시
        "--show-memory",   # 메모리 사용량 표시
        "--output-dir=dist",  # 출력 디렉토리
    ]
    
    # 배포 방식에 따른 옵션 추가
    if BUILD_MODE == "standalone":
        nuitka_cmd_args.append("--standalone")
    elif BUILD_MODE == "onefile":
        nuitka_cmd_args.append("--onefile")
    
    # 아이콘 추가 (있는 경우)
    if ICON_FILE and os.path.exists(ICON_FILE):
        nuitka_cmd_args.append(f"--windows-icon-from-ico={ICON_FILE}")
        print(f"아이콘 설정: {ICON_FILE}")
    
    # 플러그인 추가
    for plugin in ENABLE_PLUGINS:
        nuitka_cmd_args.append(f"--enable-plugin={plugin}")
    
    # 모듈 추가
    for module in INCLUDE_MODULES:
        nuitka_cmd_args.append(f"--include-module={module}")
    
    # 데이터 디렉토리 추가
    for data_dir in INCLUDE_DATA_DIRS:
        if "=" in data_dir:  # 유효한 형식인지 확인
            nuitka_cmd_args.append(f"--include-data-dir={data_dir}")
    
    # 엔트리 포인트 추가
    nuitka_cmd_args.append(ENTRY_POINT)
    
    print(f"\n{BUILD_MODE} 모드로 빌드를 시작합니다.")
    print("시간이 좀 걸릴 수 있습니다...")
    
    try:
        result = subprocess.run(nuitka_cmd_args, check=True)
        print("\n빌드가 성공적으로 완료되었습니다!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n빌드 중 오류가 발생했습니다: {e}")
        return False

def create_distribution():
    """배포용 폴더 생성"""
    dist_folder = f"{PROJECT_NAME}_Distribution"
    
    if os.path.exists(dist_folder):
        shutil.rmtree(dist_folder)
    
    os.makedirs(dist_folder)
    
    # 빌드 결과물 복사
    success = False
    
    if BUILD_MODE == "standalone":
        # standalone 모드: 전체 폴더 복사
        standalone_folder = os.path.join("dist", f"{OUTPUT_NAME}.dist")
        if os.path.exists(standalone_folder):
            shutil.copytree(standalone_folder, os.path.join(dist_folder, "app"))
            print(f"standalone 폴더를 {dist_folder}/app로 복사했습니다.")
            success = True
    
    elif BUILD_MODE == "onefile":
        # onefile 모드: 실행 파일만 복사
        exe_file = f"{OUTPUT_NAME}.exe"
        if os.path.exists(exe_file):
            shutil.copy(exe_file, dist_folder)
            print(f"{exe_file}를 배포 폴더로 복사했습니다.")
            success = True
    
    if not success:
        print("빌드 결과물을 찾을 수 없습니다.")
        return False
    
    print(f"\n배포 폴더가 생성되었습니다: {dist_folder}")
    return True

def main():
    """메인 빌드 프로세스"""
    print(f"=== {PROJECT_NAME} Nuitka 빌드 스크립트 ===\n")
    
    # 엔트리 포인트 파일 확인
    if not os.path.exists(ENTRY_POINT):
        print(f"엔트리 포인트 파일을 찾을 수 없습니다: {ENTRY_POINT}")
        print("build_config.py의 ENTRY_POINT를 확인하세요.")
        sys.exit(1)
    
    
    # 빌드 모드 선택
    choose_build_mode()
    
    # 이전 빌드 정리
    clean_build_folders()
    
    # 빌드 실행
    if build_project():
        # 배포 폴더 생성
        if create_distribution():
            print(f"\n빌드가 완료되었습니다.")
            print(f"{PROJECT_NAME}_Distribution 폴더에서 결과물을 확인하세요.")
            
            if BUILD_MODE == "standalone":
                print("폴더 형태로 빌드되었습니다. 이제 인스톨러를 제작하여 배포하십시오.")
            else:
                print("단일 파일로 빌드되었습니다. exe 파일만 배포하면 됩니다.")
        else:
            print("\n배포 폴더 생성에 실패했습니다.")
            sys.exit(1)
    else:
        print("\n빌드에 실패했습니다.")
        sys.exit(1)

if __name__ == "__main__":
    main()
