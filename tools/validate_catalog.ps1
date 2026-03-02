param(
  [string]$CatalogPath = "presets\theme_presets_catalog.json",
  [switch]$FixIfMissing
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (!(Test-Path $CatalogPath)) {
  if ($FixIfMissing) {
    Write-Host "Catalog ausente. Criando default automático..."
    python - << 'PYCODE'
from pathlib import Path
from core.agents.theme_catalog_validator import ensure_default_catalog
p = Path("presets/theme_presets_catalog.json")
created = ensure_default_catalog(p)
print("Criado:", created)
PYCODE
  } else {
    Write-Host "Catalog não encontrado:" $CatalogPath
  }
  exit 0
}

python - << 'PYCODE'
from pathlib import Path
from core.agents.theme_catalog_validator import load_catalog, validate_catalog
p = Path("presets/theme_presets_catalog.json")
cat = load_catalog(p)
ok, errors = validate_catalog(cat)
if ok:
    print("Catalog OK.")
else:
    print("Erros encontrados:")
    for e in errors:
        print("-", e)
PYCODE
