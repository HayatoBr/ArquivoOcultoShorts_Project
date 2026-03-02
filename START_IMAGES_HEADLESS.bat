@echo off
setlocal EnableExtensions
REM Auto-activate venv if present
IF EXIST "%~dp0.venv\Scripts\activate.bat" (CALL "%~dp0.venv\Scripts\activate.bat")
IF EXIST "%~dp0venv\Scripts\activate.bat" (CALL "%~dp0venv\Scripts\activate.bat")
chcp 65001 >nul

REM ArquivoOcultoShorts - gerar imagens headless (Diffusers)
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "tools\run_sd_headless.ps1" -Count 4 -Width 576 -Height 1024 -Steps 22 -CfgScale 6.5 -AttentionSlicing -VaeSlicing
echo.
echo Concluído. Pressione qualquer tecla para fechar...
pause >nul
