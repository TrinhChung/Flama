#!/usr/bin/env bash
set -Eeuo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script as root." >&2
  exit 1
fi

for command_name in mysql openssl python3; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
done

if ! id flama >/dev/null 2>&1; then
  useradd --system --home-dir /opt/flama --shell /usr/sbin/nologin flama
fi

install -d -m 0755 /opt/flama /opt/flama/releases
install -d -m 0750 -o root -g flama /etc/flama
install -d -m 0750 -o flama -g flama /var/lib/flama /var/lib/flama/media

environment_file=/etc/flama/flama.env
if [ ! -f "$environment_file" ]; then
  database_password="$(openssl rand -hex 32)"
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
FLASHCARDS_SHARE_CUTOVER_FAIL_ON_MISMATCH=0
PAYMENTS_ENABLED=0
PAYMENTS_PROVIDER=payos
PAYMENTS_PAID_INSTALL_REQUIRED=0
PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED=0
ENVIRONMENT
else
  database_password="$(sed -n 's/^DB_PASSWORD=//p' "$environment_file" | head -n 1)"
fi

if ! printf '%s' "$database_password" | grep -Eq '^[0-9a-f]{64}$'; then
  echo "DB_PASSWORD in $environment_file must be a 64-character hexadecimal value." >&2
  exit 1
fi

mysql --protocol=socket <<SQL
CREATE DATABASE IF NOT EXISTS flama CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'flama'@'127.0.0.1' IDENTIFIED BY '$database_password';
ALTER USER 'flama'@'127.0.0.1' IDENTIFIED BY '$database_password';
GRANT ALL PRIVILEGES ON flama.* TO 'flama'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL

echo "Hostinger native runtime prerequisites are ready."
