# Bootstrap automático do catálogo (pipeline)

No início da execução, o pipeline faz:

- Se o catálogo não existir e auto_create_default_if_missing=true:
  cria um catálogo default mínimo automaticamente.

- Se auto_validate_catalog=true:
  valida estrutura, IDs duplicados e pesos inválidos.

- Se estiver inválido:
  - faz backup do arquivo original para:
    presets/theme_presets_catalog.invalid.<n>.json
  - se auto_create_default_if_missing=true, substitui por um default mínimo
    para o pipeline continuar rodando.

## Hard fail (opcional)
Se você quiser travar o pipeline quando o catálogo estiver inválido:

images:
  theme_presets:
    hard_fail_on_invalid_catalog: true

## Auditoria
O resultado do bootstrap é salvo no manifest do job:
- manifest.json -> theme_catalog_bootstrap
