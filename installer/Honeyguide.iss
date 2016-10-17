; -- Example1.iss --
; Demonstrates copying 3 files and creating an icon.

; SEE THE DOCUMENTATION FOR DETAILS ON CREATING .ISS SCRIPT FILES!

[Setup]
AppName=Honeyguide
AppVersion=0.12
DefaultDirName={pf}\Honeyguide
DefaultGroupName=Honeyguide
UninstallDisplayIcon={app}\Honeyguide.exe
Compression=lzma2
SolidCompression=yes
OutputDir=userdocs:Inno Setup Examples Output
DisableWelcomePage=True
AppCopyright=(c) Ben Weiss 2016
LicenseFile=userdocs:cc\Other\Honeyguide\LICENSE.txt

[Files]
Source: "dist/*"; DestDir: "{app}"

[Icons]
Name: "{group}\Honeyguide"; Filename: "{app}\Honeyguide.exe"

[UninstallDelete]
Type: files; Name: "settings.ini"
Type: files; Name: "app.log"
