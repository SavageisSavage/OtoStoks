; Inno Setup Script for OtoStoksBot Pro
#define MyAppName "OtoStoksBot Pro v5.0"
#define MyAppVersion "5.0.0"
#define MyAppPublisher "OtoStoksBot Team"
#define MyAppURL "https://github.com/OtoStoksBot"
#define MyAppExeName "OtoStoksBot.exe"

[Setup]
AppId={{5D9F8A1E-47C2-4C18-918B-71E3A3B432C1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\OtoStoksBot
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=C:\Users\HP\Downloads
OutputBaseFilename=OtoStoksBot-Setup
SetupIconFile=C:\Users\HP\.gemini\antigravity\scratch\OtoStoksBot\icon.ico
WizardSmallImageFile=C:\Users\HP\.gemini\antigravity\scratch\OtoStoksBot\assets\wizard_small.bmp
WizardImageFile=C:\Users\HP\.gemini\antigravity\scratch\OtoStoksBot\assets\wizard_large.bmp
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "C:\Users\HP\.gemini\antigravity\scratch\OtoStoksBot\dist\OtoStoksBot-WINDOWS.exe"; DestDir: "{app}"; DestName: "OtoStoksBot.exe"; Flags: ignoreversion
Source: "C:\Users\HP\.gemini\antigravity\scratch\OtoStoksBot\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\HP\.gemini\antigravity\scratch\OtoStoksBot\icon.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\HP\.gemini\antigravity\scratch\OtoStoksBot\OtoStoksBridge.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\HP\.gemini\antigravity\scratch\OtoStoksBot\ScreenStocksLocalBridge.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\HP\.gemini\antigravity\scratch\OtoStoksBot\model.onnx"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\HP\.gemini\antigravity\scratch\OtoStoksBot\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
