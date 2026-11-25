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

PG_CONTAINER=agropilot-pg

log() { printf '\n==> %s\n' "$*"; }

if [ "$(id -un)" != ubuntu ] || [ ! -d "$REPO_DIR/.git" ]; then
  echo "Run this as ubuntu, with the repository cloned to $REPO_DIR." >&2
  exit 1
fi

# The database password comes from the POSTGRES_PASSWORD Actions secret. Hex only, so it can go
# into DATABASE_URL without percent-encoding. The value is never printed.
if ! [[ "${POSTGRES_PASSWORD:-}" =~ ^[0-9a-f]{32,}$ ]]; then
  echo "POSTGRES_PASSWORD must be set to at least 32 lowercase hex characters (openssl rand -hex 24)." >&2
  exit 1
fi

log "System packages"
# git is installed by the workflow, which needs it before this script exists on the instance.
missing=()
command -v curl >/dev/null || missing+=(curl)
command -v docker >/dev/null || missing+=(docker.io)
if [ "${#missing[@]}" -gt 0 ]; then
  sudo apt-get update
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
else
  echo "curl and docker are installed."
fi
sudo systemctl enable --now docker.service

log "uv"
if [ ! -x "$UV" ]; then
  curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" | sh
fi
"$UV" --version

log "PostgreSQL"
# Created once; later runs only make sure it is running. The data lives in the named volume,
# so it survives a restart or a re-creation of the container. POSTGRES_PASSWORD only takes
# effect when the volume is first initialised.
if sudo docker container inspect "$PG_CONTAINER" >/dev/null 2>&1; then
  sudo docker start "$PG_CONTAINER" >/dev/null
  echo "$PG_CONTAINER exists and is running."
else
  # --preserve-env passes the password through sudo without putting it on the command line.
  sudo --preserve-env=POSTGRES_PASSWORD docker run -d --name "$PG_CONTAINER" \
    --restart unless-stopped \
    -e POSTGRES_PASSWORD -e POSTGRES_DB=registry \
    -v agropilot-pg-data:/var/lib/postgresql/data \
    -p 127.0.0.1:5436:5432 \
    postgres:17
fi
# Ask over TCP: during first initialisation the image runs a temporary server on the Unix
# socket only, which would look ready before the real server has started.
for _ in $(seq 1 30); do
  sudo docker exec "$PG_CONTAINER" pg_isready -h 127.0.0.1 -U postgres -d registry -q && break
  sleep 1
done
sudo docker exec "$PG_CONTAINER" pg_isready -h 127.0.0.1 -U postgres -d registry

log "registry-service: dependencies"
cd "$REGISTRY_DIR"
"$UV" sync --locked

log "registry-service: .env"
# Written from scratch on every run, readable only by ubuntu.
rm -f .env
(
  umask 077
  printf '%s\n' \
    '# Written by deploy/deploy.sh on every deploy. Do not edit it on the server.' \
    "DATABASE_URL=postgresql+psycopg://postgres:${POSTGRES_PASSWORD}@127.0.0.1:5436/registry" > .env
)

log "registry-service: database"
# Creates any missing tables and catalogue rows; never changes or deletes existing rows.
.venv/bin/python -m scripts.setup_postgres
# The demo farms and plots go in only on an empty database, so a later deploy never brings
# back demo rows that were deleted in production.
farms=$(sudo docker exec "$PG_CONTAINER" psql -U postgres -d registry -tAc 'SELECT count(*) FROM farms')
if [ "$farms" = 0 ]; then
  .venv/bin/python -m scripts.setup_postgres --demo
else
  echo "$farms farms exist; demo data not loaded."
fi
# registry.db (the old SQLite database) is left untouched as a backup.

for service in weather-service planner-service; do
  log "$service: dependencies and .env"
  cd "$REPO_DIR/services/$service"
  "$UV" sync --locked
  # The example values are the production values (127.0.0.1 URLs, no secrets).
  # A fresh copy on every run, readable only by ubuntu.
  rm -f .env
  (umask 077; cp .env.example .env)
done

log "frontend: Node.js"
# Node 24, the major version used locally (.nvmrc). Ubuntu's own nodejs is 22 with npm 9, so it
# comes from NodeSource's apt repository; apt checks every package against NodeSource's signing key.
if ! node --version 2>/dev/null | grep -q '^v24\.'; then
  sudo install -d -m 755 /etc/apt/keyrings
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | sudo tee /etc/apt/keyrings/nodesource.asc >/dev/null
  printf '%s\n' \
    'Types: deb' \
    'URIs: https://deb.nodesource.com/node_24.x' \
    'Suites: nodistro' \
    'Components: main' \
    'Signed-By: /etc/apt/keyrings/nodesource.asc' \
    | sudo tee /etc/apt/sources.list.d/nodesource.sources >/dev/null
  sudo apt-get update
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
fi
echo "node $(node --version), npm $(npm --version)"
if ! node --version | grep -q '^v24\.'; then
  echo "Expected Node 24 after the install." >&2
  exit 1
fi

log "frontend: dependencies, .env.local, build"
cd "$REPO_DIR/services/frontend"
# The example values are the production values (127.0.0.1 URLs, no secrets).
rm -f .env.local
(umask 077; cp .env.example .env.local)
npm ci            # exactly the versions in package-lock.json, into a fresh node_modules
npm run build     # the new build is served from the restart below

log "systemd units"
# In dependency order: planner calls registry and weather; frontend calls all three.
UNITS=(registry weather planner frontend)
for unit in "${UNITS[@]}"; do
  sudo install -m 644 "$REPO_DIR/deploy/systemd/$unit.service" "/etc/systemd/system/$unit.service"
done
sudo systemctl daemon-reload
for unit in "${UNITS[@]}"; do
  sudo systemctl enable "$unit.service"
  sudo systemctl restart "$unit.service"
done

log "Health checks"
# restart returns before an app is ready, and a crash on startup would still look like
# success. Retry until each app answers; on failure, print that unit's log.
check() {
  local unit=$1 url=$2
  if ! curl -fsS --retry 20 --retry-delay 1 --retry-all-errors --max-time 5 -o /dev/null "$url"; then
    echo "Health check failed: $url" >&2
    sudo journalctl -u "$unit.service" -n 30 --no-pager >&2
    exit 1
  fi
  echo "OK $url"
}
check registry http://127.0.0.1:8000/health
check registry http://127.0.0.1:8000/v1/crops   # also proves the database can be read
# weather and planner refuse to start without a valid .env, so /health also proves the config.
check weather http://127.0.0.1:8001/health
check planner http://127.0.0.1:8002/health
check frontend http://127.0.0.1:3000/

log "Deployed $(git -C "$REPO_DIR" log -1 --oneline)"
