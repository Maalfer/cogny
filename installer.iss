[Setup]
AppName=Cogny
AppVersion=1.0.5
DefaultDirName={autopf}\Cogny
DefaultGroupName=Cogny
OutputDir=release
OutputBaseFilename=Cogny_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The main executable
Source: "dist\main\main.exe"; DestDir: "{app}"; Flags: ignoreversion
; All other files (recursive)
Source: "dist\main\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Cogny"; Filename: "{app}\main.exe"
Name: "{autodesktop}\Cogny"; Filename: "{app}\main.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\main.exe"; Description: "{cm:LaunchProgram,Cogny}"; Flags: nowait postinstall skipifsilent
