#!/usr/bin/env bash
set -Eeuo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script as root." >&2
  exit 1
fi

for command_name in mysql nginx openssl python3 redis-cli; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
done

headers_more_module="/etc/nginx/modules-enabled/50-mod-http-headers-more-filter.conf"
if [ ! -r "$headers_more_module" ]; then
  echo "Missing Nginx headers-more module." >&2
  echo "Install it with: apt-get install libnginx-mod-http-headers-more-filter" >&2
  exit 1
fi

if ! id flama >/dev/null 2>&1; then
  useradd --system --home-dir /opt/flama --shell /usr/sbin/nologin flama
fi

install -d -m 0755 /opt/flama /opt/flama/releases
install -d -m 0750 -o root -g flama /etc/flama
install -d -m 0755 -o flama -g flama /var/lib/flama /var/lib/flama/media /var/lib/flama/downloads

environment_file="${FLAMA_ENVIRONMENT_FILE:-/etc/flama/flama.env}"
if [ ! -f "$environment_file" ]; then
  database_password="${DB_PASSWORD:-$(openssl rand -hex 32)}"
  secret_key="$(openssl rand -hex 32)"

  install -m 0640 -o root -g flama /dev/null "$environment_file"
  cat > "$environment_file" <<ENVIRONMENT
FLASK_APP=wsgi.py
FLASK_ENV=production
SECRET_KEY=$secret_key
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=flama
DB_PASSWORD=$database_password
DB_NAME=flama
USE_NEW_CARD_MODEL=true
FLASHCARD_MEDIA_UPLOAD_ROOT=/var/lib/flama/media
FLASHCARD_MEDIA_MAX_BYTES=10485760
MEDIA_PROXY_USE_XACCEL=true
CONNECT_MAX_CONTENT_LENGTH=2097152
CONNECT_MEDIA_RATE_LIMIT=20
CONNECT_MEDIA_MAX_BYTES=1048576
CONNECT_PENDING_MEDIA_TTL_SECONDS=1800
CONNECT_PENDING_MEDIA_MAX_ITEMS=20
CONNECT_PENDING_MEDIA_MAX_TOTAL_BYTES=10485760
FLASHCARDS_SHARE_CUTOVER_FAIL_ON_MISMATCH=0
PAYMENTS_ENABLED=0
PAYMENTS_PROVIDER=payos
PAYMENTS_PAID_INSTALL_REQUIRED=0
PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED=1
PAYMENTS_ORDER_EXPIRY_SECONDS=1800
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS=1
REDIS_SOCKET_TIMEOUT_SECONDS=1
STUDY_QUEUE_NAMESPACE=flama-production
STUDY_ASYNC_BATCH_ENABLED=0
RATE_LIMIT_BACKEND=redis
RATE_LIMIT_KEY_PREFIX=flama:v1
RATE_LIMIT_DAILY_ENABLED=true
RATE_LIMIT_REGULAR_DAILY_MAX=300
RATE_LIMIT_CREATOR_DAILY_MAX=2000
RATE_LIMIT_ENTERPRISE_DAILY_MAX=10000
RATE_LIMIT_DAILY_TIMEZONE=Asia/Ho_Chi_Minh
LOGIN_RATE_LIMIT_ENABLED=true
LOGIN_RATE_LIMIT_WINDOW_SECONDS=60
LOGIN_RATE_LIMIT_MAX_ATTEMPTS=5
LOGIN_RATE_LIMIT_LOCKOUT_SECONDS=300
MCP_TOKEN_RATE_LIMIT_ENABLED=false
MCP_TOKEN_RATE_LIMIT_WINDOW_SECONDS=60
MCP_TOKEN_RATE_LIMIT_MAX_REQUESTS=100000
MCP_PREVIEW_BACKEND=redis
MCP_PREVIEW_TTL_SECONDS=600
SHARED_DECK_TREE_CLONE_MODE=batched
DECK_SOURCE_NOTETYPE_GUARD_MODE=shadow
MARKETPLACE_SAMPLE_MODE=shadow_cache
DB_POOL_SIZE=4
DB_MAX_OVERFLOW=1
DB_POOL_TIMEOUT_SECONDS=5
DB_POOL_RECYCLE_SECONDS=1800
REVIEW_ANALYTICS_WRITE_ENABLED=0
REVIEW_ANALYTICS_READ_MODE=raw
REVIEW_ANALYTICS_SHADOW_SAMPLE_RATE=0.01
DECK_COUNT_WRITE_ENABLED=0
DECK_COUNT_READ_MODE=raw
FORECAST_SUMMARY_READ_MODE=raw
FLASHCARD_RENDER_PREVIEW_CACHE_MAX_ENTRIES=512
ENVIRONMENT
fi

read_environment_value() {
  python3 - "$environment_file" "$1" <<'PYTHON'
import re
import shlex
import sys

environment_path, requested_key = sys.argv[1:]
assignment_pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")

with open(environment_path, encoding="utf-8") as handle:
    for raw_line in handle:
        match = assignment_pattern.match(raw_line.rstrip("\r\n"))
        if match is None or match.group(1) != requested_key:
            continue
        lexer = shlex.shlex(match.group(2), posix=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        values = list(lexer)
        if len(values) != 1:
            raise SystemExit(f"Invalid {requested_key} assignment in {environment_path}.")
        print(values[0], end="")
        break
    else:
        raise SystemExit(f"Missing {requested_key} in {environment_path}.")
PYTHON
}

if ! redis-cli -u "$(read_environment_value REDIS_URL 2>/dev/null || printf '%s' 'redis://127.0.0.1:6379/0')" ping \
  | grep -qx 'PONG'; then
  echo "Redis is not reachable; keep RATE_LIMIT_BACKEND/MCP_PREVIEW_BACKEND=local until fixed." >&2
  exit 1
fi

database_host="$(read_environment_value DB_HOST)"
database_user="$(read_environment_value DB_USER)"
database_password="$(read_environment_value DB_PASSWORD)"
database_name="$(read_environment_value DB_NAME)"

if ! printf '%s' "$database_host" | grep -Eq '^[A-Za-z0-9_.%-]+$'; then
  echo "DB_HOST in $environment_file contains unsupported characters." >&2
  exit 1
fi
if ! printf '%s' "$database_user" | grep -Eq '^[A-Za-z0-9_.%-]+$'; then
  echo "DB_USER in $environment_file contains unsupported characters." >&2
  exit 1
fi
if ! printf '%s' "$database_name" | grep -Eq '^[A-Za-z0-9_]+$'; then
  echo "DB_NAME in $environment_file contains unsupported characters." >&2
  exit 1
fi
if ! printf '%s' "$database_password" | grep -Eq '^[A-Za-z0-9._@%+=:,/-]{12,128}$'; then
  echo "DB_PASSWORD in $environment_file must be 12-128 safe printable characters." >&2
  exit 1
fi

mysql --protocol=socket <<SQL
CREATE DATABASE IF NOT EXISTS \`$database_name\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$database_user'@'$database_host' IDENTIFIED BY '$database_password';
ALTER USER '$database_user'@'$database_host' IDENTIFIED BY '$database_password';
GRANT ALL PRIVILEGES ON \`$database_name\`.* TO '$database_user'@'$database_host';
FLUSH PRIVILEGES;
SQL

echo "Hostinger native runtime prerequisites are ready."
