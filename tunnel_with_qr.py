"""
One-command launcher: Streamlit + Cloudflare Tunnel + QR code
Scan the QR code with your smartphone - no copy-paste needed.
"""
import subprocess
import sys
import re
import time
import os
import urllib.request
import urllib.parse

def show_qr_code(url):
    """Generate QR code via free API (no extra dependencies)."""
    try:
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(url)}"
        qr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qr_tunnel.png")
        urllib.request.urlretrieve(qr_url, qr_path)
        os.startfile(qr_path)
    except Exception as e:
        print("(QR generation failed - copy URL manually:", url, ")")

def main():
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(script_dir, ".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    # Start Streamlit
    print("Starting Streamlit...")
    streamlit = subprocess.Popen(
        [venv_python, "-m", "streamlit", "run", "app.py", "--server.address", "127.0.0.1", "--server.port", "8501"],
        cwd=script_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(5)

    # Start cloudflared and capture URL
    print("Starting Cloudflare Tunnel...")
    print("")
    tunnel_url = None
    proc = None

    # Find cloudflared (winget installs to WinGet\Links)
    cloudflared_exe = "cloudflared"
    for path in [
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe"),
        r"C:\Program Files\cloudflared\cloudflared.exe",
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
    ]:
        if os.path.exists(path):
            cloudflared_exe = path
            break

    cloudflared_cmd = f'"{cloudflared_exe}" tunnel --url http://localhost:8501'
    try:
        proc = subprocess.Popen(
            cloudflared_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in proc.stdout:
            print(line, end="")
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if match and not tunnel_url:
                tunnel_url = match.group(0)
                print("")
                print("=" * 50)
                print(">>> SCAN THIS QR CODE WITH YOUR SMARTPHONE <<<")
                print("=" * 50)
                show_qr_code(tunnel_url)
                print("")
                print("URL:", tunnel_url)
                print("(QR image opened - scan with smartphone camera)")
                print("=" * 50)
                print("")

    except FileNotFoundError:
        print("cloudflared not found. Install: winget install Cloudflare.cloudflared")
        print("Then restart the terminal.")
        streamlit.kill()
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    finally:
        streamlit.kill()
        if proc and proc.poll() is None:
            proc.kill()

if __name__ == "__main__":
    main()
