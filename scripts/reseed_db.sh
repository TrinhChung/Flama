#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

echo "[1/6] flask --app wsgi.py db upgrade"
flask --app wsgi.py db upgrade

echo "[2/6] flask --app wsgi.py dev-purge-data --yes"
flask --app wsgi.py dev-purge-data --yes

echo "[3/6] python scripts/seed_flama_template.py"
python scripts/seed_flama_template.py

echo "[4/6] flask --app wsgi.py user-role-seed"
flask --app wsgi.py user-role-seed

echo "[5/6] flask --app wsgi.py taxonomy-seed"
flask --app wsgi.py taxonomy-seed

echo "[6/6] flask --app wsgi.py vocab-seed --path static/seed_data --replace-lessons"
flask --app wsgi.py vocab-seed --path "static/seed_data" --replace-lessons

echo "Done reseed DB."
