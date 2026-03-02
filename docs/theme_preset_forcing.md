# Fixar preset por job (episódio)

Crie um arquivo no diretório do job (ex.: output/jobs/job_YYYYMMDD_HHMMSS/):

- job_theme_preset_id.txt

Conteúdo: o ID exato do preset definido em presets/theme_presets_catalog.json
Exemplo:
desaparecimento_v2_nightsearch

Quando presente, o seletor usa esse preset (método=forced_id) e registra no sd_headless_report.json:
- theme_selection.method = "forced_id"
- theme_selection.forced_id = "..."
