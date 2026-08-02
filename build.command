#!/bin/zsh
set -euo pipefail

APP_DIR="${0:A:h}"
cd "$APP_DIR"

PYTHON="$APP_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "De virtual environment ontbreekt. Voer eerst setup.command uit."
    read -r "?Druk op Enter om dit venster te sluiten."
    exit 1
fi

echo "PyInstaller controleren..."
"$PYTHON" -m pip install -r requirements-build.txt

echo "Applicatie bouwen..."
"$PYTHON" -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name "AI Task Creator" \
    task_creator.py

echo
echo "Klaar: $APP_DIR/dist/AI Task Creator.app"
read -r "?Druk op Enter om dit venster te sluiten."
