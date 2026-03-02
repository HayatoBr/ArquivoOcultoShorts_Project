param(
  [Parameter(Mandatory=$false)][string]$Config = "config\config.yml",
  [Parameter(Mandatory=$false)][string]$ScriptPath = "assets\text\script.txt",
  [Parameter(Mandatory=$false)][string]$OutDir = "assets\images",
  [Parameter(Mandatory=$false)][int]$Seconds = 60
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if(!(Test-Path $ScriptPath)){ throw "Script não encontrado: $ScriptPath" }

$tmp = Join-Path $env:TEMP ("ao_gen_imgs_" + [guid]::NewGuid().ToString("N") + ".py")

@"
import os, sys, json
sys.path.insert(0, os.path.abspath('.'))
import yaml
from core.images.image_generator_multi import generate_images_from_script

cfg_path = r'''$Config'''
with open(cfg_path, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f) or {}

sp = r'''$ScriptPath'''
with open(sp, 'r', encoding='utf-8') as f:
    script = f.read()

scenes, paths = generate_images_from_script(cfg, script, r'''$OutDir''', target_seconds=int($Seconds))

os.makedirs('output', exist_ok=True)
with open(os.path.join('output','scene_images_report.json'), 'w', encoding='utf-8') as f:
    json.dump({'scenes': scenes, 'paths': paths}, f, ensure_ascii=False, indent=2)

print('Cenas:', len(scenes))
ok = sum(1 for s in scenes if os.path.exists(s.get('image_path','')))
print('Imagens geradas:', ok, '/', len(scenes))
print('OK: relatório em output/scene_images_report.json')
"@ | Set-Content -Encoding UTF8 $tmp

py $tmp
Remove-Item -Force $tmp -ErrorAction SilentlyContinue
