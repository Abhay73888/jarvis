@echo off
REM JARVIS launcher (Windows)
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo JARVIS isn't installed yet - run install.bat first.
    pause & exit /b 1
)
call .venv\Scripts\activate.bat
if "%~1"=="doctor" (
    python run.py doctor
) else if "%~1"=="init" (
    python run.py init
) else (
    python run.py %*
)


