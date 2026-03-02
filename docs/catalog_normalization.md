# Normalização do catálogo (automático + tool)

O pipeline pode normalizar automaticamente o arquivo de presets:

- Ordena temas e presets por `id`
- Converte `weight` para float (clamp >= 0)
- Remove campos vazios (ex.: strings vazias)
- Ignora campos desconhecidos dentro de um preset
- Mantém o JSON determinístico (bom para Git)

## Config
images:
  theme_presets:
    auto_normalize_catalog: true

## Tool PowerShell
Normalizar:
  .\tools\catalog_normalize.ps1 -Normalize

Normalizar + Validar:
  .\tools\catalog_normalize.ps1 -Normalize -Validate

## Auditoria
As mudanças aplicadas aparecem no bootstrap do catálogo, salvo no manifest do job:
- manifest.json -> theme_catalog_bootstrap.meta.normalize_changes
