; Flama Audio - Inno Setup Installer Script
; Compiles Flama.Audio.App into a clean Windows Setup Wizard (FlamaAudio-Setup.exe)

#define MyAppName "Flama Audio"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Flama Team"
#define MyAppURL "https://github.com/TrinhChung/Flama"
#define MyAppExeName "Flama.Audio.App.exe"

[Setup]
AppId={{D3E8C1F4-8A52-474B-96B1-3E2A01234567}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={userlocalappdata}\Programs\Flama Audio
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\publish\installer
OutputBaseFilename=FlamaAudio-Setup
SetupIconFile=..\src\Flama.Audio.App\Assets\app.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\publish\singlefile\Flama.Audio.App.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
