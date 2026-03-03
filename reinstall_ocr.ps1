# Reinstall PaddleOCR 2.7.3 in venv (fixes PDX initialization error)
$venv = "$PSScriptRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $venv)) {
    Write-Host "venv not found. Run: py -3.10 -m venv .venv" -ForegroundColor Red
    exit 1
}
Write-Host "Reinstalling PaddleOCR 2.7.3 in venv..." -ForegroundColor Cyan
& $venv -m pip uninstall paddleocr paddlex -y 2>$null
& $venv -m pip install paddlepaddle paddleocr==2.7.3 --quiet
Write-Host "Done. Run .\run.ps1" -ForegroundColor Green
