# ArquivoOcultoShorts Project

Patch local aplicado por PowerShell.

## CorreÃ§Ãµes desta rodada
- RUN_SHORT_TEST_SDXL.bat e RUN_SHORT_PROD_SDXL.bat corrigidos
- config.sdxl.yml ajustado para llama3.2:3b
- Prompt compiler com normalizaÃ§Ã£o PT->EN
- Loader do UNet Lightning via state_dict
- SeleÃ§Ã£o da melhor tentativa de narraÃ§Ã£o
- Guard rails de deduplicaÃ§Ã£o visual

## Modelos SDXL esperados
- models/sdxl/sd_xl_base_1.0_0.9vae.safetensors
- models/sdxl/sdxl_lightning_4step_unet.safetensors