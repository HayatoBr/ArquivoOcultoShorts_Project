param(
  [string]$SdNextDir = "C:\AI\sdnext",
  [string]$Args = "--api"
)

$ErrorActionPreference = "Stop"

$dir = Resolve-Path $SdNextDir
$bat = Join-Path $dir "webui.bat"

if (-not (Test-Path $bat)) {
  throw "Não encontrei webui.bat em: $bat. Confira o caminho -SdNextDir."
}

Push-Location $dir
try {
  Write-Host "Iniciando SD.Next em $dir com args: $Args" -ForegroundColor Cyan
  & $bat $Args
} finally {
  Pop-Location
}
