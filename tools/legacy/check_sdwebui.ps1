# Verifica se o SD WebUI (AUTOMATIC1111) está rodando
$ErrorActionPreference = 'SilentlyContinue'
$url = 'http://127.0.0.1:7860/sdapi/v1/sd-models'
try {
  $r = Invoke-RestMethod -Uri $url -TimeoutSec 5
  Write-Host 'OK: SD WebUI respondeu. Modelos disponíveis:' -ForegroundColor Green
  $r | Select-Object -First 5 | ForEach-Object { Write-Host (' - ' + $_.title) }
} catch {
  Write-Host 'ERRO: não consegui acessar o SD WebUI em http://127.0.0.1:7860' -ForegroundColor Red
  Write-Host 'Dica: abra o AUTOMATIC1111 WebUI com --api e tente novamente.' -ForegroundColor Yellow
}
