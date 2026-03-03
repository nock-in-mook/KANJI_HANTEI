# Clean reinstall - remove Paddle* completely, use EasyOCR only
$ErrorActionPreference = "Stop"
$venv = "$PSScriptRoot\.venv\Scripts\python.exe"

if (-not (Test-Path $venv)) {
    Write-Host "Creating venv..." -ForegroundColor Cyan
    py -3.10 -m venv "$PSScriptRoot\.venv"
}

Write-Host "Removing PaddleOCR/PaddleX (source of PDX error)..." -ForegroundColor Yellow
& $venv -m pip uninstall paddleocr paddlex paddlepaddle -y 2>$null

Write-Host "Installing EasyOCR + Streamlit..." -ForegroundColor Cyan
& $venv -m pip install easyocr streamlit Pillow --quiet

Write-Host ""
Write-Host "Verifying..." -ForegroundColor Cyan
& $venv "$PSScriptRoot\check_env.py"

Write-Host ""
Write-Host "Done. Run: .\run_simple.bat (PC only) or .\run.ps1 (with QR)" -ForegroundColor Green
