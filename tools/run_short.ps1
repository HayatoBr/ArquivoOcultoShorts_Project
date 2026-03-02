param(
  [switch]$DryRun,
  [switch]$TestMode
)

$root = Split-Path $PSScriptRoot -Parent
$venvPy = Join-Path $root ".venv\Scripts\python.exe"

if (Test-Path $venvPy) {
  $PY = $venvPy
} else {
  $PY = "python"
}

Write-Host "Usando Python: $PY"

$logDir = Join-Path $root "output\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "run_short_$ts.log"

if ($DryRun) {
  Write-Host "DRY-RUN: executando apenas healthcheck (via python)..."
  & $PY -c "import json,yaml; from core.utils.healthcheck import run_healthcheck; cfg=yaml.safe_load(open(r'config/config.yml','r',encoding='utf-8')); print(json.dumps(run_healthcheck(cfg), ensure_ascii=False, indent=2))" 2>&1 | Tee-Object -FilePath $logFile
  Write-Host "Log: $logFile"
  exit 0
}

if ($TestMode) {
  Write-Host "Executando em TEST MODE (Wiki+DDG+Ollama; sem OpenAI)..."
  & $PY -c "from core.pipeline import run; run(test_mode=True)" 2>&1 | Tee-Object -FilePath $logFile
} else {
  Write-Host "Executando em PRODUÇÃO (OpenAI gpt-4o-mini + Ollama fallback)..."
  & $PY -c "from core.pipeline import run; run(test_mode=False)" 2>&1 | Tee-Object -FilePath $logFile
}

Write-Host "Log: $logFile"
