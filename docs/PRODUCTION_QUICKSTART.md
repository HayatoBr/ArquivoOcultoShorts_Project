# Produção (Short) - 1 clique

## 1) Configure dependências
- Python 3.10+
- FFmpeg no PATH (ou configure healthcheck.ffmpeg_path)
- Piper (configure tts.piper_path)
- Whisper CLI (configure paths.whisper_exe / subs.whisper_exe conforme seu config)
- Models e assets (não incluídos neste zip)

## 2) Rodar healthcheck
  .\tools\run_short.ps1 -DryRun

## 3) Rodar 1 vídeo
  .\START_AUTOMATION_SHORT.bat
ou
  .\tools\run_short.ps1

## 4) Rodar em batch
  .\tools\run_batch_short.ps1 -Count 5 -SleepSeconds 10

## 5) Agendar (Task Scheduler)
  .\tools\create_scheduled_tasks.ps1 -Time "09:00" -BatchCount 1

## 6) Upload YouTube (opcional)
1) Crie um projeto no Google Cloud + OAuth Client (Desktop)
2) Salve `secrets/client_secret.json`
3) Instale deps:
   pip install -r requirements_youtube.txt
4) Faça upload:
   .\tools\upload_youtube.ps1 -VideoPath "output\jobs\...\short.mp4"
