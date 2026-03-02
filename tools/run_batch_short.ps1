# ArquivoOcultoShorts - run_batch_short.ps1
param(
  [int]$Count = 5,
  [int]$SleepSeconds = 10,
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

try { chcp 65001 > $null } catch {}

function Get-PythonCmd {
    if (Test-Path ".\.venv\Scripts\python.exe") { return (Resolve-Path ".\.venv\Scripts\python.exe").Path }
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    if (Get-Command py -ErrorAction SilentlyContinue) { return "py" }
    throw "Python não encontrado."
}

$PY = Get-PythonCmd
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$logDir = ".\output\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("run_batch_short_" + $ts + ".log")

Write-Host "Batch SHORT: $Count runs" -ForegroundColor Cyan
for ($i=1; $i -le $Count; $i++) {
  Write-Host "== RUN $i / $Count ==" -ForegroundColor Green
  if ($DryRun) {
    & $PY -c "print('dry-run ok')" 2>&1 | Tee-Object -FilePath $logFile -Append
  } else {
    & $PY .\main.py 2>&1 | Tee-Object -FilePath $logFile -Append
  }
  if ($i -lt $Count) {
    Start-Sleep -Seconds $SleepSeconds
  }
}
Write-Host "Concluído. Log:" $logFile -ForegroundColor DarkGray
