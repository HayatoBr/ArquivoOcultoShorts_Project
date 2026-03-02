param(
  [string]$BaseUrl = "http://127.0.0.1:7860"
)

$ErrorActionPreference = "SilentlyContinue"

function Try-Get($url) {
  try {
    return Invoke-RestMethod -Uri $url -TimeoutSec 5
  } catch {
    return $null
  }
}

$models = Try-Get ($BaseUrl.TrimEnd("/") + "/sdapi/v1/sd-models")
if ($models) {
  Write-Host "OK: servidor respondeu em /sdapi/v1/sd-models" -ForegroundColor Green
  $models | Select-Object -First 5 | ForEach-Object { Write-Host (" - " + $_.title) }
  exit 0
}

$docs = Try-Get ($BaseUrl.TrimEnd("/") + "/docs")
if ($docs) {
  Write-Host "OK: servidor respondeu em /docs (API ativa)" -ForegroundColor Green
  exit 0
}

Write-Host "ERRO: não consegui acessar o servidor SD em $BaseUrl" -ForegroundColor Red
Write-Host "Dica: inicie o SD.Next com: .\webui.bat --api" -ForegroundColor Yellow
