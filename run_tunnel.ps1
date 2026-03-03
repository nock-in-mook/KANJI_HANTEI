# Step 2: Start Cloudflare Tunnel - THE URL FOR SMARTPHONE APPEARS HERE
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
$cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cmd) {
    Write-Host "cloudflared not found. Install: winget install Cloudflare.cloudflared" -ForegroundColor Red
    exit 1
}
Write-Host ">>> Open the URL below on your smartphone <<<" -ForegroundColor Yellow
cloudflared tunnel --url http://localhost:8501
