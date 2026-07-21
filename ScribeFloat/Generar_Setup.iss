[Setup]
AppId={{D9AC4422-56E4-4C28-87E6-C6B4F5A1A937}
AppName=ScribeFloat Premium
AppVersion=1.1.0
AppVerName=ScribeFloat Premium 1.1.0
AppPublisher=ScribeFloat
DefaultDirName={localappdata}\ScribeFloat-Premium
DefaultGroupName=ScribeFloat Premium
OutputDir=release
OutputBaseFilename=ScribeFloat-Premium-Setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayName=ScribeFloat Premium
UninstallDisplayIcon={app}\ScribeFloat-Premium.exe
AllowNoIcons=yes
CloseApplications=yes
RestartApplications=no
WizardStyle=modern
SetupLogging=yes

[Files]
Source: "build_release\main.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "default_config.json"; DestDir: "{app}"; DestName: "config.json"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\ScribeFloat Premium"; Filename: "{app}\ScribeFloat-Premium.exe"
Name: "{group}\Desinstalar ScribeFloat Premium"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ScribeFloat Premium"; Filename: "{app}\ScribeFloat-Premium.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"

[Run]
Filename: "{app}\ScribeFloat-Premium.exe"; Description: "Iniciar ScribeFloat Premium"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\temp_audio"
