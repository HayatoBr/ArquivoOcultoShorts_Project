param(
  [string]$InstallDir = "C:\AI\sdnext"
)

$ErrorActionPreference = "Stop"

function Ensure-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Comando não encontrado: $name. Instale e tente novamente."
  }
}

Ensure-Command git
Ensure-Command py

# Verifica Python 3.10
try {
  $pyv = & py -3.10 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
} catch {
  throw "Python 3.10 não encontrado via 'py -3.10'. Instale Python 3.10.x e habilite o launcher 'py'."
}

Write-Host "OK: Python 3.10 encontrado: $pyv" -ForegroundColor Green

$parent = Split-Path -Parent $InstallDir
if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }

if (Test-Path $InstallDir) {
  Write-Host "Pasta já existe: $InstallDir" -ForegroundColor Yellow
} else {
  Write-Host "Clonando SD.Next em: $InstallDir" -ForegroundColor Cyan
  git clone https://github.com/vladmandic/sdnext $InstallDir
}

Write-Host ""
Write-Host "Instalado. Para iniciar com API:" -ForegroundColor Green
Write-Host "  cd `"$InstallDir`"" -ForegroundColor Gray
Write-Host "  .\webui.bat --api" -ForegroundColor Gray
