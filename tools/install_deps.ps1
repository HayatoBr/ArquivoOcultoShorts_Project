Write-Host "Instalando dependências do ArquivoOcultoShorts..." -ForegroundColor Cyan

$ErrorActionPreference = "Stop"

# Usa o Python padrão do sistema (py launcher do Windows)
$py = "py"

& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt

Write-Host "OK: dependências instaladas com sucesso." -ForegroundColor Green
