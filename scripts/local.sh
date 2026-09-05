#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
units=(interviewer-api interviewer-worker interviewer-beat interviewer-frontend)

case "${1:-start}" in
  stop)
    for unit in "${units[@]}"; do systemctl --user stop "$unit" || true; done
    docker compose -f compose.local.yml stop
    exit
    ;;
  status)
    docker compose -f compose.local.yml ps
    systemctl --user --no-pager --full status "${units[@]}"
    exit
    ;;
  start) ;;
  *) echo 'Usage: bash scripts/local.sh start|stop|status'; exit 2 ;;
esac

docker compose -f compose.local.yml up -d --wait
if [[ ! -f .env.local ]]; then cp .env.local.example .env.local; fi
uv sync --frozen
export PYTHONPATH="$project_dir/backend"
export NO_PROXY=localhost,127.0.0.1,::1
export no_proxy="$NO_PROXY"
uv run alembic upgrade head
uv run python scripts/local_init.py
npm --prefix frontend ci
npm --prefix frontend run build

for unit in "${units[@]}"; do systemctl --user stop "$unit" 2>/dev/null || true; done
start_service() {
  local unit="$1"
  shift
  systemd-run --user --collect --unit="$unit" \
    --property="WorkingDirectory=$project_dir" \
    --property=Restart=on-failure --property=RestartSec=3 \
    --setenv="PYTHONPATH=$PYTHONPATH" --setenv="NO_PROXY=$NO_PROXY" \
    --setenv="no_proxy=$NO_PROXY" --setenv="ALL_PROXY=${ALL_PROXY:-}" \
    --setenv="HTTPS_PROXY=${HTTPS_PROXY:-}" --setenv="HTTP_PROXY=${HTTP_PROXY:-}" \
    "$@"
}
uv_bin="$(command -v uv)"
if [[ "$uv_bin" == /snap/bin/uv && -x /snap/astral-uv/current/bin/uv ]]; then
  uv_bin=/snap/astral-uv/current/bin/uv
fi
start_service interviewer-api "$uv_bin" run --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8000
start_service interviewer-worker "$uv_bin" run --no-sync celery -A app.celery_app:celery_app worker --concurrency=1 --loglevel=INFO
start_service interviewer-beat "$uv_bin" run --no-sync celery -A app.celery_app:celery_app beat --loglevel=INFO --schedule=/tmp/interviewer-e2e-beat
start_service interviewer-frontend "$(command -v npm)" --prefix frontend run preview -- --host 127.0.0.1 --port 5173 --strictPort
for attempt in {1..30}; do
  if curl --noproxy '*' --fail --silent http://127.0.0.1:8000/health/db >/dev/null \
    && curl --noproxy '*' --fail --silent http://127.0.0.1:5173 >/dev/null; then
    break
  fi
  if [[ "$attempt" == 30 ]]; then echo 'Startup failed; check journalctl --user'; exit 1; fi
  sleep 1
done
echo 'Application: http://localhost:5173 — Logs: journalctl --user -u interviewer-api -u interviewer-worker -f'
