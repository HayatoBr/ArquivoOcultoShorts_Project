param(
  [string]$CatalogPath = "presets\theme_presets_catalog.json",
  [switch]$AutoFill,
  [switch]$Validate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (!(Test-Path $CatalogPath)) {
  Write-Host "Catalog não encontrado:" $CatalogPath
  exit 1
}

if ($AutoFill) {
  python - << 'PYCODE'
from pathlib import Path
from core.agents.theme_catalog_validator import load_catalog, ensure_minimum_themes, write_catalog
p = Path("presets/theme_presets_catalog.json")
cat = load_catalog(p)
cat2, changes = ensure_minimum_themes(cat)
if changes:
    write_catalog(p, cat2)
    print("AutoFill aplicado. Mudanças:")
    for c in changes:
        print("-", c)
else:
    print("AutoFill: nenhuma mudança necessária.")
PYCODE
}

if ($Validate) {
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
}
