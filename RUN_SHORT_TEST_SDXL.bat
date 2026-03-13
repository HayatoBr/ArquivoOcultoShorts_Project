@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist "%ROOT%\.venv\Scripts\activate.bat" call "%ROOT%\.venv\Scripts\activate.bat"

echo [ArquivoOculto][SDXL][TEST] Python da venv:
"%ROOT%\.venv\Scripts\python.exe" -c "import torch,sys; print(sys.executable); print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.device_count()); print(0 if torch.cuda.is_available() else -1)"

echo [ArquivoOculto][SDXL][TEST] Iniciando pipeline...

"%ROOT%\.venv\Scripts\python.exe" "%ROOT%\main.py" --config "%ROOT%\config.sdxl.yml" --test

echo [ArquivoOculto][SDXL][TEST] Encerrado com codigo %ERRORLEVEL%.
pause