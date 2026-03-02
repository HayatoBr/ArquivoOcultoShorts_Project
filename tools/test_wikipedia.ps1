param(
  [string]$Query = "caso não resolvido"
)

$ErrorActionPreference = "Stop"

Write-Host "Testando Wikipedia API (com User-Agent)..." -ForegroundColor Cyan

$py = "py"
$proj = Split-Path -Parent $PSScriptRoot   # raiz do projeto (um nível acima de tools)
$tmp  = Join-Path $env:TEMP ("ao_test_wikipedia_" + [guid]::NewGuid().ToString("N") + ".py")

$code = @"
import os, sys
# garante import do pacote local 'core'
proj = r'''$proj'''
if proj not in sys.path:
    sys.path.insert(0, proj)
os.chdir(proj)

from core.script.wikipedia_source import search_titles, fetch_extract

q = r'''$Query'''
titles = search_titles(q, cfg=None, limit=3)
print("Titulos:", titles)
if titles:
    ex = fetch_extract(titles[0], cfg=None, sentences=6)
    print("\nExtract:\n", ex[:600])
"@

Set-Content -Encoding UTF8 -Path $tmp -Value $code

try {
  & $py $tmp
  $exit = $LASTEXITCODE
  if ($exit -ne 0) {
    throw "Falhou o teste da Wikipedia (exitcode=$exit). Veja o traceback acima."
  }
  Write-Host "OK: Wikipedia funcionando (titulos/extract acima)." -ForegroundColor Green
} finally {
  Remove-Item -Force -ErrorAction SilentlyContinue $tmp
}
