@echo off
cd /d "%~dp0"
where pythonw.exe >nul 2>&1
if errorlevel 1 (
    python gui.py
    if errorlevel 1 pause
) else (
    start "" pythonw.exe gui.py
)
