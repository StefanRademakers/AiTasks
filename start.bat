@echo off
setlocal
set "APP_DIR=%~dp0"
if not exist "%APP_DIR%.venv\Scripts\pythonw.exe" (
    echo De virtual environment ontbreekt. Voer eerst setup.bat uit.
    pause
    exit /b 1
)
start "" "%APP_DIR%.venv\Scripts\pythonw.exe" "%APP_DIR%task_creator.py"
