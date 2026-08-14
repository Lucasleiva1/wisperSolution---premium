[Setup]
AppId={{D9AC4422-56E4-4C28-87E6-C6B4F5A1A937}
AppName=Whisper Solution
AppVersion=1.1.3
AppVerName=Whisper Solution 1.1.3
AppPublisher=Whisper Solution
DefaultDirName={localappdata}\Whisper-Solution
DefaultGroupName=Whisper Solution
OutputDir=release
OutputBaseFilename=Whisper-Solution-Setup
SetupIconFile=assets\icons\whisper-solution.ico
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayName=Whisper Solution
UninstallDisplayIcon={app}\Whisper-Solution.exe
AllowNoIcons=yes
CloseApplications=yes
RestartApplications=no
WizardStyle=modern
SetupLogging=yes

[Files]
Source: "build_release\main.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "default_config.json"; DestDir: "{app}"; DestName: "config.json"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\Whisper Solution"; Filename: "{app}\Whisper-Solution.exe"
Name: "{group}\Desinstalar Whisper Solution"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Whisper Solution"; Filename: "{app}\Whisper-Solution.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"

[Run]
Filename: "{app}\Whisper-Solution.exe"; Description: "Iniciar Whisper Solution"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\temp_audio"
