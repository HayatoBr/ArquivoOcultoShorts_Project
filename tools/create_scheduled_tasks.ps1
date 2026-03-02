# tools\create_scheduled_tasks.ps1
param(
  [string]$TaskName = "ArquivoOcultoShorts_DailyShort",
  [string]$Time = "09:00",
  [int]$BatchCount = 1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

$project = (Get-Location).Path
$ps = Join-Path $project "tools\run_batch_short.ps1"

# Build action
$action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ps`" -Count $BatchCount"

# Create or replace via schtasks (most compatible)
$cmd = @(
  "/Create",
  "/F",
  "/TN", $TaskName,
  "/SC", "DAILY",
  "/ST", $Time,
  "/TR", $action
)

Write-Host "Criando tarefa: $TaskName @ $Time (count=$BatchCount)" -ForegroundColor Cyan
schtasks.exe @cmd | Out-Host

Write-Host "OK. Para testar agora:" -ForegroundColor Green
Write-Host "  schtasks /Run /TN `"$TaskName`""
