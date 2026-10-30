#!/usr/bin/env bash
# The entire activation runs under systemd, with journal-backed stdio.
set -Eeuo pipefail
PROJECT_DIR=${1:?project directory required}
RELEASE_ID=${2:?release SHA required}
DEPLOYMENT_ID=${3:?deployment ID required}
[[ "$PROJECT_DIR" =~ ^/[A-Za-z0-9/_-]+$ ]]
[[ "$RELEASE_ID" =~ ^[a-f0-9]{40}$ ]]
[[ "$DEPLOYMENT_ID" =~ ^[a-f0-9-]+$ ]]
install -d -m 0755 "$PROJECT_DIR"
exec 9>"$PROJECT_DIR/deploy.lock"
flock -n 9 || { echo "Another deployment owns the server lock." >&2; exit 1; }
install -d -m 0700 "$PROJECT_DIR/deployments"
state_file="$PROJECT_DIR/deployments/$DEPLOYMENT_ID.status"
phase=preparing
record_state() {
  printf '%s %s\n' "$1" "$phase" > "$state_file.tmp"
  mv -f "$state_file.tmp" "$state_file"
  echo "Deployment $DEPLOYMENT_ID: $1 ($phase)"
}
record_state running

release_dir="$PROJECT_DIR/releases/$RELEASE_ID"
archive_path="/tmp/flama-$RELEASE_ID.tar.gz"
environment_file=/etc/flama/flama.env
desired_environment_file="/etc/flama/.flama.env.$RELEASE_ID"
environment_backup_file="/etc/flama/.flama.env.rollback.$RELEASE_ID"
managed_env_payload_path="/tmp/flama-$RELEASE_ID.env.json"
previous_release=""
activation_started=0
deployment_succeeded=0
previous_analytics_timer_enabled=0
previous_review_timer_enabled=0
previous_note_retention_timer_enabled=0
previous_study_retention_timer_enabled=0
runtime_venv=""
previous_venv=""
venv_switched=0
if systemctl is-enabled --quiet flama-analytics-counts.timer; then
  previous_analytics_timer_enabled=1
fi
if systemctl is-enabled --quiet flama-review-analytics-worker.timer; then
  previous_review_timer_enabled=1
fi
if systemctl is-enabled --quiet flama-note-base-retention.timer; then
  previous_note_retention_timer_enabled=1
fi
if systemctl is-enabled --quiet flama-study-retention.timer; then
  previous_study_retention_timer_enabled=1
fi

