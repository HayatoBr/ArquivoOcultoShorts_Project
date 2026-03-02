param(
  [string]$BaseUrl = "http://127.0.0.1:7860"
)

$ErrorActionPreference = "Stop"

function Join-Url([string]$b, [string]$p) {
  if($b.EndsWith("/")) { $b = $b.TrimEnd("/") }
  if(-not $p.StartsWith("/")) { $p = "/" + $p }
  return $b + $p
}

function Invoke-Json([string]$method, [string]$path, $body=$null) {
  $url = Join-Url $BaseUrl $path
  $headers = @{ "Content-Type"="application/json" }
  if($null -ne $body) {
    $json = $body | ConvertTo-Json -Depth 10
    return Invoke-RestMethod -Method $method -Uri $url -Headers $headers -Body $json
  } else {
    return Invoke-RestMethod -Method $method -Uri $url -Headers $headers
  }
}

function Normalize-Checkpoint([string]$s) {
  if([string]::IsNullOrWhiteSpace($s)) { return "" }
  # SD.Next/A1111 often returns "name [hash]". Keep only the name part.
  $m = [regex]::Match($s, "^(.*?)\s*\[[0-9a-fA-F]+\]\s*$")
  if($m.Success) { return $m.Groups[1].Value.Trim() }
  return $s.Trim()
}

Write-Host "Testando SD API em $BaseUrl ..." -ForegroundColor Cyan

# 1) options + models
$options = Invoke-Json "GET" "/sdapi/v1/options"
$ck = $options.sd_model_checkpoint
Write-Host "Options OK. sd_model_checkpoint:" $ck

$models = Invoke-Json "GET" "/sdapi/v1/sd-models"
Write-Host "Models count:" $models.Count
if($models.Count -lt 1) { throw "Nenhum modelo encontrado em /sdapi/v1/sd-models. Coloque um .safetensors em models/Stable-diffusion." }

$firstModelTitle = $models[0].title
$firstModelName  = $models[0].model_name
Write-Host "First model:" $firstModelName

# prefer title as checkpoint value (most compatible), fallback to model_name
$targetCheckpoint = $firstModelTitle
if([string]::IsNullOrWhiteSpace($targetCheckpoint)) { $targetCheckpoint = $firstModelName }
if([string]::IsNullOrWhiteSpace($targetCheckpoint)) { throw "Modelo inválido retornado pela API (sem title/model_name)." }

Write-Host "Ajustando sd_model_checkpoint para:" $targetCheckpoint -ForegroundColor Yellow

# 2) set options (best effort)
try {
  Invoke-Json "POST" "/sdapi/v1/options" @{ sd_model_checkpoint = $targetCheckpoint } | Out-Null
} catch {
  Write-Host "AVISO: falhou POST /options (vamos continuar via override_settings)." -ForegroundColor DarkYellow
}

# 3) wait until option reflects (with normalization)
$ok = $false
for($i=0; $i -lt 30; $i++) {
  Start-Sleep -Milliseconds 500
  $cur = (Invoke-Json "GET" "/sdapi/v1/options").sd_model_checkpoint
  $curNorm = Normalize-Checkpoint $cur
  $tNorm   = Normalize-Checkpoint $targetCheckpoint
  Write-Host ("checkpoint atual: {0}" -f $cur)
  if($curNorm -eq $tNorm) { $ok = $true; break }
}

if(-not $ok) {
  Write-Host "AVISO: checkpoint não refletiu via /options. Vamos forçar via override_settings no txt2img." -ForegroundColor DarkYellow
}

# 4) sampler: list and pick a compatible one
$samplers = Invoke-Json "GET" "/sdapi/v1/samplers"
if($samplers.Count -lt 1) { throw "Nenhum sampler retornado por /sdapi/v1/samplers." }

# Preferred sampler candidates (order matters)
$preferred = @(
  "DPM++ 2M Karras",
  "DPM++ 2M SDE Karras",
  "Euler a",
  "Euler",
  "DDIM"
)

$availableNames = @($samplers | ForEach-Object { $_.name })
$samplerName = $null
foreach($p in $preferred) {
  if($availableNames -contains $p) { $samplerName = $p; break }
}
if([string]::IsNullOrWhiteSpace($samplerName)) {
  $samplerName = $availableNames[0]
}
Write-Host "Sampler escolhido:" $samplerName -ForegroundColor Green

# 5) txt2img
Write-Host "Chamando txt2img..." -ForegroundColor Cyan

$payload = @{
  prompt = "cinematic noir interior, abandoned room, dust, film grain, moody lighting, highly detailed"
  negative_prompt = "lowres, worst quality, blurry, watermark, text, jpeg artifacts"
  steps = 18
  cfg_scale = 6.5
  width = 576
  height = 1024
  sampler_name = $samplerName
  batch_size = 1
  n_iter = 1
  seed = -1
  send_images = $true
  save_images = $false
  # Force checkpoint even if /options didn't apply
  override_settings = @{ sd_model_checkpoint = $targetCheckpoint }
  override_settings_restore_afterwards = $true
}

try {
  $resp = Invoke-Json "POST" "/sdapi/v1/txt2img" $payload
} catch {
  Write-Host "ERRO chamando txt2img:" -ForegroundColor Red
  throw
}

if($null -eq $resp.images -or $resp.images.Count -lt 1) {
  Write-Host "Nenhuma imagem retornada. Dump parcial da resposta:" -ForegroundColor Yellow
  $raw = $resp | ConvertTo-Json -Depth 6
  Write-Host ($raw.Substring(0, [Math]::Min($raw.Length, 1200)))
  throw "Nenhuma imagem retornada pela API."
}

# 6) decode and save
$outDir = Join-Path (Get-Location) "output"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outPng = Join-Path $outDir "sdnext_test.png"

# SD API returns base64 PNG; may contain "data:image/png;base64," prefix
$img64 = $resp.images[0]
if($img64.StartsWith("data:image")) {
  $img64 = $img64.Split(",")[1]
}

[IO.File]::WriteAllBytes($outPng, [Convert]::FromBase64String($img64))
Write-Host "OK: imagem salva em $outPng" -ForegroundColor Green
Write-Host "Dica: se continuar falhando, abra o SD.Next UI e veja se o modelo aparece como selecionado." -ForegroundColor DarkGray
