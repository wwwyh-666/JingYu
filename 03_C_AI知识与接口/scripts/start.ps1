$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:TEMP = Join-Path $projectRoot 'tmp'
$env:TMP = $env:TEMP
$env:PYTHONIOENCODING = 'utf-8'
& (Join-Path $projectRoot '.venv\Scripts\python.exe') -m uvicorn app.main:app --host 127.0.0.1 --port 8000
