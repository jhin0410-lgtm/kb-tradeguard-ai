$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot
python -m pytest -q
python -m compileall -q app.py src tests scripts
python -c "import app; import src"
