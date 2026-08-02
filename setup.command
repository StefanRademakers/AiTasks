#!/bin/zsh
set -euo pipefail

APP_DIR="${0:A:h}"
cd "$APP_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
    python3 -m venv .venv
fi

".venv/bin/python" -m pip install --upgrade pip
".venv/bin/python" -m pip install -r requirements.txt

echo
echo "Klaar. Start de app voortaan met start.command."
read -r "?Druk op Enter om dit venster te sluiten."
