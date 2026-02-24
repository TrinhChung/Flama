#!/usr/bin/env bash
set -euo pipefail

MODE="local"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

usage() {
  cat <<'EOF'
Usage: bash scripts/setup_new_device.sh [--mode local|docker]

Options:
  --mode local   Setup Python environment for local run (default)
  --mode docker  Setup .env and start Docker services
  -h, --help     Show this help

Environment variables:
  PYTHON_BIN  Python executable to use (default: python3)
  VENV_DIR    Virtualenv directory (default: .venv)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "requirements.txt" || ! -f ".env_example" ]]; then
  echo "Please run this script from the project root."
  exit 1
fi

if [[ ! -f ".env" ]]; then
  cp .env_example .env
  echo "Created .env from .env_example"
else
  echo ".env already exists, skipped copy."
fi

if [[ "${MODE}" == "local" ]]; then
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
  python -m pip install --upgrade pip
  pip install -r requirements.txt

  cat <<'EOF'
Local environment is ready.
Next:
  1) Edit .env with your MySQL credentials.
  2) Ensure DB exists (DB_NAME in .env).
  3) Run migration: flask --app wsgi.py db upgrade
  4) Start app: flask --app wsgi.py run
EOF
  exit 0
fi

if [[ "${MODE}" == "docker" ]]; then
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    docker compose up --build -d
    cat <<'EOF'
Docker services started.
App: http://127.0.0.1:5000
If needed, run migrations inside container:
  docker compose exec web flask --app wsgi.py db upgrade
EOF
    exit 0
  fi

  echo "Docker Compose not found. Install Docker Desktop / docker compose plugin first."
  exit 1
fi

echo "Invalid mode: ${MODE}. Use --mode local or --mode docker."
exit 1
