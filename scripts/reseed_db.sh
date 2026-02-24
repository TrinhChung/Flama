#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

echo "[1/4] flask --app wsgi.py db upgrade"
flask --app wsgi.py db upgrade

echo "[2/4] python scripts/seed_flama_template.py"
python scripts/seed_flama_template.py

echo "[3/4] flask --app wsgi.py user-role-seed"
flask --app wsgi.py user-role-seed

echo "[4/4] flask --app wsgi.py vocab-seed --path static/seed_data --replace-lessons"
flask --app wsgi.py vocab-seed --path "static/seed_data" --replace-lessons

echo "Done reseed DB."
