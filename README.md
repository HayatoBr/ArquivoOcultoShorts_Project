# ArquivoOcultoShorts_Project

Automação local para gerar vídeos curtos investigativos no estilo do canal **Arquivo Oculto**.

## Objetivo

Gerar Shorts verticais prontos para YouTube Shorts, TikTok e Reels com:

- escolha automática de tema investigativo
- pesquisa documental
- roteiro narrativo
- narração em PT-BR
- legendas automáticas
- imagens documentais com SDXL
- trilha e efeitos sonoros
- render final em vídeo vertical

## Stack principal

- **Roteiro / planner:** Ollama com `qwen2.5:7b-instruct-q4_K_M`
- **Imagens:** SDXL Base + SDXL Lightning 4-step UNet
- **TTS:** Piper (`pt_BR-faber-medium`)
- **Legendas:** Faster-Whisper XXL
- **Render:** FFmpeg
- **SO alvo:** Windows com PowerShell
- **GPU alvo:** NVIDIA GTX 1660 Ti 6GB

## Fluxo do pipeline

1. Healthcheck do ambiente
2. Descoberta ou escolha do tema
3. Pesquisa híbrida (Wikipedia + DDGS)
4. Geração do roteiro
5. Planejamento de cenas
6. Narração com Piper
7. Geração de legendas
8. Planejamento CapCut (hook, overlays e SFX)
9. Mixagem de áudio
10. Geração de imagens
11. Render final

## Estrutura do projeto

```text
ao/
  core/
    agents.py
    audio_mix_ffmpeg.py
    capcut_engine.py
    images.py
    media_utils.py
    pipeline_short.py
    script_generator.py
    sfx_planner.py
    style.py
    subs.py
    tts.py
    whisper_subs.py
  providers/
    ollama.py
    openai_writer.py
    research.py
  render/
    render_short.py
  utils/
    config_loader.py
    logger.py
```

## Assets esperados

```text
assets/
  music/
  sfx/
    ambience/
    archive/
    hits/
    transitions/
  watermark/
    watermark.png
```

## Configuração principal

Arquivo: `config.sdxl.yml`

Pontos importantes:

- modelo local do Ollama
- caminhos do FFmpeg, Piper e Whisper
- alvo de duração do Short
- resolução e parâmetros do SDXL
- configuração da pesquisa
- watermark
- pastas de música e SFX

## Requisitos

- Python 3.11+
- FFmpeg instalado
- Piper instalado
- Faster-Whisper XXL standalone
- Ollama rodando localmente
- CUDA funcionando no PyTorch

## Como rodar

No PowerShell, dentro da raiz do projeto:

```powershell
RUN_SHORT_TEST_SDXL.bat
```

Ou, se você usa execução manual:

```powershell
.\.venv\Scripts\python.exe main.py --config config.sdxl.yml --test
```

## Saída

Os jobs são gravados em:

```text
output/jobs/job_short_YYYYMMDD_HHMMSS/
```

Arquivos comuns do job:

- `script.txt`
- `script_clean.txt`
- `script.json`
- `research.txt`
- `meta.txt`
- `narration.wav`
- `mixed_audio.wav`
- `subs.srt`
- `images/`
- `job_data.json`
- `short.mp4`

## Módulos principais

### `ao/providers/research.py`
Responsável por:
- descobrir temas
- evitar repetição com `topic_history.json`
- extrair pesquisa limpa
- bloquear resultados irrelevantes

### `ao/core/script_generator.py`
Responsável por:
- gerar roteiro
- limpar texto para TTS
- ajustar meta de palavras
- selecionar a melhor tentativa

### `ao/core/agents.py`
Responsável por:
- normalizar pesquisa
- montar plano de cenas
- deduplicar itens de pesquisa
- reforçar coerência visual

### `ao/core/style.py`
Responsável por:
- montar prompts finais do SDXL
- normalizar visual
- definir motion
- aplicar style base e negative prompt

### `ao/core/capcut_engine.py`
Responsável por:
- gerar hook
- gerar overlays curtos
- montar um plano visual em estilo Short/CapCut

### `ao/core/sfx_planner.py`
Responsável por:
- escolher SFX por categoria
- sincronizar eventos sonoros com o plano visual

### `ao/render/render_short.py`
Responsável por:
- montar o filtro de vídeo no FFmpeg
- aplicar motion
- aplicar overlays
- aplicar subtitles
- aplicar watermark
- renderizar o MP4 final

## Histórico de temas

O histórico fica em:

```text
output/topic_history.json
```

O pipeline salva:
- título
- slug
- chave canônica do tema

Isso ajuda a evitar repetição de casos já usados.

## Segurança para YouTube

O projeto aplica filtros básicos para:
- gore detalhado
- violência sexual
- linguagem excessivamente gráfica
- instruções perigosas

Ainda assim, revisão humana final é recomendada para temas sensíveis.

## Limitações conhecidas

- temas muito recentes ou ambíguos podem contaminar a pesquisa
- vozes TTS variam bastante conforme a pontuação do roteiro
- SDXL Lightning em GPU de 6GB exige fallback de resolução
- overlays e fontes no FFmpeg no Windows precisam de caminho de fonte confiável

## Próximas evoluções sugeridas

- mais cortes visuais por cena
- transições rápidas estilo CapCut
- overlays por palavra-chave
- mapas, documentos e gráficos processuais
- seletor de temas por faixa editorial
- melhor classificação factual por tipo de caso

## Licenças e direitos

- verifique a licença dos SFX e músicas usados
- a pasta `assets/sfx` foi organizada com base em efeitos obtidos do YouTube Studio
- revise termos de uso antes de redistribuir os assets

## Observação importante

Quando editar o projeto:
- sempre use os arquivos atuais
- evite aplicar patch antigo por cima de versão nova
- valide o log após cada mudança