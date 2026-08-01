#define MyAppName "Whisper Solution"
#define MyAppVersion "1.1.2-pre.1"
#define MyAppExeName "Whisper-Solution.exe"

[Setup]
AppId={{7B80876D-0F1A-4378-AC7F-ABEB67CA0FE5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppName}
DefaultDirName={localappdata}\Whisper-Solution
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=release_pyinstaller
OutputBaseFilename=Whisper-Solution-Setup
SetupIconFile=assets\icons\whisper-solution.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "dist_pyinstaller\Whisper-Solution\*"; DestDir: "{app}"; Excludes: "whisper-solution-runtime.log,nvidia\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "default_config.json"; DestDir: "{app}"; DestName: "config.json"; Flags: onlyifdoesntexist uninsneveruninstall

[Dirs]
Name: "{app}\exports"
Name: "{app}\temp_audio"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
