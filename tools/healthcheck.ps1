<#
Arquivo: tools\healthcheck.ps1
Executa checagens do ambiente e imprime o resultado em JSON.
#>
param(
  [string]$ConfigPath = "config\config.yml"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

python - << 'PYCODE'
import yaml, json
from core.utils.healthcheck import run_healthcheck

with open(r"config/config.yml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

res = run_healthcheck(cfg)
print(json.dumps(res, ensure_ascii=False, indent=2))
print("OK geral:", res.get("ok"))
PYCODE
