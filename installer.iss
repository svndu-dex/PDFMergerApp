; Inno Setup script for PDF Toolkit
; Run build.bat first so that dist\PDF Toolkit exists, then compile this file in Inno Setup.

#define AppName "PDF Toolkit"
#define AppVersion "1.0"
#define AppExe "PDF Toolkit.exe"

[Setup]
AppId={{B7E3C1A2-5D4F-4C8E-9A61-2F7D0E8B3C54}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
OutputBaseFilename=PDF-Toolkit-Setup
OutputDir=installer_output
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Uncomment if you have an app.ico next to this file:
; SetupIconFile=app.ico

[Files]
Source: "dist\PDF Toolkit\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
