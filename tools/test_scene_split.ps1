param(
  [Parameter(Mandatory=$false)][string]$ScriptPath = "assets\text\script.txt",
  [Parameter(Mandatory=$false)][int]$Seconds = 60
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if(!(Test-Path $ScriptPath)){ throw "Script não encontrado: $ScriptPath" }

$tmp = Join-Path $env:TEMP ("ao_scene_split_" + [guid]::NewGuid().ToString("N") + ".py")

@"
import os, sys, json
sys.path.insert(0, os.path.abspath('.'))
from core.agents.scene_splitter import split_script_into_scenes

p = r'''$ScriptPath'''
with open(p, 'r', encoding='utf-8') as f:
    txt = f.read()

scenes = split_script_into_scenes(txt, target_seconds=int($Seconds))
print('Cenas:', len(scenes))
for s in scenes:
    print(f"[{s['idx']}] {s['start_s']}s->{s['end_s']}s ({s['duration_s']}s): {s['text'][:80]}")

out = os.path.join('output','scenes.json')
os.makedirs('output', exist_ok=True)
with open(out, 'w', encoding='utf-8') as f:
    json.dump(scenes, f, ensure_ascii=False, indent=2)
print('OK: salvo em', out)
"@ | Set-Content -Encoding UTF8 $tmp

py $tmp
Remove-Item -Force $tmp -ErrorAction SilentlyContinue
