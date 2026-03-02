Param(
  [Parameter(Mandatory=$false)][string]$ModelPath = "",
  [Parameter(Mandatory=$false)][string]$ScriptPath = "assets\text\script.txt",
  [Parameter(Mandatory=$false)][int]$Count = 4,
  [Parameter(Mandatory=$false)][int]$Width = 576,
  [Parameter(Mandatory=$false)][int]$Height = 1024,
  [Parameter(Mandatory=$false)][int]$Steps = 22,
  [Parameter(Mandatory=$false)][double]$CfgScale = 6.5,
  [Parameter(Mandatory=$false)][string]$Negative = "lowres, blurry, watermark, text, logo",
  [Parameter(Mandatory=$false)][int]$Seed = 0,
  [Parameter(Mandatory=$false)][string]$Prompt = "cinematic photo, dramatic lighting, ultra detailed, sharp focus",
  [switch]$AttentionSlicing,
  [switch]$VaeSlicing,
  [switch]$CpuOffload
)

$ErrorActionPreference = "Stop"

function Write-Info($m){ Write-Host $m }

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot ".." )).Path
Set-Location $ProjectDir

# Preferir modelo local do projeto, se existir
if ([string]::IsNullOrWhiteSpace($ModelPath)) {
  $candidate = Join-Path $ProjectDir "models\dreamshaper_8.safetensors"
  if (Test-Path $candidate) {
    $ModelPath = $candidate
  }
}

if ([string]::IsNullOrWhiteSpace($ModelPath) -or !(Test-Path $ModelPath)) {
  throw "ModelPath inválido: '$ModelPath'. Informe -ModelPath ou coloque o modelo em .\models\\dreamshaper_8.safetensors"
}

$OutDir = Join-Path $ProjectDir "output\images"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Info "=== SD Headless Runner (Diffusers) ==="
Write-Info "Projeto:  $ProjectDir"
Write-Info "Modelo:   $ModelPath"
Write-Info "OutDir:   $OutDir"
Write-Info "Script:   $ScriptPath"

# Usa o Python do venv do projeto (recomendado)
$pyCmd = $null
$venv1 = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$venv2 = Join-Path $ProjectDir "venv\Scripts\python.exe"
if (Test-Path $venv1) { $pyCmd = $venv1 }
elseif (Test-Path $venv2) { $pyCmd = $venv2 }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $pyCmd = "python" }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $pyCmd = "py" }

if (-not $pyCmd) {
  throw "Python não encontrado. Crie/ative um venv em .\.venv (ou .\venv)."
}

$gen = Join-Path $ProjectDir "scripts\generate_images.py"
if (!(Test-Path $gen)) {
  throw "Não achei $gen. Copie o arquivo scripts\\generate_images.py do patch."
}

$argList = @(
  $gen,
  "--model", $ModelPath,
  "--outdir", $OutDir,
  "--count", $Count,
  "--width", $Width,
  "--height", $Height,
  "--steps", $Steps,
  "--cfg", $CfgScale,
  "--negative", $Negative,
  "--prompt", $Prompt
)

if ($Seed -ne 0) {
  $argList += @("--seed", $Seed)
}

if ($AttentionSlicing) { $argList += "--attention-slicing" }
if ($VaeSlicing) { $argList += "--vae-slicing" }
if ($CpuOffload) { $argList += "--cpu-offload" }

if (![string]::IsNullOrWhiteSpace($ScriptPath)) {
  $argList += @("--script", $ScriptPath)
}

Write-Info "Rodando geração headless..."
& $pyCmd @argList
Write-Info "=== Concluído ==="
