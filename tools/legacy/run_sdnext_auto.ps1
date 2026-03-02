param(
  [Parameter(Mandatory=$false)][string]$SdNextDir = "C:\AI\sdnext",
  [Parameter(Mandatory=$false)][string]$BaseUrl  = "http://127.0.0.1:7860",
  [Parameter(Mandatory=$false)][string]$ProjectDir = "",
  [Parameter(Mandatory=$false)][string]$ScriptPath = "assets\text\script.txt",
  [Parameter(Mandatory=$false)][string]$OutputDir = "output",
  [Parameter(Mandatory=$false)][int]$TimeoutSec = 900,
  [switch]$CloseWhenDone
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$m){ Write-Host $m }
function Write-Warn([string]$m){ Write-Host "AVISO: $m" -ForegroundColor Yellow }
function Write-Err([string]$m){ Write-Host "ERRO: $m" -ForegroundColor Red }

function Test-Url([string]$u){
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $u -Method GET -TimeoutSec 5
    return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
  } catch { return $false }
}

function Api-Call([string]$method, [string]$path, $body=$null){
  $uri = $BaseUrl.TrimEnd("/") + $path
  $headers = @{ "Content-Type"="application/json" }
  if ($body -ne $null) {
    $json = ($body | ConvertTo-Json -Depth 12 -Compress)
    return Invoke-RestMethod -Method $method -Uri $uri -Headers $headers -Body $json -TimeoutSec 120
  } else {
    return Invoke-RestMethod -Method $method -Uri $uri -Headers $headers -TimeoutSec 120
  }
}

function Ensure-Absolute([string]$root, [string]$p){
  if ([string]::IsNullOrWhiteSpace($p)) { return $p }
  if ([System.IO.Path]::IsPathRooted($p)) { return $p }
  return (Join-Path $root $p)
}

Write-Info "=== SD.Next Auto Runner ==="

if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
  $ProjectDir = (Get-Location).Path
}
$ProjectDir = (Resolve-Path $ProjectDir).Path

$SdNextDir = (Resolve-Path $SdNextDir).Path
$ScriptAbs = Ensure-Absolute $ProjectDir $ScriptPath
$OutputAbs = Ensure-Absolute $ProjectDir $OutputDir
New-Item -ItemType Directory -Force -Path $OutputAbs | Out-Null

Write-Info ("Projeto: " + $ProjectDir)
Write-Info ("SD.Next:  " + $SdNextDir)
Write-Info ("API:      " + $BaseUrl)
Write-Info ("Roteiro:  " + $ScriptPath)
Write-Info ""

$venvPy = Join-Path $SdNextDir "venv\Scripts\python.exe"
$webuiPy = Join-Path $SdNextDir "webui.py"
$launchPy = Join-Path $SdNextDir "launch.py"

if (!(Test-Path $venvPy)) {
  Write-Err "Não encontrei o python do venv: $venvPy"
  Write-Err "Dica: rode 1x o SD.Next manualmente para ele criar o venv."
  exit 1
}

if (!(Test-Path $webuiPy)) {
  Write-Err "Não encontrei webui.py em: $webuiPy"
  exit 1
}

# Detect if already online
$alreadyOnline = Test-Url ($BaseUrl.TrimEnd("/") + "/docs")
$startedHere = $false
$proc = $null

if ($alreadyOnline) {
  Write-Info "API já está online. Vou reutilizar a instância atual."
} else {
  Write-Info "Iniciando SD.Next com --api..."
  $stdoutLog = Join-Path $SdNextDir "sdnext_auto_stdout.log"
  $stderrLog = Join-Path $SdNextDir "sdnext_auto_stderr.log"
  try { Remove-Item $stdoutLog,$stderrLog -ErrorAction SilentlyContinue } catch {}

  # Start SD.Next directly via venv python (evita bugs do webui.bat/webui.ps1)
  $args = @($webuiPy, "--api")
  $proc = Start-Process -FilePath $venvPy -ArgumentList $args -WorkingDirectory $SdNextDir -PassThru -WindowStyle Minimized -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
  $startedHere = $true
  Write-Info ("Processo SD.Next iniciado. PID=" + $proc.Id)
}

Write-Info "Aguardando API do SD.Next ficar online..."
$deadline = (Get-Date).AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline) {
  if (Test-Url ($BaseUrl.TrimEnd("/") + "/docs")) { break }
  Start-Sleep -Seconds 2
}

if (!(Test-Url ($BaseUrl.TrimEnd("/") + "/docs"))) {
  Write-Err "Timeout esperando API ficar online."
  if ($startedHere -and $proc -ne $null) {
    try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
  }
  $logPath = Join-Path $SdNextDir "sdnext.log"
  if (Test-Path $logPath) {
    Write-Host "`n---- Últimas linhas de sdnext.log ----"
    Get-Content $logPath -Tail 80
  } else {
    Write-Warn "Não achei sdnext.log em $SdNextDir"
  }
  exit 2
}

Write-Info "API online. Checando modelo..."
# Wait model ready: options has sd_model_checkpoint and /sd-models returns >=1
$ready = $false
$deadline2 = (Get-Date).AddSeconds([Math]::Max(60, [int]($TimeoutSec/2)))
while ((Get-Date) -lt $deadline2) {
  try {
    $opt = Api-Call "GET" "/sdapi/v1/options"
    $models = Api-Call "GET" "/sdapi/v1/sd-models"
    if ($models -and $models.Count -ge 1 -and $opt.sd_model_checkpoint) { $ready = $true; break }
  } catch { }
  Start-Sleep -Seconds 2
}
if (-not $ready) {
  Write-Warn "Modelo ainda não parece pronto. Vou tentar mesmo assim, mas pode falhar nas primeiras cenas."
}

