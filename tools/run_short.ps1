param(
  [switch]$DryRun,
  [switch]$TestMode,
  [switch]$Debug
)

$ErrorActionPreference = "Stop"

function NowTs { (Get-Date).ToString("yyyy-MM-dd HH:mm:ss") }
function Step($msg) { Write-Host ("[{0}] >>> {1}" -f (NowTs), $msg) }
function Ok($msg)   { Write-Host ("[{0}] OK  {1}" -f (NowTs), $msg) }
function Warn($msg) { Write-Host ("[{0}] !!  {1}" -f (NowTs), $msg) }

$root = Split-Path $PSScriptRoot -Parent
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
$PY = (Test-Path $venvPy) ? $venvPy : "python"

Step "Raiz do projeto: $root"
Step "Python selecionado: $PY"

# Debug flags for Python side
if ($Debug) {
  $env:AO_DEBUG="1"
  Ok "AO_DEBUG=1"
}

# Log setup
$logDir = Join-Path $root "output\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir ("run_short_{0}.log" -f $ts)

Step "Log em: $logFile"

# Basic env info
try {
  $pyVer = & $PY -c "import sys; print(sys.version.split()[0])" 2>$null
  Ok "Python version: $pyVer"
} catch {
  Warn "Não foi possível obter versão do Python: $($_.Exception.Message)"
}

# Healthcheck only
if ($DryRun) {
  Step "DRY-RUN: healthcheck"
  & $PY -c "import json,yaml; from core.utils.healthcheck import run_healthcheck; cfg=yaml.safe_load(open(r'config/config.yml','r',encoding='utf-8')); print(json.dumps(run_healthcheck(cfg), ensure_ascii=False, indent=2))" 2>&1 | Tee-Object -FilePath $logFile
  Ok "Dry-run finalizado"
  Ok "Log: $logFile"
  exit 0
}

# Execute pipeline with mode flag
if ($TestMode) {
  Step "Executando TEST MODE (Wiki+DDG+Ollama; sem OpenAI)"
  $modeArg = "True"
} else {
  Step "Executando PRODUÇÃO (OpenAI + fallback Ollama)"
  $modeArg = "False"
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()

# Stream Python output while also writing to log.
# Prefix lines in console for readability.
& $PY -u -c "from core.pipeline import run; run(test_mode=$modeArg)" 2>&1 |
  Tee-Object -FilePath $logFile |
  ForEach-Object {
    $line = $_
    if ($line -match "^(OK:|AVISO:|== |\\[)") {
      Write-Host ("[{0}] {1}" -f (NowTs), $line)
    } else {
      Write-Host ("[{0}] ... {1}" -f (NowTs), $line)
    }
  }

$sw.Stop()
Ok ("Execução finalizada em {0:n1}s" -f ($sw.Elapsed.TotalSeconds))
Ok "Log: $logFile"
