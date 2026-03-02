@echo off
setlocal
cd /d "%~dp0"
set PS=powershell.exe
%PS% -NoProfile -ExecutionPolicy Bypass -File ".\tools\run_short.ps1" 
exit /b %ERRORLEVEL%
