# ArquivoOcultoShorts (Shorts Investigativos 100% Automático)

Pipeline para gerar **Shorts narrativos (mistério / casos reais / eventos controversos)** com:
roteiro → cenas → imagens (Stable Diffusion via Diffusers headless) → TTS (Piper) → trilha/mix (FFmpeg) → legendas (Whisper) → render final (FFmpeg) → organização por **job**.

> Foco: estabilidade em **GTX 1660 Ti (6GB)**, evitando imagens pretas (FP16) e mantendo identidade visual do canal.

---

## Requisitos (Windows)

- Python **3.11** (recomendado) + venv
- **FFmpeg** (ex: `C:\ffmpeg\bin\ffmpeg.exe`)
- **Piper** (ex: `C:\piper\piper.exe` + modelo `.onnx`)
- **Whisper Standalone** ou `faster-whisper` (conforme seu setup)
- (Opcional) **Ollama** para fallback/local QA (`http://127.0.0.1:11434`)

---

## Instalação

Na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
```

Dependências típicas (mínimo):
- `torch` (CUDA) compatível
- `diffusers`, `transformers`, `safetensors`, `accelerate`
- `openai` (para provider principal em produção)
- `ddgs>=7.0.0` (busca gratuita no TestMode)
- `pyyaml`, etc.

---

## Configuração (config/config.yml)

### Caminhos (exemplo)
```yaml
paths:
  output_dir: "output"
  ffmpeg_exe: "C:/ffmpeg/bin/ffmpeg.exe"
  piper_exe:  "C:/piper/piper.exe"
  piper_model: "C:/piper/models/pt_BR-faber-medium.onnx"

images:
  model_path: "models/dreamshaper_8.safetensors"
  # 3–6 cenas (prompts) por vídeo
  max_scenes: 5
  steps: 20
  cfg_scale: 6.5
  width: 576
  height: 1024
  dtype: "float32"  # importante na GTX 1660 Ti
  seed: 12345
  retry_attempts: 3
  retry_base_delay: 2

image_style:
  base_prompt: "cinematic, dramatic lighting, realistic, film grain, shallow depth of field, close-up framing, high detail"
  negative_prompt: "text, watermark, logo, blurry, lowres, bad anatomy, bad hands, extra fingers, deformed, distorted face, mutated, disfigured, cropped, out of frame, jpeg artifacts"

video:
  seconds: 60
  tts_fit_attempts: 3
  tts_fit_tolerance_sec: 1.5

llm:
  provider: "openai"           # openai | ollama
  openai_model: "gpt-4o-mini"
  ollama_url: "http://127.0.0.1:11434"
  ollama_model: "llama3.2:latest"
  ollama_fallback_models:
    - "llama3.1:latest"
```

### Variáveis de ambiente
```powershell
$env:OPENAI_API_KEY="SUA_CHAVE_AQUI"
# (Opcional)
$env:OLLAMA_URL="http://127.0.0.1:11434"
$env:OLLAMA_MODEL="llama3.2:latest"
```

---

## Como rodar

### Teste gratuito (sem gastar OpenAI)
Usa **Wiki + DDG + Ollama** para gerar roteiro e cenas.

```powershell
.\tools\run_short.ps1 -TestMode
```

### Produção (OpenAI como principal + fallback local)
```powershell
.\tools\run_short.ps1
```

### Debug
```powershell
.\tools\run_short.ps1 -TestMode -Debug
```

Logs ficam em:
- `output\logs\run_short_*.log`
- e também no `output\jobs\job_short_...\manifest.json`

---

## Estrutura de saída (output/jobs)

Cada execução cria um job:
```
output/jobs/job_short_YYYYMMDD_HHMMSS/
  script.txt
  script_report.json
  scenes.json
  images/
    scene_01.png
    scene_02.png
    ...
  narration.wav
  mix.wav
  subs.srt
  subs.ass
  short.mp4
  manifest.json
```

---

## Observações importantes (GTX 1660 Ti)
- Use **float32** (evita imagens pretas / instabilidade)
- Steps 18–22 e CFG 6–7 costumam ser estáveis
- O pipeline faz retry e fallback de imagem se necessário

---

## GitHub
- Inclua `models/` e `assets/` no `.gitignore`
- Versione apenas código + config + docs

---

## Roadmap curto
- Logs por cena (prompt final + contagem estimada)
- Melhorar QA do roteiro (Ollama como revisor final)
- Upload YouTube opcional (desligado por padrão)
## Atalhos .BAT (1-clique)
Na raiz do projeto (duplo clique):

- `RUN_SHORT.bat` → produção (OpenAI como principal + fallback local)
- `RUN_SHORT_TESTMODE.bat` → **teste grátis** (Wiki + DDG + Ollama; não usa OpenAI)
- `RUN_SHORT_DRYRUN.bat` → só healthcheck
- `RUN_SHORT_TESTMODE_DEBUG.bat` → TestMode + logs extra

> Todos chamam `tools/run_short.ps1` e já apontam para o Python do `.venv` automaticamente (se existir).
