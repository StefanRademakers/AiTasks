#!/bin/zsh
set -euo pipefail

APP_DIR="${0:A:h}"
PYTHON="$APP_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "De virtual environment ontbreekt. Voer eerst setup.command uit."
    read -r "?Druk op Enter om dit venster te sluiten."
    exit 1
fi

export TK_SILENCE_DEPRECATION=1
nohup "$PYTHON" "$APP_DIR/task_creator.py" >/dev/null 2>&1 &
