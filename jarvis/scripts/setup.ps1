# JARVIS dev/bootstrap helper (PowerShell, optional)
# The .bat installer is the primary path; this is for PowerShell-first users.
param([switch]$SkipWindowsExtras)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

python --version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Python 3.12+ required (not on PATH)." }

python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip -q
& .\.venv\Scripts\pip.exe install -r requirements.txt -q
if (-not $SkipWindowsExtras) {
    & .\.venv\Scripts\pip.exe install -r requirements-windows.txt -q
    & .\.venv\Scripts\python.exe -m playwright install chromium 2>$null
}
& .\.venv\Scripts\python.exe run.py init
Write-Host "Ready. Activate with .\.venv\Scripts\Activate.ps1 and run: python run.py"
