param(
    [string]$OutputDir = "outputs/ui-captures",
    [int]$Port = 8517,
    [int]$StartupTimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$output = Join-Path $root $OutputDir
New-Item -ItemType Directory -Force -Path $output | Out-Null

$chromeCandidates = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
)
$chrome = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) {
    throw "Chrome or Edge executable was not found."
}

$env:TRADEGUARD_ENABLE_PRIVATE_WORKSPACE = "false"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"

$stdout = Join-Path $output "streamlit-stdout.log"
$stderr = Join-Path $output "streamlit-stderr.log"
$process = Start-Process -FilePath "python" -ArgumentList @(
    "-m", "streamlit", "run", "streamlit_app.py",
    "--server.headless=true",
    "--server.address=127.0.0.1",
    "--server.port=$Port",
    "--browser.gatherUsageStats=false"
) -WorkingDirectory $root -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr

function Wait-ForHealth {
    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    $health = "http://127.0.0.1:$Port/_stcore/health"
    while ((Get-Date) -lt $deadline) {
        if ($process.HasExited) {
            throw "Streamlit exited before UI capture. See $stdout and $stderr"
        }
        try {
            $response = Invoke-WebRequest -Uri $health -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200 -and $response.Content.Trim().ToLowerInvariant() -eq "ok") {
                return
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "Streamlit did not become healthy within $StartupTimeoutSeconds seconds."
}

function Capture-Page {
    param(
        [string]$Name,
        [string]$PathAndQuery,
        [int]$Width,
        [int]$Height,
        [int]$BudgetMilliseconds = 14000
    )
    $target = Join-Path $output "$Name.png"
    $url = "http://127.0.0.1:$Port/$PathAndQuery"
    $arguments = @(
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        "--window-size=$Width,$Height",
        "--virtual-time-budget=$BudgetMilliseconds",
        "--screenshot=$target",
        $url
    )
    & $chrome @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Browser capture failed for $Name with exit code $LASTEXITCODE"
    }
    if (-not (Test-Path $target)) {
        throw "Browser did not create screenshot: $target"
    }
    $size = (Get-Item $target).Length
    if ($size -lt 20000) {
        throw "Screenshot appears incomplete: $target ($size bytes)"
    }
    Write-Host "$Name -> $target ($size bytes)"
}

try {
    Wait-ForHealth
    Capture-Page -Name "01-decision-desk-desktop" -PathAndQuery "?mode=decision&scenario=oa_high_risk" -Width 1440 -Height 2200
    Capture-Page -Name "02-portfolio-official-data" -PathAndQuery "?mode=portfolio&scenario=oa_high_risk" -Width 1440 -Height 1800
    Capture-Page -Name "03-evidence-submission" -PathAndQuery "?mode=evidence&scenario=oa_high_risk" -Width 1440 -Height 1800
    Capture-Page -Name "04-presentation-mode" -PathAndQuery "?presentation=1&scenario=oa_high_risk" -Width 1440 -Height 2200
    Capture-Page -Name "05-decision-desk-mobile" -PathAndQuery "?mode=decision&scenario=oa_high_risk" -Width 430 -Height 1900 -BudgetMilliseconds 16000

    $manifest = [ordered]@{
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        entrypoint = "streamlit_app.py"
        public_private_workspace = $env:TRADEGUARD_ENABLE_PRIVATE_WORKSPACE
        browser = $chrome
        captures = Get-ChildItem -Path $output -Filter "*.png" | Sort-Object Name | ForEach-Object {
            [ordered]@{
                file = $_.Name
                bytes = $_.Length
                sha256 = (Get-FileHash -Algorithm SHA256 -Path $_.FullName).Hash.ToLowerInvariant()
            }
        }
    }
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $output "capture-manifest.json")
} finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}
