param(
  [string]$CatalogPath = "presets\theme_presets_catalog.json",
  [switch]$Normalize,
  [switch]$Validate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (!(Test-Path $CatalogPath)) {
  Write-Host "Catalog não encontrado:" $CatalogPath
  exit 1
}

if ($Normalize) {
  python - << 'PYCODE'
from pathlib import Path
from core.agents.theme_catalog_validator import load_catalog, write_catalog
from core.agents.theme_catalog_normalizer import normalize_catalog, catalogs_equal
p = Path("presets/theme_presets_catalog.json")
cat = load_catalog(p)
cat2, changes = normalize_catalog(cat)
if changes and not catalogs_equal(cat2, cat):
    write_catalog(p, cat2)
    print("Normalize aplicado. Mudanças:")
    for c in changes:
        print("-", c)
else:
    print("Normalize: nenhuma mudança necessária.")
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
