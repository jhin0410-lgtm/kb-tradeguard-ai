param(
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

$address = Get-NetIPAddress -AddressFamily IPv4 `
    | Where-Object {
        $_.IPAddress -notlike "127.*" -and
        $_.IPAddress -notlike "169.254.*" -and
        $_.PrefixOrigin -ne "WellKnown"
    } `
    | Sort-Object -Property InterfaceMetric `
    | Select-Object -First 1 -ExpandProperty IPAddress

if (-not $address) {
    throw "사용 가능한 로컬 IPv4 주소를 찾지 못했습니다. ipconfig로 직접 확인하십시오."
}

Write-Host ""
Write-Host "KB TradeGuard AI · Competition Demo" -ForegroundColor Cyan
Write-Host "PC와 휴대폰을 같은 Wi-Fi에 연결하십시오."
Write-Host "휴대폰 URL: http://${address}:$Port/?demo=1" -ForegroundColor Green
Write-Host "실제 고객자료나 API Key를 입력하지 마십시오. 합성 데모 전용입니다." -ForegroundColor Yellow
Write-Host "Windows 방화벽이 물으면 Private network에만 허용하십시오."
Write-Host ""

$env:TRADEGUARD_PUBLIC_DEMO_URL = "http://${address}:$Port/"

py -3.13 -m streamlit run competition_app.py `
    --server.address 0.0.0.0 `
    --server.port $Port `
    --server.headless true
