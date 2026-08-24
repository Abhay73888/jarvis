@echo off
REM ============================================================
REM  JARVIS installer (Windows) — creates venv, installs deps,
REM  writes default config, initializes the database.
REM ============================================================
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python not found. Install Python 3.12+ from python.org
    echo     and tick "Add Python to PATH" during setup.
    pause & exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv .venv || goto :fail
call .venv\Scripts\activate.bat

echo [2/4] Installing core dependencies...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q || goto :fail

echo [3/4] Installing Windows extras (voice/GUI/browser/vision)...
pip install -r requirements-windows.txt -q || (
    echo [!] Some optional extras failed - JARVIS core still works.
    echo     Re-run: pip install -r requirements-windows.txt
)

echo [4/4] Initializing configuration and database...
python run.py init || goto :fail

echo.
echo ============================================================
echo  Done. Next steps:
echo   1. copy .env.example to .env and add your API key(s)
echo   2. edit config\models.yaml to point at your provider
echo   3. start JARVIS:  run.bat
echo   4. check health:  run.bat doctor
echo ============================================================
pause & exit /b 0

:fail
echo [X] Installation failed - see messages above.
pause & exit /b 1
