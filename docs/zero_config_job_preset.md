# Zero-config: Preset por Job (automático)

A partir deste patch, o pipeline faz isso sozinho:

1) Gera o roteiro do job
2) Detecta o tema (LLM opcional + fallback heurístico)
3) Seleciona um preset do catálogo (A/B com seed estável por job)
4) Grava no job:

- job_theme_preset_id.txt
- job_theme_preset_meta.json

Isso torna a renderização repetível (o mesmo job mantém o mesmo preset).

## Como desativar
No config.yml:

images:
  theme_presets:
    auto_write_job_preset_id: false
