@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0build.local.cmd" call "%~dp0build.local.cmd"
if exist "%~dp0tools\cargo\bin\cargo.exe" (
  set "RUSTUP_HOME=%~dp0tools\rustup"
  set "CARGO_HOME=%~dp0tools\cargo"
  set "PATH=%~dp0tools\cargo\bin;%PATH%"
)
if not defined DSH_VSDEVCMD (
  for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "DSH_VSDEVCMD=%%i\Common7\Tools\VsDevCmd.bat"
)
if not defined DSH_VSDEVCMD (
  echo Visual Studio C++ Build Tools not found. Set DSH_VSDEVCMD.
  exit /b 1
)
call "%DSH_VSDEVCMD%" -arch=x64 -host_arch=x64
if errorlevel 1 exit /b %errorlevel%
cargo build --release --locked
exit /b %errorlevel%
