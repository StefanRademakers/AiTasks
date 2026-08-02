@echo off
setlocal
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
echo.
echo Klaar. Start de app voortaan met start.bat.
pause
