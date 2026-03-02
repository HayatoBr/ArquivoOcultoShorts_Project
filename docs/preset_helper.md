# Preset Helper (PowerShell)

Este utilitário deixa a escolha do preset do tema 100% automática antes do render.

## Comandos

### Listar presets
- Todos:
  `.	ools\preset_helper.ps1 -List`

- Por tema:
  `.	ools\preset_helper.ps1 -List -Theme desaparecimento`

### Auto (escolha ponderada com seed por job)
`.	ools\preset_helper.ps1 -Auto -JobDir "output\jobs\job_YYYYMMDD_HHMMSS"`

Opcional:
- Restringir por tema:
  `-Theme conspiracao`
- Determinístico (sempre pega o primeiro):
  `-Deterministic`

### Fixar manualmente um preset específico
`.	ools\preset_helper.ps1 -Set -JobDir "output\jobs\job_..." -PresetId "desaparecimento_v2_nightsearch"`

### Ver preset atual do job
`.	ools\preset_helper.ps1 -Get -JobDir "output\jobs\job_..."`

## O que ele faz
Ele grava/atualiza:
- `output\jobs\<job>\job_theme_preset_id.txt`

O pipeline lê esse arquivo e força o preset (`method = forced_id` no report).
