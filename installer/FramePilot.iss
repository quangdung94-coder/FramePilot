; Inno Setup 6 Script - Bộ cài đặt Windows FramePilot (chạy song song bản Python trong DaVinci)
; Cách build sau khi chạy build_exe.py:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\FramePilot.iss

#define MyAppName "FramePilot"
#define MyAppVersion "0.4.0 (22h01)"
#define MyAppExeName "FramePilot.exe"

[Setup]
AppId={{8D4F6C21-9E3A-4B52-A1C7-F0123456789A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\dist
OutputBaseFilename=FramePilot_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo shortcut ngoài Desktop"; GroupDescription: "Tiện ích:"; Flags: unchecked

[Files]
Source: "..\dist\FramePilot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
