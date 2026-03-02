@echo off
setlocal EnableExtensions
REM Auto-activate venv if present
IF EXIST "%~dp0.venv\Scripts\activate.bat" (CALL "%~dp0.venv\Scripts\activate.bat")
IF EXIST "%~dp0venv\Scripts\activate.bat" (CALL "%~dp0venv\Scripts\activate.bat")
chcp 65001 >nul

REM ArquivoOcultoShorts - iniciar automação SHORT
REM Executa o pipeline via PowerShell com ExecutionPolicy Bypass (sem precisar assinar scripts)

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "tools\run_short.ps1"
echo.
echo Concluído. Pressione qualquer tecla para fechar...
pause >nul
