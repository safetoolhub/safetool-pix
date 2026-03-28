; Inno Setup script for SafeTool Pix
; Generates a single-file installer: SafeToolPix-{version}-windows-setup.exe
;
; Build with:
;   iscc build\installer.iss
;
; Environment variables used (set by build.py / GitHub Actions):
;   APP_VERSION       - e.g. "0.8.6"
;   APP_FULL_VERSION  - e.g. "0.8.6-alpha"

#ifndef APP_VERSION
  #define APP_VERSION GetEnv("APP_VERSION")
#endif
#ifndef APP_FULL_VERSION
  #define APP_FULL_VERSION GetEnv("APP_FULL_VERSION")
#endif
; Fallback to APP_VERSION when FULL_VERSION is not set
#if APP_FULL_VERSION == ""
  #define APP_FULL_VERSION APP_VERSION
#endif

#define AppName    "SafeTool Pix"
#define AppPublisher "SafeToolHub"
#define AppURL     "https://safetoolhub.org"
#define AppExeName "SafeToolPix.exe"

; Paths relative to this script (which lives in build/)
#define RootDir    ".."
#define SourceDir  "..\dist\SafeToolPix"
#define OutputDir  "..\dist"
#define OutputFile "SafeToolPix-" + APP_FULL_VERSION + "-windows-setup"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#APP_VERSION}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile={#RootDir}\LICENSE
OutputDir={#OutputDir}
OutputBaseFilename={#OutputFile}
SetupIconFile={#RootDir}\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#AppExeName}
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Bundle all PyInstaller output (exe + _internal/ with libs and data)
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";         Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";   Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName,'&','&&')}}"; Flags: nowait postinstall skipifsilent
