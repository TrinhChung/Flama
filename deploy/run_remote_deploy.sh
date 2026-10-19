#!/usr/bin/env bash
# SSH only starts/observes the deployment; a disconnect cannot kill activation.
set -Eeuo pipefail
: "${SSH_HOST:?}" "${SSH_USER:?}" "${SSH_PORT:?}"
: "${PROJECT_DIR:?}" "${RELEASE_ID:?}" "${DEPLOYMENT_ID:?}"
[[ "$PROJECT_DIR" =~ ^/[A-Za-z0-9/_-]+$ ]]
[[ "$RELEASE_ID" =~ ^[a-f0-9]{40}$ ]]
[[ "$DEPLOYMENT_ID" =~ ^[a-f0-9-]+$ ]]
ssh_options=(-p "$SSH_PORT" -o BatchMode=yes -o ConnectTimeout=15
  -o ServerAliveInterval=15 -o ServerAliveCountMax=4)
remote="$SSH_USER@$SSH_HOST"
unit="flama-deploy-$DEPLOYMENT_ID"
script="/tmp/$unit.sh"

# Retrying the start is safe: the same systemd unit identifies this attempt.
started=0
for attempt in 1 2 3; do
  if ssh "${ssh_options[@]}" "$remote" "umask 077; cat > '$script.upload' && mv -f '$script.upload' '$script'" < deploy/activate_release.sh \
    && ssh "${ssh_options[@]}" "$remote" \
      "if systemctl cat '$unit.service' >/dev/null 2>&1; then exit 0; fi; systemd-run --quiet --unit='$unit' --property=Type=exec --property=RemainAfterExit=yes --property=StandardInput=null --property=StandardOutput=journal --property=StandardError=journal /bin/bash '$script' '$PROJECT_DIR' '$RELEASE_ID' '$DEPLOYMENT_ID'"; then
    started=1
    break
  fi
  echo "SSH start response unavailable; reconnecting to the same deployment ($attempt/3)."
  sleep 5
done
if [ "$started" -ne 1 ]; then
  echo "Could not confirm start. Inspect $unit on the VPS before retrying deployment." >&2
  exit 1
fi

for attempt in $(seq 1 180); do
  # The durable terminal state is authoritative; active/exited alone is not.
  if state=$(ssh "${ssh_options[@]}" "$remote" \
    "cat '$PROJECT_DIR/deployments/$DEPLOYMENT_ID.status' 2>/dev/null || true"); then
    echo "Deployment status: ${state:-starting}"
    case "$state" in
      succeeded\ *) exit 0 ;;
      failed\ *)
        ssh "${ssh_options[@]}" "$remote" "journalctl -u '$unit' -n 100 --no-pager" || true
        exit 1 ;;
    esac
    # A killed coordinator cannot write a terminal state. Detect it explicitly.
    if result=$(ssh "${ssh_options[@]}" "$remote" \
      "systemctl show '$unit' --property=ActiveState --value"); then
      case "$result" in
        failed|inactive)
          echo "Coordinator stopped without success. Inspect journalctl -u $unit on the VPS." >&2
          exit 1 ;;
      esac
    fi
  else
    echo "SSH observation interrupted; deployment continues on the VPS. Reconnecting."
  fi
  sleep 10
done
echo "Observation timed out; the VPS deployment continues. Inspect $unit and its status before starting another attempt." >&2
exit 1
