#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

set_env_value() {
  local key="$1"
  local value="$2"
  local file="$3"
  if grep -q "^${key}=" "${file}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${file}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${file}"
  fi
}

if [[ ! -f "requirements.txt" || ! -f "docker-compose.yml" ]]; then
  echo "Please run this script from the project root."
  exit 1
fi

if [[ ! -f ".env" ]]; then
  cp .env_example .env
  echo "Created .env from .env_example"
fi

get_env_value() {
  local key="$1"
  local file="$2"
  local value
  value="$(grep -E "^${key}=" "${file}" | head -n 1 | cut -d '=' -f 2- || true)"
  printf '%s' "${value}"
}

CURRENT_DB_HOST="$(get_env_value "DB_HOST" ".env")"
CURRENT_DB_PORT="$(get_env_value "DB_PORT" ".env")"
CURRENT_DB_USER="$(get_env_value "DB_USER" ".env")"
CURRENT_DB_PASSWORD="$(get_env_value "DB_PASSWORD" ".env")"
CURRENT_DB_NAME="$(get_env_value "DB_NAME" ".env")"

DB_HOST="${DB_HOST:-${CURRENT_DB_HOST:-127.0.0.1}}"
DB_PORT="${DB_PORT:-${CURRENT_DB_PORT:-3306}}"
DB_USER="${DB_USER:-${CURRENT_DB_USER:-root}}"
DB_PASSWORD="${DB_PASSWORD:-${CURRENT_DB_PASSWORD:-your-db-password}}"
DB_NAME="${DB_NAME:-${CURRENT_DB_NAME:-flama}}"

if [[ ! "${DB_NAME}" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "DB_NAME must contain only letters, numbers, and underscores."
  exit 1
fi

set_env_value "DB_HOST" "${DB_HOST}" ".env"
set_env_value "DB_PORT" "${DB_PORT}" ".env"
set_env_value "DB_USER" "${DB_USER}" ".env"
set_env_value "DB_PASSWORD" "${DB_PASSWORD}" ".env"
set_env_value "DB_NAME" "${DB_NAME}" ".env"
set_env_value "USE_NEW_CARD_MODEL" "true" ".env"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required."
  exit 1
fi

docker compose up -d db

echo "Waiting for MySQL to be ready..."
for _ in $(seq 1 60); do
  if docker compose exec -T db mysqladmin ping -h127.0.0.1 -uroot -p"${DB_PASSWORD}" --silent >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! docker compose exec -T db mysqladmin ping -h127.0.0.1 -uroot -p"${DB_PASSWORD}" --silent >/dev/null 2>&1; then
  echo "MySQL did not become ready in time."
  exit 1
fi

docker compose exec -T db mysql -h127.0.0.1 -uroot -p"${DB_PASSWORD}" \
  -e "CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
echo "Database is ready: ${DB_NAME}"

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
fi

# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
pip install -r requirements.txt

cat <<'EOF'
Workspace setup complete.
Run app:
  source .venv/bin/activate
  flask --app wsgi.py db upgrade
  # Optional seed commands:
  # flask --app wsgi.py user-role-seed
  # flask --app wsgi.py vocab-seed --path "static/seed_data" --replace-lessons
  flask --app wsgi.py run --host=0.0.0.0 --port=5000
EOF
