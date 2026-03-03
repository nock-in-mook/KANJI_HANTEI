# KANJI_HANTEI - Streamlit + Cloudflare Tunnel (for smartphone access)

# Refresh PATH (winget installs may not appear until terminal restart)
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

$cloudflaredExe = $null
$cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($cmd) {
    $cloudflaredExe = $cmd.Source
} else {
    foreach ($dir in @("C:\Program Files\cloudflared", "C:\Program Files (x86)\cloudflared", "$env:LOCALAPPDATA\cloudflared")) {
        $exe = Join-Path $dir "cloudflared.exe"
        if (Test-Path $exe) { $cloudflaredExe = $exe; break }
    }
}
if (-not $cloudflaredExe) {
    Write-Host "cloudflared is not installed or not in PATH." -ForegroundColor Yellow
    Write-Host "Install: winget install Cloudflare.cloudflared" -ForegroundColor Cyan
    Write-Host "Then RESTART the terminal (close and reopen) and try again." -ForegroundColor Yellow
    exit 1
}

Write-Host "=== KANJI_HANTEI - Public URL ===" -ForegroundColor Green
Write-Host ""

$venvPath = Join-Path $PSScriptRoot ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "venv not found. Run setup first." -ForegroundColor Red
    exit 1
}

Write-Host "[1/2] Starting Streamlit..." -ForegroundColor Cyan
$streamlitProcess = Start-Process -FilePath $pythonExe -ArgumentList "-m streamlit run app.py --server.address 127.0.0.1 --server.port 8501" -WorkingDirectory $PSScriptRoot -PassThru -WindowStyle Normal

# Streamlitの起動を待つ
Start-Sleep -Seconds 6

Write-Host "[2/2] Starting Cloudflare Tunnel..." -ForegroundColor Cyan
Write-Host ""
Write-Host ">>> Open the URL below on your smartphone browser <<<" -ForegroundColor Yellow
Write-Host "    https://xxxxx.trycloudflare.com" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

try {
    & $cloudflaredExe tunnel --url http://localhost:8501
}
finally {
    $streamlitProcess | Stop-Process -Force -ErrorAction SilentlyContinue
}