rollback_activation() {
  if [ "$activation_started" -ne 1 ] || [ "$deployment_succeeded" -eq 1 ]; then
    return
  fi

  echo "Deployment failed after activation; restoring the previous release." >&2
  # Quiesce request writers before inspecting durable state. Leave the
  # new consumer/environment/release intact if rollback is unsafe, so
  # accepted work can drain and an operator can audit/rollback NOTE.
  if ! systemctl stop flama.service flama-connect.service; then
    echo "Automatic rollback blocked: HTTP/Connect writers did not stop." >&2
    return
  fi
  if systemctl cat flama-study-retention.timer >/dev/null 2>&1; then
    if ! systemctl stop flama-study-retention.timer flama-study-retention.service; then
      echo "Automatic rollback blocked: Study retention writer did not stop." >&2
      return
    fi
  fi
  systemctl stop flama-analytics-counts.timer flama-analytics-counts.service || true
  systemctl stop flama-review-analytics-worker.timer flama-review-analytics-worker.service || true
  if systemctl cat flama-note-base-retention.service >/dev/null 2>&1; then
    if ! systemctl stop flama-note-base-retention.timer flama-note-base-retention.service; then
      echo "Automatic rollback blocked: Published Base retention did not stop." >&2
      return
    fi
  fi
  if ! systemd-run --quiet --wait --collect \
    --unit="flama-study-rollback-check-$RELEASE_ID" \
    --property=User=flama \
    --property=Group=flama \
    --property="WorkingDirectory=$release_dir" \
    --property="EnvironmentFile=$environment_file" \
    "$PROJECT_DIR/venv/bin/python" study_worker.py --check-code-rollback --writers-quiesced; then
    echo "Automatic rollback blocked: retain this release/consumer and resolve the reported Study gate before restoring code." >&2
    return
  fi
  if ! systemctl stop flama-study-worker.service; then
    echo "Automatic rollback blocked: the Study consumer did not stop." >&2
    return
  fi
  if [ -f "$release_dir/deploy/flama-review-analytics-worker.service" ]; then
    if ! systemd-run --quiet --wait --collect \
      --unit="flama-history-rollback-check-$RELEASE_ID" \
      --property=User=flama --property=Group=flama \
      --property="WorkingDirectory=$release_dir" \
      --property="EnvironmentFile=$environment_file" \
      "$PROJECT_DIR/venv/bin/flask" --app wsgi.py review-analytics-rollback-check --writers-quiesced; then
      echo "Automatic rollback blocked: drain committed history revisions with this release before restoring old code." >&2
      return
    fi
  fi
  if [ -f "$release_dir/deploy/check_field_code_rollback.py" ]; then
    if ! systemd-run --quiet --wait --collect \
      --unit="flama-field-code-rollback-$RELEASE_ID" \
      --property=User=flama --property=Group=flama \
      --property="WorkingDirectory=$release_dir" \
      --property="EnvironmentFile=$environment_file" \
      "$PROJECT_DIR/venv/bin/python" "$release_dir/deploy/check_field_code_rollback.py" \
        --writers-quiesced --previous-release "$previous_release"; then
      echo "Automatic rollback blocked: contracted Field ID storage requires compatible code or an isolated backup restore." >&2
      return
    fi
  fi
  if [ -f "$environment_backup_file" ]; then
    cp -p "$environment_backup_file" "$environment_file"
  fi

  if [ -n "$previous_release" ] && [ -d "$previous_release" ]; then
    previous_connect_available=0
    previous_worker_available=0
    if [ -f "$previous_release/deploy/flama.service" ]; then
      install -m 0644 \
        "$previous_release/deploy/flama.service" \
        /etc/systemd/system/flama.service
    fi
    if [ -f "$previous_release/deploy/flama-connect.service" ]; then
      install -m 0644 \
        "$previous_release/deploy/flama-connect.service" \
        /etc/systemd/system/flama-connect.service
      previous_connect_available=1
    fi
    if [ -f "$previous_release/deploy/flama-study-worker.service" ]; then
      install -m 0644 \
        "$previous_release/deploy/flama-study-worker.service" \
        /etc/systemd/system/flama-study-worker.service
      previous_worker_available=1
    fi
    if [ -f "$previous_release/deploy/flama-analytics-counts.service" ] && [ -f "$previous_release/deploy/flama-analytics-counts.timer" ]; then
      install -m 0644 "$previous_release/deploy/flama-analytics-counts.service" /etc/systemd/system/flama-analytics-counts.service
      install -m 0644 "$previous_release/deploy/flama-analytics-counts.timer" /etc/systemd/system/flama-analytics-counts.timer
    fi
    if [ -f "$previous_release/deploy/flama-review-analytics-worker.service" ] && [ -f "$previous_release/deploy/flama-review-analytics-worker.timer" ]; then
      install -m 0644 "$previous_release/deploy/flama-review-analytics-worker.service" /etc/systemd/system/flama-review-analytics-worker.service
      install -m 0644 "$previous_release/deploy/flama-review-analytics-worker.timer" /etc/systemd/system/flama-review-analytics-worker.timer
    fi
    if [ -f "$previous_release/deploy/flama-note-base-retention.service" ] && [ -f "$previous_release/deploy/flama-note-base-retention.timer" ]; then
      install -m 0644 "$previous_release/deploy/flama-note-base-retention.service" /etc/systemd/system/flama-note-base-retention.service
      install -m 0644 "$previous_release/deploy/flama-note-base-retention.timer" /etc/systemd/system/flama-note-base-retention.timer
    fi
    if [ "${venv_switched:-0}" -eq 1 ]; then
      ln -sfn "$previous_venv" "$PROJECT_DIR/venv"
    fi
    ln -sfn "$previous_release" "$PROJECT_DIR/current"
    systemctl daemon-reload || true
    if [ "${previous_analytics_timer_enabled:-0}" -eq 1 ] && [ -f "$previous_release/deploy/flama-analytics-counts.timer" ]; then
      systemctl enable --now flama-analytics-counts.timer || true
    else
      systemctl disable flama-analytics-counts.timer || true
    fi
    if [ "${previous_review_timer_enabled:-0}" -eq 1 ] && [ -f "$previous_release/deploy/flama-review-analytics-worker.timer" ]; then
      systemctl enable --now flama-review-analytics-worker.timer || true
    else
      systemctl disable flama-review-analytics-worker.timer || true
    fi
    if [ "${previous_note_retention_timer_enabled:-0}" -eq 1 ] && [ -f "$previous_release/deploy/flama-note-base-retention.timer" ]; then
      systemctl enable --now flama-note-base-retention.timer || true
    else
      systemctl disable flama-note-base-retention.timer || true
    fi
    if [ "${previous_study_retention_timer_enabled:-0}" -eq 1 ]; then
      systemctl enable --now flama-study-retention.timer || true
    fi
    if [ "$previous_worker_available" -eq 1 ]; then
      systemctl restart flama-study-worker.service || true
    else
      systemctl disable flama-study-worker.service || true
    fi
    systemctl restart flama.service || true
    if [ "$previous_connect_available" -eq 1 ]; then
      systemctl restart flama-connect.service || true
    else
      systemctl stop flama-connect.service || true
    fi

    for attempt in $(seq 1 10); do
      if curl --fail --silent --show-error --max-time 5 \
        http://127.0.0.1:4789/api/health >/dev/null \
        && { [ "$previous_connect_available" -eq 0 ] \
          || curl --fail --silent --show-error --max-time 5 \
            http://127.0.0.1:4790/healthz >/dev/null; }; then
        echo "Previous release restored: $previous_release" >&2
        return
      fi
      sleep 2
    done

    echo "Previous release was selected but did not become healthy." >&2
    return
  fi

  systemctl stop flama.service || true
  systemctl stop flama-connect.service || true
  systemctl disable flama-study-worker.service || true
  systemctl disable flama-analytics-counts.timer || true
  systemctl disable flama-review-analytics-worker.timer || true
  systemctl disable flama-note-base-retention.timer || true
  echo "No previous release was available; stopped flama.service." >&2
}

# Units only use $PROJECT_DIR/venv, so changing interpreter is a link switch
# made while writers are stopped. Rollback points the link back.
switch_runtime_venv() {
  if [ -L "$PROJECT_DIR/venv" ]; then
    previous_venv="$(readlink -f "$PROJECT_DIR/venv")"
  elif [ -d "$PROJECT_DIR/venv" ]; then
    # A host from before per-interpreter venvs keeps its directory for rollback.
    mv -T "$PROJECT_DIR/venv" "$PROJECT_DIR/venv-legacy"
    previous_venv="$PROJECT_DIR/venv-legacy"
  fi
  if [ "$previous_venv" != "$runtime_venv" ]; then
    # Marked before linking, so rollback also undoes a half-made switch.
    if [ -n "$previous_venv" ]; then
      venv_switched=1
    fi
    ln -sfn "$runtime_venv" "$PROJECT_DIR/venv"
  fi
}

# Every second the review timer starts its ExecCondition, about 80k Python
# processes a day while the writer is off. Disable it only when the active
# environment says off; a failed check keeps it enabled behind ExecCondition.
sync_review_analytics_timer() {
  if systemd-run --quiet --wait --collect \
    --unit="flama-review-analytics-gate-$RELEASE_ID" \
    --property=User=flama \
    --property=Group=flama \
    --property="EnvironmentFile=$environment_file" \
    "$PROJECT_DIR/venv/bin/python" -c "import os; raise SystemExit(1 if os.getenv('REVIEW_ANALYTICS_WRITE_ENABLED', '').strip().lower() in {'1', 'true', 'yes', 'on'} else 0)"; then
    systemctl disable flama-review-analytics-worker.timer
  else
    systemctl enable --now flama-review-analytics-worker.timer
  fi
}

cleanup() {
  status=$?
  trap - EXIT
  if [ "$status" -ne 0 ]; then
    # Preserve payload/env backups and the failure phase for operator recovery.
    # Keep errexit inside rollback: wrapping a function in `if`/`||` would
    # silently disable it for every command in the function.
    set +e
    ( set -e; rollback_activation )
    rollback_status=$?
    set -e
    if [ "$rollback_status" -ne 0 ]; then
      echo "Rollback did not complete; inspect the deployment journal." >&2
    fi
    record_state failed
  else
    record_state succeeded
    rm -f "$archive_path" "$managed_env_payload_path" \
      "$desired_environment_file" "$environment_backup_file"
  fi
  exit "$status"
}
trap cleanup EXIT

# A killed coordinator can leave its separate migration unit running. Never
# start another migration over that child, even after the shell lock is freed.
pending_migrations=$(systemctl list-units --plain --no-legend \
  --state=active,activating 'flama-db-migrate-*.service')
if [ -n "$pending_migrations" ]; then
  echo "A previous database migration is still active; inspect its journal before retrying." >&2
  exit 1
fi

test -f "$environment_file"
test -f "$managed_env_payload_path"
mkdir -p "$release_dir"
tar -xzf "$archive_path" -C "$release_dir"
# CI tests the interpreter named here; the release must run on the same one.
python_version="$(tr -d '[:space:]' < "$release_dir/.python-version")"
[[ "$python_version" =~ ^3\.[0-9]+$ ]]
runtime_python="python$python_version"
if ! command -v "$runtime_python" >/dev/null 2>&1; then
  echo "Missing $runtime_python required by .python-version." >&2
  echo "Install it with: add-apt-repository ppa:deadsnakes/ppa && apt-get install $runtime_python $runtime_python-venv $runtime_python-dev" >&2
  exit 1
fi
cp -p "$environment_file" "$desired_environment_file"
"$runtime_python" "$release_dir/deploy/sync_managed_env.py" apply \
  --env-file "$desired_environment_file" \
  --payload-file "$managed_env_payload_path"
FLAMA_ENVIRONMENT_FILE="$desired_environment_file" \
  bash "$release_dir/deploy/bootstrap_hostinger.sh"

mkdir -p /var/lib/flama/downloads
mkdir -p "$release_dir/static"
ln -sfn /var/lib/flama/downloads "$release_dir/static/downloads"
chown -R flama:flama /var/lib/flama/downloads

# A new interpreter gets its own venv, built while the old one still serves.
runtime_venv="$PROJECT_DIR/venv-$python_version"
if [ ! -x "$runtime_venv/bin/python" ]; then
  "$runtime_python" -m venv "$runtime_venv"
fi

"$runtime_venv/bin/pip" install --disable-pip-version-check -r "$release_dir/requirements.txt"
previous_release="$(readlink -f "$PROJECT_DIR/current" 2>/dev/null || true)"
case "$previous_release" in
  "$PROJECT_DIR"/releases/*) test -d "$previous_release" || previous_release="" ;;
  *) previous_release="" ;;
esac
cp -p "$environment_file" "$environment_backup_file"
# Field contraction is an explicit maintenance boundary. No old
# process may continue writing name-key values while rows are mapped.
phase=quiescing
record_state running
activation_started=1
for unit in flama.service flama-connect.service flama-study-worker.service \
  flama-analytics-counts.timer flama-analytics-counts.service \
  flama-review-analytics-worker.timer flama-review-analytics-worker.service \
  flama-note-base-retention.timer flama-note-base-retention.service \
  flama-study-retention.timer flama-study-retention.service; do
  # A first deployment has no application units yet. A loaded unit
  # must stop successfully; never acknowledge quiescence on failure.
  if systemctl cat "$unit" >/dev/null 2>&1; then
    systemctl stop "$unit"
  fi
done
switch_runtime_venv
phase=migrating
record_state running
systemd-run --quiet --wait --collect \
  --unit="flama-db-migrate-$RELEASE_ID" \
  --property=User=flama \
  --property=Group=flama \
  --property="WorkingDirectory=$release_dir" \
  --property="EnvironmentFile=$desired_environment_file" \
  --property='Environment=STARTUP_RUN_MAINTENANCE=0 STARTUP_RUN_DB_CREATE_ALL=0 STARTUP_RUN_CLONE_CUTOVER=0' \
  "$PROJECT_DIR/venv/bin/python" "$release_dir/deploy/migrate_database.py" --writers-quiesced
phase=activating
record_state running
systemd-run --quiet --wait --collect \
  --unit="flama-bootstrap-admin-$RELEASE_ID" \
  --property=User=flama \
  --property=Group=flama \
  --property="WorkingDirectory=$release_dir" \
  --property="EnvironmentFile=$desired_environment_file" \
  "$PROJECT_DIR/venv/bin/flask" --app wsgi.py bootstrap-admin-sync
install -m 0644 "$release_dir/deploy/flama.service" /etc/systemd/system/flama.service
install -m 0644 "$release_dir/deploy/flama-connect.service" /etc/systemd/system/flama-connect.service
install -m 0644 "$release_dir/deploy/flama-study-worker.service" /etc/systemd/system/flama-study-worker.service
install -m 0644 "$release_dir/deploy/flama-analytics-counts.service" /etc/systemd/system/flama-analytics-counts.service
install -m 0644 "$release_dir/deploy/flama-analytics-counts.timer" /etc/systemd/system/flama-analytics-counts.timer
install -m 0644 "$release_dir/deploy/flama-review-analytics-worker.service" /etc/systemd/system/flama-review-analytics-worker.service
install -m 0644 "$release_dir/deploy/flama-review-analytics-worker.timer" /etc/systemd/system/flama-review-analytics-worker.timer
install -m 0644 "$release_dir/deploy/flama-note-base-retention.service" /etc/systemd/system/flama-note-base-retention.service
install -m 0644 "$release_dir/deploy/flama-note-base-retention.timer" /etc/systemd/system/flama-note-base-retention.timer

cp -p "$environment_file" /etc/flama/flama.env.bak
# Stop the previous consumer under its original environment before
# changing the symlink/namespace; DB admissions survive the handoff.
systemctl daemon-reload
systemctl stop flama-study-worker.service
systemctl stop flama-analytics-counts.timer flama-analytics-counts.service || true
systemctl stop flama-review-analytics-worker.timer flama-review-analytics-worker.service || true
systemctl stop flama-note-base-retention.timer flama-note-base-retention.service
activation_started=1
mv -f "$desired_environment_file" "$environment_file"
ln -sfn "$release_dir" "$PROJECT_DIR/current"

systemctl daemon-reload
systemctl enable flama.service
systemctl enable flama-connect.service
systemctl enable flama-study-worker.service
systemctl restart flama-study-worker.service
systemctl restart flama.service
systemctl restart flama-connect.service
# The oneshot ExecCondition skips disabled/unconfigured writers;
# readers stay independently gated until parity/latency qualification.
systemctl enable --now flama-analytics-counts.timer
sync_review_analytics_timer
systemctl enable --now flama-note-base-retention.timer

phase=health
record_state running
for attempt in $(seq 1 20); do
  if curl --fail --silent --show-error --max-time 5 \
    http://127.0.0.1:4789/api/health >/dev/null \
    && curl --fail --silent --show-error --max-time 5 \
    http://127.0.0.1:4790/healthz >/dev/null \
    && systemctl is-active --quiet flama-study-worker.service \
    && systemd-run --quiet --wait --collect \
      --unit="flama-study-ready-$RELEASE_ID-$attempt" \
      --property=User=flama \
      --property=Group=flama \
      --property="WorkingDirectory=$release_dir" \
      --property="EnvironmentFile=$environment_file" \
      "$PROJECT_DIR/venv/bin/python" study_worker.py --check-ready; then
    touch "$release_dir/.deployment_succeeded"
    deployment_succeeded=1
    # This older, separately approved maintenance job is not enabled by deploy.
    # Resume it only when the operator had already enabled it before quiescence.
    if [ "$previous_study_retention_timer_enabled" -eq 1 ]; then
      systemctl enable --now flama-study-retention.timer
    fi
    "$runtime_python" "$release_dir/deploy/prune_releases.py" \
      --releases-dir "$PROJECT_DIR/releases" \
      --current-release "$release_dir" \
      --keep 2 || echo "Warning: failed to prune old releases." >&2
    systemctl --no-pager --full status flama.service || true
    systemctl --no-pager --full status flama-connect.service || true
    systemctl --no-pager --full status flama-study-worker.service || true
    exit 0
  fi
  sleep 3
done

systemctl --no-pager --full status flama.service || true
systemctl --no-pager --full status flama-connect.service || true
systemctl --no-pager --full status flama-study-worker.service || true
journalctl -u flama.service -n 100 --no-pager || true
journalctl -u flama-connect.service -n 100 --no-pager || true
journalctl -u flama-study-worker.service -n 100 --no-pager || true
exit 1
