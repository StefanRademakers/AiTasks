@echo off
setlocal
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

if not exist ".venv\Scripts\python.exe" (
    echo De virtual environment ontbreekt. Voer eerst setup.bat uit.
    pause
    exit /b 1
)

echo PyInstaller controleren...
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 (
    echo Installeren van de build-tools is mislukt.
    pause
    exit /b 1
)

echo Applicatie bouwen...
".venv\Scripts\python.exe" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "AI Task Creator" ^
    task_creator.py
if errorlevel 1 (
    echo Build mislukt.
    pause
    exit /b 1
)

echo.
echo Klaar: "%APP_DIR%dist\AI Task Creator.exe"
pause