# Determine sampler
$samplerName = "Euler a"
try {
  $samplers = Api-Call "GET" "/sdapi/v1/samplers"
  $names = @()
  foreach($s in $samplers){ if ($s.name) { $names += $s.name } }
  if ($names -contains "Euler a") { $samplerName = "Euler a" }
  elseif ($names -contains "Euler") { $samplerName = "Euler" }
  elseif ($names.Count -ge 1) { $samplerName = $names[0] }
} catch { }
Write-Info ("Sampler escolhido: " + $samplerName)

# Load scenes
$scenesPath = Join-Path $OutputAbs "scenes.json"
$scenes = @()

if (Test-Path $scenesPath) {
  try {
    $scenes = Get-Content $scenesPath -Raw | ConvertFrom-Json
  } catch {
    Write-Warn "Falhei lendo scenes.json; vou gerar cenas simples."
    $scenes = @()
  }
}

if (-not $scenes -or $scenes.Count -lt 1) {
  # Fallback: 4 cenas genéricas
  $basePrompt = ""
  if (Test-Path $ScriptAbs) {
    $basePrompt = (Get-Content $ScriptAbs -Raw)
    if ($basePrompt.Length -gt 600) { $basePrompt = $basePrompt.Substring(0,600) }
  }
  $scenes = @(
    @{ idx = 1; prompt = "foto realista, investigacao, misterio, noite, cinematic lighting. " + $basePrompt },
    @{ idx = 2; prompt = "foto realista, arquivo antigo, recortes de jornal, mesa de investigacao, cinematic. " + $basePrompt },
    @{ idx = 3; prompt = "foto realista, rua vazia, chuva, luzes neon, suspense, cinematic. " + $basePrompt },
    @{ idx = 4; prompt = "foto realista, silhueta, neblina, atmosfera sombria, cinematic. " + $basePrompt }
  )
}

Write-Info ("Cenas: " + $scenes.Count)
$imagesDir = Ensure-Absolute $ProjectDir "assets\images"
New-Item -ItemType Directory -Force -Path $imagesDir | Out-Null

$report = @{
  base_url = $BaseUrl
  sdnext_dir = $SdNextDir
  images_dir = $imagesDir
  started_here = $startedHere
  started_pid = ($proc.Id  | ForEach-Object { $_ })  # can be null
  sampler = $samplerName
  scenes = @()
}

$generated = 0
foreach($s in $scenes) {
  $idx = $s.idx
  if (-not $idx) { $idx = ($generated + 1) }

  $prompt = $s.prompt
  if (-not $prompt) { $prompt = "" }

  $outFile = Join-Path $imagesDir ("scene{0}.png" -f $idx)

  $payload = @{
    prompt = $prompt
    negative_prompt = "text, watermark, logo, lowres, blurry, bad anatomy, disfigured, extra fingers"
    steps = 18
    sampler_name = $samplerName
    width = 576
    height = 1024
    cfg_scale = 6.5
    batch_size = 1
    n_iter = 1
    seed = -1
    restore_faces = $false
    enable_hr = $false
    override_settings = @{
      sd_model_checkpoint = $null
    }
  }

  # try to force current checkpoint if options provides it
  try {
    $opt = Api-Call "GET" "/sdapi/v1/options"
    if ($opt.sd_model_checkpoint) {
      $payload.override_settings.sd_model_checkpoint = $opt.sd_model_checkpoint
    }
  } catch { }

  $sceneRec = @{
    idx = $idx
    prompt = $prompt
    out = $outFile
    ok = $false
    error = $null
  }

  try {
    $resp = Api-Call "POST" "/sdapi/v1/txt2img" $payload
    if ($resp -and $resp.images -and $resp.images.Count -ge 1) {
      $b64 = $resp.images[0]
      # sometimes returns "data:image/png;base64,...."
      if ($b64 -match "base64,") { $b64 = $b64.Split("base64,")[1] }
      [IO.File]::WriteAllBytes($outFile, [Convert]::FromBase64String($b64))
      $generated++
      $sceneRec.ok = $true
    } else {
      $sceneRec.error = "Sem imagem retornada (images vazio)."
      Write-Warn ("Cena {0}: nenhuma imagem retornada." -f $idx)
    }
  } catch {
    $sceneRec.error = $_.Exception.Message
    Write-Warn ("Cena {0}: erro na API: {1}" -f $idx, $_.Exception.Message)
  }

  $report.scenes += $sceneRec
}

Write-Info ("Imagens geradas: {0} / {1}" -f $generated, $scenes.Count)

$reportPath = Join-Path $OutputAbs "scene_images_report.json"
($report | ConvertTo-Json -Depth 10) | Set-Content -Encoding UTF8 $reportPath
Write-Info ("OK: relatório em " + (Resolve-Path $reportPath).Path)

if ($CloseWhenDone -and $startedHere -and $proc -ne $null) {
  Write-Info "Encerrando SD.Next..."
  try {
    # kill tree to close the cmd window too
    & taskkill /PID $proc.Id /T /F | Out-Null
  } catch {
    try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
  }
}

Write-Info "=== Processo concluído ==="
