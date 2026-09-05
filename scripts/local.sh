#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
units=(interviewer-api interviewer-worker interviewer-beat interviewer-frontend)
compose_files=(-f compose.local.yml)
if [[ -f docker-compose.override.yml ]]; then
  compose_files+=(-f docker-compose.override.yml)
fi

case "${1:-start}" in
  stop)
    for unit in "${units[@]}"; do systemctl --user stop "$unit" || true; done
    docker compose "${compose_files[@]}" stop
    exit
    ;;
  status)
    docker compose "${compose_files[@]}" ps
    systemctl --user --no-pager --full status "${units[@]}"
    exit
    ;;
  start) ;;
  *) echo 'Usage: bash scripts/local.sh start|stop|status'; exit 2 ;;
esac

docker compose "${compose_files[@]}" up -d --wait
if [[ ! -f .env.local ]]; then cp .env.local.example .env.local; fi
set -a
# shellcheck disable=SC1091
source .env.local
set +a
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
for attempt in {1..45}; do
  if curl --noproxy '*' --fail --silent http://127.0.0.1:8000/health/db >/dev/null \
    && curl --noproxy '*' --fail --silent http://127.0.0.1:5173 >/dev/null; then
    echo 'Application: http://localhost:5173 — Logs: journalctl --user -u interviewer-api -u interviewer-worker -f'
    exit 0
  fi
  sleep 1
done
echo 'Startup failed. API:' >&2
curl --noproxy '*' -sS -o /tmp/interviewer-health.txt -w '  GET /health/db -> %{http_code}\n' http://127.0.0.1:8000/health/db >&2 || true
curl --noproxy '*' -sS -o /dev/null -w '  GET :5173 -> %{http_code}\n' http://127.0.0.1:5173 >&2 || true
echo '  journalctl --user -u interviewer-api -u interviewer-frontend -n 50 --no-pager' >&2
exit 1
