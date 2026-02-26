#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
REQ_FILE="${REQ_FILE:-requirements.txt}"

usage() {
  cat <<'EOF'
Usage: bash scripts/setup_venv.sh

Environment variables:
  PYTHON_BIN  Python executable (default: python3)
  VENV_DIR    Virtualenv directory (default: .venv)
  REQ_FILE    Requirements file (default: requirements.txt)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -f "${REQ_FILE}" ]]; then
  echo "Requirements file not found: ${REQ_FILE}"
  echo "Run this script from the project root or set REQ_FILE."
  exit 1
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python executable '${PYTHON_BIN}' not found."
  exit 1
fi

"${PYTHON_BIN}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo "Python 3.10+ is required."
  exit 1
}

if [[ ! -d "${VENV_DIR}" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  echo "Created virtual environment: ${VENV_DIR}"
else
  echo "Virtual environment already exists: ${VENV_DIR}"
fi

# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip setuptools wheel
pip install -r "${REQ_FILE}"

if [[ ! -f ".env" && -f ".env_example" ]]; then
  cp .env_example .env
  echo "Created .env from .env_example"
fi

cat <<EOF
Setup complete.

Activate venv:
  source ${VENV_DIR}/bin/activate

Next commands (DB already running on your Ubuntu machine):
  flask --app wsgi.py db upgrade
  flask --app wsgi.py run --host=0.0.0.0 --port=5000
EOF
