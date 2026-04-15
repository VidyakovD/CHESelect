#define MyAppName      "SelectVPN"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "SelectVPN"
#define MyAppExe       "SelectVPN.exe"
#define DistDir        "dist2\SelectVPN"

[Setup]
AppId={{8F3A2B1C-4D5E-6F7A-8B9C-0D1E2F3A4B5C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=SelectVPN-Setup
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExe}
CloseApplications=yes
RestartApplications=no
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon";    Description: "Создать значок на рабочем столе"; GroupDescription: "Дополнительно:"; Flags: unchecked
Name: "startupicon";   Description: "Запускать при старте Windows";     GroupDescription: "Дополнительно:"; Flags: unchecked

[Files]
; All app files from PyInstaller output
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExe}"
Name: "{group}\Удалить {#MyAppName}";   Filename: "{uninstallexe}"
; Desktop (optional)
Name: "{autodesktop}\{#MyAppName}";     Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; Autostart (optional task)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#MyAppName}"; \
  ValueData: """{app}\{#MyAppExe}"""; \
  Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExe}"; \
  Description: "Запустить {#MyAppName}"; \
  Flags: nowait postinstall skipifsilent runascurrentuser

[UninstallRun]
Filename: "taskkill"; Parameters: "/F /IM {#MyAppExe}"; Flags: runhidden; RunOnceId: "KillApp"
