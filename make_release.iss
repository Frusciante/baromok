[Setup]

#define MyAppName "Baromok"

; (기존 Setup 섹션 내용들...)
AppName={#MyAppName}
AppVersion=1.0.2
DefaultDirName={autopf}\{#MyAppName}

OutputDir="C:\Users\hsbin\OneDrive\문서"

; 2. 빌드되어 나올 최종 설치 파일의 이름을 지정 (확장자 .exe는 자동으로 붙습니다)
OutputBaseFilename=Baromok_Setup_v1.0

[Files]
; 1. [추가] main.dist 하위의 모든 파일 및 폴더를 사용자의 설치 경로({app})에 그대로 배포
Source: "D:\2026-1\CD\baromok\dist\main.dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

; 2. [확인] 파이썬 설치 파일 (이전 코드에서 ExtractTemporaryFile로 쓰이기 때문에 dontcopy 플래그가 필요합니다)
; 실제 파이썬 인스톨러 파일이 있는 정확한 로컬 경로로 수정해서 사용하세요.
Source: "D:\2026-1\CD\baromok\python-3.14.3-amd64.exe"; DestDir: "{tmp}"; Flags: dontcopy

[Registry]
; 설치된 main.exe 파일이 실행될 때 윈도우가 항상 관리자 권한(RUNASADMIN)을 요구하도록 설정합니다.
Root: HKCU; Subkey: "Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"; ValueType: string; ValueName: "{app}\baromok.exe"; ValueData: "~ RUNASADMIN"; Flags: uninsdeletevalue

[Icons]
; 설치 완료 후 바탕화면에 바로가기(ShortCut)를 생성합니다
Name: "{autodesktop}\Baromok"; Filename: "{app}\baromok.exe"

[Tasks]
; 바로가기 생성 여부를 묻는 체크박스(Task)를 정의합니다. (기본적으로 체크된 상태: checked)
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"