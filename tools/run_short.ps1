param(
  [switch]$DryRun,
  [switch]$TestMode,
  [switch]$Debug
)

# --- UTF-8 / robust streaming for Windows consoles ---
try { chcp 65001 | Out-Null } catch {}
try {
  $utf8NoBom = New-Object System.Text.UTF8Encoding $false
  [Console]::OutputEncoding = $utf8NoBom
  $OutputEncoding = $utf8NoBom
} catch {}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
# PowerShell 5.1 compatibility: avoid ternary operator ?:
$ErrorActionPreference = "Stop"

function NowTs { (Get-Date).ToString("yyyy-MM-dd HH:mm:ss") }
function Step($msg) { Write-Host ("[{0}] >>> {1}" -f (NowTs), $msg) }
function Ok($msg)   { Write-Host ("[{0}] OK  {1}" -f (NowTs), $msg) }
function Warn($msg) { Write-Host ("[{0}] !!  {1}" -f (NowTs), $msg) }

$root = Split-Path $PSScriptRoot -Parent
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPy) { $PY = $venvPy } else { $PY = "python" }

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

function Invoke-PythonAndLog([string]$code, [string]$label) {
  $sw = [System.Diagnostics.Stopwatch]::StartNew()

  # PowerShell 5.1: native stderr becomes a non-terminating error record.
  # Temporarily relax ErrorActionPreference so we can capture full traceback text.
  $oldEAP = $ErrorActionPreference
  $ErrorActionPreference = "Continue"

  # Capture ALL output (stdout+stderr)
  $lines = & $PY -u -c $code 2>&1
  $exitCode = $LASTEXITCODE

  $ErrorActionPreference = $oldEAP
  $sw.Stop()

  # Write full output to log
  if ($lines -ne $null) {
    $lines | Out-File -FilePath $logFile -Encoding UTF8 -Append
  }

  # Also print to console with light prefixing
  foreach ($line in $lines) {
    if ($null -eq $line) { continue }
    if ($line -match "^(OK:|AVISO:|== |\[)") {
      Write-Host ("[{0}] {1}" -f (NowTs), $line)
    } else {
      Write-Host ("[{0}] ... {1}" -f (NowTs), $line)
    }
  }

  if ($exitCode -ne 0) {
    Warn "$label falhou (exit code $exitCode). Veja o log: $logFile"
    exit $exitCode
  }

  Ok ("$label finalizado em {0:n1}s" -f ($sw.Elapsed.TotalSeconds))
}

# Healthcheck only
if ($DryRun) {
  Step "DRY-RUN: healthcheck"
  $hc = "import json,yaml; from core.utils.healthcheck import run_healthcheck; cfg=yaml.safe_load(open(r'config/config.yml','r',encoding='utf-8')); print(json.dumps(run_healthcheck(cfg), ensure_ascii=False, indent=2))"
  Invoke-PythonAndLog $hc "Dry-run"
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

$pyCode = "from core.pipeline import run; run(test_mode=$modeArg)"
Invoke-PythonAndLog $pyCode "Pipeline"

Ok "Log: $logFile"
