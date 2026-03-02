# Healthcheck (pré-execução)

Este patch adiciona um healthcheck que roda antes do pipeline iniciar de verdade.

Ele checa:
- saída (output) gravável + espaço em disco
- ffmpeg disponível
- piper configurado
- whisper/faster-whisper importável
- diffusers/transformers importável
- model_path existe
- torch + CUDA + VRAM livre (se disponível)

## Executar manualmente (PowerShell)
  .\tools\healthcheck.ps1

## Config
healthcheck:
  enabled: true
  hard_fail: false
  min_free_disk_gb: 3.0
  min_vram_free_mb: 800

Se hard_fail=true e faltar algo crítico (error), o pipeline para no início.
