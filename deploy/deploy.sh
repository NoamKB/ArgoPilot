#!/usr/bin/env bash
# Brings this instance to the state of the checked-out commit: tools, dependencies, .env,
# systemd unit, restart, health check. The deploy workflow runs it as ubuntu after it checks
# out the commit. Every step first checks what already exists, so a clean instance and one
# deployed 20 times end in the same state.
set -euo pipefail

REPO_DIR=/home/ubuntu/ArgoPilot              # the unit files use these paths too
REGISTRY_DIR="$REPO_DIR/services/registry-service"
UV=/home/ubuntu/.local/bin/uv                # not on PATH in a non-interactive SSH session
UV_VERSION=0.13.9                            # the version already on the production instance

log() { printf '\n==> %s\n' "$*"; }

if [ "$(id -un)" != ubuntu ] || [ ! -d "$REPO_DIR/.git" ]; then
  echo "Run this as ubuntu, with the repository cloned to $REPO_DIR." >&2
  exit 1
fi

log "System packages"
# git is installed by the workflow, which needs it before this script exists on the instance.
missing=()
for cmd in curl sqlite3; do
  command -v "$cmd" >/dev/null || missing+=("$cmd")
done
if [ "${#missing[@]}" -gt 0 ]; then
  sudo apt-get update
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
else
  echo "curl and sqlite3 are installed."
fi

log "uv"
if [ ! -x "$UV" ]; then
  curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" | sh
fi
"$UV" --version

log "registry-service: dependencies"
cd "$REGISTRY_DIR"
"$UV" sync --locked

log "registry-service: database"
if [ -e registry.db ]; then
  echo "registry.db exists and was not changed."
else
  # Seed a temporary file and move it into place, so a failed seed never leaves a
  # half-written registry.db that the next run would treat as a real database.
  rm -f registry.db.new
  bash seed_registry.sh registry.db.new
  mv registry.db.new registry.db
fi

log "registry-service: .env"
# Written from scratch on every run, readable only by ubuntu.
# An empty DATABASE_URL means the SQLite file registry.db in this folder (config.py).
rm -f .env
(
  umask 077
  printf '%s\n' \
    '# Written by deploy/deploy.sh on every deploy. Do not edit it on the server.' \
    'DATABASE_URL=' > .env
)

log "registry-service: systemd unit"
sudo install -m 644 "$REPO_DIR/deploy/systemd/registry.service" /etc/systemd/system/registry.service
sudo systemctl daemon-reload
sudo systemctl enable registry.service
sudo systemctl restart registry.service

log "registry-service: health check"
# restart returns before the app is ready, and a crash on startup would still look like
# success. Retry until the app answers; /v1/crops also proves the database can be read.
check() {
  if ! curl -fsS --retry 20 --retry-delay 1 --retry-all-errors --max-time 5 -o /dev/null "$1"; then
    echo "Health check failed: $1" >&2
    sudo journalctl -u registry.service -n 30 --no-pager >&2
    exit 1
  fi
  echo "OK $1"
}
check http://127.0.0.1:8000/health
check http://127.0.0.1:8000/v1/crops

log "Deployed $(git -C "$REPO_DIR" log -1 --oneline)"
