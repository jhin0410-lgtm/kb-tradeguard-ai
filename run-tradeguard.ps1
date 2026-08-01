param(
    [ValidateSet("decision", "analyst", "portfolio", "evidence")]
    [string]$Mode = "decision",
    [int]$Port = 8501,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pythonExe = $null
$pythonArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonExe = "py"
    $pythonArgs = @("-3.11")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonExe = "python"
} else {
    throw "Python 3.11 이상을 찾을 수 없습니다. Python을 설치한 뒤 다시 실행하십시오."
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "[1/3] 가상환경을 생성합니다." -ForegroundColor Cyan
    & $pythonExe @pythonArgs -m venv .venv
}

if (-not $SkipInstall) {
    Write-Host "[2/3] 의존성을 확인합니다." -ForegroundColor Cyan
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
}

Write-Host "[3/3] KB TradeGuard AI를 실행합니다." -ForegroundColor Green
Write-Host "브라우저 주소: http://localhost:$Port/?mode=$Mode"
& $venvPython -m streamlit run streamlit_app.py --server.port $Port --server.headless true
