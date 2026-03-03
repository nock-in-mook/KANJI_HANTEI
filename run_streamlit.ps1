# Step 1: Start Streamlit (keep this window open)
$venvPath = Join-Path $PSScriptRoot ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
& $pythonExe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
