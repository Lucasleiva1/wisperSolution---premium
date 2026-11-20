#define MyAppName "Whisper Solution"
#ifndef MyAppVersion
  #define MyAppVersion "1.1.4"
#endif
#define MyAppExeName "Whisper-Solution.exe"

[Setup]
AppId={{7B80876D-0F1A-4378-AC7F-ABEB67CA0FE5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductTextVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppName}
DefaultDirName={localappdata}\Whisper-Solution
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=release_pyinstaller
OutputBaseFilename=Whisper-Solution-Setup-v{#MyAppVersion}
SetupIconFile=assets\icons\whisper-solution.ico
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
; Explicit mandatory entries make Inno fail if either sound is missing.
Source: "dist_pyinstaller\Whisper-Solution\assets\start.mp3"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "dist_pyinstaller\Whisper-Solution\assets\stop.mp3"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "dist_pyinstaller\Whisper-Solution\*"; DestDir: "{app}"; Excludes: "whisper-solution-runtime.log,assets\start.mp3,assets\stop.mp3,nvidia\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "default_config.json"; DestDir: "{app}"; DestName: "config.json"; Flags: onlyifdoesntexist uninsneveruninstall

[Dirs]
Name: "{app}\exports"
Name: "{app}\temp_audio"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icons\whisper-solution-v{#MyAppVersion}.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icons\whisper-solution-v{#MyAppVersion}.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
