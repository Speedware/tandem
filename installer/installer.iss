#define AppName "Tandem"
#ifndef StageDir
  #define StageDir "..\build\stage"
#endif
#ifndef IconFile
  #define IconFile "..\src\assets\tandem.ico"
#endif
#ifndef OutDir
  #define OutDir "..\dist"
#endif
#ifndef AppVersion
  #define AppVersion "2.0.0"
#endif
#define AppId "Tandem.App"
#define PyW "{app}\python\pythonw.exe"
#define MainPy "{app}\app\main.py"
#define AppIcon "{app}\app\assets\tandem.ico"
#define LegacyDir "{localappdata}\Programs\Winmirror"

[Setup]
AppId={{8F6C2B1E-4A7D-4E3B-9C1A-2D5E7F9A1B3C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
VersionInfoDescription={#AppName} — установка
DefaultDirName={localappdata}\Programs\{#AppName}
UsePreviousAppDir=no
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir={#OutDir}
OutputBaseFilename=Tandem-Setup
SetupIconFile={#IconFile}
UninstallDisplayIcon={#AppIcon}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{#LegacyDir}"
Type: files; Name: "{autoprograms}\Winmirror.lnk"
Type: files; Name: "{autodesktop}\Winmirror.lnk"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{#PyW}"; Parameters: """{#MainPy}"""; WorkingDir: "{app}\app"; IconFilename: "{#AppIcon}"; AppUserModelID: "{#AppId}"
Name: "{autodesktop}\{#AppName}"; Filename: "{#PyW}"; Parameters: """{#MainPy}"""; WorkingDir: "{app}\app"; IconFilename: "{#AppIcon}"; AppUserModelID: "{#AppId}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Tandem"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{#PyW}"; Parameters: """{#MainPy}"""; WorkingDir: "{app}\app"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{#PyW}"; Parameters: """{#MainPy}"" --quit"; Flags: runhidden waituntilterminated; RunOnceId: "StopApp"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure StopCopy(const Dir: String);
var
  ResultCode: Integer;
begin
  if FileExists(Dir + '\python\pythonw.exe') then
    Exec(Dir + '\python\pythonw.exe', '"' + Dir + '\app\main.py" --quit', '',
         SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopCopy(ExpandConstant('{app}'));
  StopCopy(ExpandConstant('{#LegacyDir}'));
  Result := '';
end;
