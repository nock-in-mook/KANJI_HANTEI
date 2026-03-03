"""Diagnostic: Which Python and packages are being used?"""
import sys
import os

print("=== Environment Check ===")
print("Python:", sys.executable)
print("")

if ".venv" in sys.executable.replace("\\", "/"):
    print("OK: Using VENV")
else:
    print("WARNING: Using GLOBAL Python - run via .\run_simple.bat or .\run.ps1")

print("")
for name in ["streamlit", "easyocr", "paddleocr", "paddlex"]:
    try:
        mod = __import__(name)
        p = getattr(mod, "__file__", "?")
        print(f"  {name}: {p}")
    except ImportError:
        print(f"  {name}: (not installed)")
