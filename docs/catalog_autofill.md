# Zero-config total do catálogo

Agora, além de criar um catálogo default quando estiver ausente, o sistema também:

- Preenche automaticamente temas/presets mínimos se o arquivo existir mas estiver incompleto:
  - desaparecimento
  - caso_historico
  - conspiracao
  - default

Quando aplica autofill, ele faz backup do catálogo original:
- presets/theme_presets_catalog.backup.<n>.json

## Tool PowerShell

AutoFill (sem rodar o pipeline):
  .\tools\catalog_autofill.ps1 -AutoFill

Validar:
  .\tools\catalog_autofill.ps1 -Validate

AutoFill + Validate:
  .\tools\catalog_autofill.ps1 -AutoFill -Validate
