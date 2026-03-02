<#
Arquivo: tools\preset_helper.ps1

Objetivo:
- Listar presets disponíveis do catálogo presets\theme_presets_catalog.json
- Selecionar um preset (por tema ou por ID) e gravar automaticamente no job:
  output\jobs\<job>\job_theme_preset_id.txt

Uso rápido:
  # Listar tudo
  .\tools\preset_helper.ps1 -List

  # Listar por tema
  .\tools\preset_helper.ps1 -List -Theme desaparecimento

  # Escolher automaticamente (ponderado, seed por job) e escrever no job
  .\tools\preset_helper.ps1 -Auto -JobDir "output\jobs\job_20260228_235500"

  # Fixar manualmente um ID no job
  .\tools\preset_helper.ps1 -Set -JobDir "output\jobs\job_20260228_235500" -PresetId "desaparecimento_v2_nightsearch"

  # Mostrar qual preset está fixado no job
  .\tools\preset_helper.ps1 -Get -JobDir "output\jobs\job_20260228_235500"
#>

param(
  [switch]$List,
  [switch]$Auto,
  [switch]$Set,
  [switch]$Get,

  [string]$Theme = "",
  [string]$PresetId = "",
  [string]$JobDir = "",

  [string]$CatalogPath = "presets\theme_presets_catalog.json",
  [switch]$Deterministic
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Read-JsonFile([string]$Path) {
  if (!(Test-Path -LiteralPath $Path)) {
    throw "Catalog não encontrado: $Path"
  }
  $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
  return $raw | ConvertFrom-Json
}

function Get-JobId([string]$JobDir) {
  $name = Split-Path -Leaf $JobDir
  if ([string]::IsNullOrWhiteSpace($name)) { return "" }
  return $name
}

function Hash-JobSeed([string]$JobId) {
  # Seed estável (não depende do hash interno do PowerShell)
  # Implementa um hash simples (FNV-1a 32-bit) em UTF-8.
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($JobId)
  [uint32]$hash = 2166136261
  foreach ($b in $bytes) {
    $hash = $hash -bxor [uint32]$b
    $hash = $hash * 16777619
  }
  return [int]($hash -band 0x7fffffff)
}

function Weighted-Choice($Items, [int]$Seed) {
  # Items: array de objetos com propriedade weight
  $rnd = New-Object System.Random($Seed)
  $total = 0.0
  $weights = @()
  foreach ($it in $Items) {
    $w = 1.0
    if ($null -ne $it.weight) {
      $w = [double]$it.weight
    }
    if ($w -lt 0) { $w = 0 }
    $weights += $w
    $total += $w
  }
  if ($total -le 0) { return $Items[0] }

  $r = $rnd.NextDouble() * $total
  $acc = 0.0
  for ($i=0; $i -lt $Items.Count; $i++) {
    $acc += $weights[$i]
    if ($r -le $acc) { return $Items[$i] }
  }
  return $Items[$Items.Count-1]
}

function Flatten-Presets($Catalog) {
  $out = @()
  $themes = $Catalog.themes
  foreach ($t in $themes.PSObject.Properties.Name) {
    $items = $themes.$t
    foreach ($it in $items) {
      $obj = [PSCustomObject]@{
        theme = $t
        id = $it.id
        weight = $it.weight
        visual_profile = $it.visual_profile
        negative_profile = $it.negative_profile
        character_anchor_hint = $it.character_anchor_hint
      }
      $out += $obj
    }
  }
  return $out
}

function Write-JobPresetId([string]$JobDir, [string]$PresetId) {
  if ([string]::IsNullOrWhiteSpace($JobDir)) { throw "JobDir é obrigatório." }
  if ([string]::IsNullOrWhiteSpace($PresetId)) { throw "PresetId é obrigatório." }
  if (!(Test-Path -LiteralPath $JobDir)) {
    throw "JobDir não existe: $JobDir"
  }
  $path = Join-Path $JobDir "job_theme_preset_id.txt"
  Set-Content -LiteralPath $path -Value $PresetId -Encoding UTF8
  Write-Host "OK: preset fixado no job -> $path"
}

function Read-JobPresetId([string]$JobDir) {
  if ([string]::IsNullOrWhiteSpace($JobDir)) { throw "JobDir é obrigatório." }
  $path = Join-Path $JobDir "job_theme_preset_id.txt"
  if (!(Test-Path -LiteralPath $path)) {
    Write-Host "(vazio) Nenhum preset fixado ainda. Arquivo não existe: $path"
    return ""
  }
  $id = (Get-Content -LiteralPath $path -Raw -Encoding UTF8).Trim()
  Write-Host "Preset atual do job: $id"
  return $id
}

# --- Main ---
$catalog = Read-JsonFile $CatalogPath
$flat = Flatten-Presets $catalog

if ($List) {
  if (-not [string]::IsNullOrWhiteSpace($Theme)) {
    $flat | Where-Object { $_.theme -eq $Theme } | Sort-Object id | Format-Table theme,id,weight -AutoSize
  } else {
    $flat | Sort-Object theme,id | Format-Table theme,id,weight -AutoSize
  }
  exit 0
}

if ($Get) {
  [void](Read-JobPresetId $JobDir)
  exit 0
}

if ($Set) {
  Write-JobPresetId $JobDir $PresetId
  exit 0
}

if ($Auto) {
  if ([string]::IsNullOrWhiteSpace($JobDir)) { throw "JobDir é obrigatório em -Auto." }
  if (!(Test-Path -LiteralPath $JobDir)) { throw "JobDir não existe: $JobDir" }

  $jobId = Get-JobId $JobDir
  $seed = Hash-JobSeed $jobId

  # Se o usuário passou Theme, limita a seleção
  $choices = $flat
  if (-not [string]::IsNullOrWhiteSpace($Theme)) {
    $choices = $flat | Where-Object { $_.theme -eq $Theme }
    if ($choices.Count -eq 0) { throw "Nenhum preset encontrado para o tema: $Theme" }
  }

  $chosen = $null
  if ($Deterministic) {
    $chosen = $choices | Sort-Object id | Select-Object -First 1
    Write-Host "Seleção determinística: $($chosen.id)"
  } else {
    $chosen = Weighted-Choice $choices $seed
    Write-Host "Seleção ponderada (seed=$seed, job=$jobId): $($chosen.id)"
  }

  Write-JobPresetId $JobDir $chosen.id
  exit 0
}

throw "Nenhuma ação selecionada. Use -List, -Auto, -Set ou -Get."
