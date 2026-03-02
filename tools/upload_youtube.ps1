# tools\upload_youtube.ps1
param(
  [string]$VideoPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not $VideoPath) {
  throw "Informe -VideoPath (ex.: output\jobs\job_short_...\short.mp4)"
}

function Get-PythonCmd {
    if (Test-Path ".\.venv\Scripts\python.exe") { return (Resolve-Path ".\.venv\Scripts\python.exe").Path }
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    if (Get-Command py -ErrorAction SilentlyContinue) { return "py" }
    throw "Python não encontrado."
}

$PY = Get-PythonCmd
& $PY -c "import yaml, json; from core.youtube.uploader import upload_video; cfg=yaml.safe_load(open('config/config.yml','r',encoding='utf-8')); yt=cfg.get('youtube_upload',{}); res=upload_video(r'$VideoPath', yt.get('title','Arquivo Oculto — Upload'), yt.get('description','Conteúdo gerado com auxílio de IA.'), yt.get('tags',['arquivo oculto']), yt.get('privacy','unlisted'), yt.get('client_secret','secrets/client_secret.json'), yt.get('token_path','secrets/youtube_token.json')); print(json.dumps(res,ensure_ascii=False,indent=2))"
