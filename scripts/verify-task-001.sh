#!/usr/bin/env bash
# Локальная проверка acceptance/test_steps для TASK-001.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> uv sync"
uv sync

echo "==> ruff"
uv run ruff check .

echo "==> pytest"
uv run pytest

echo "==> docker compose up"
docker compose up -d

echo "==> wait for healthy"
for i in $(seq 1 30); do
  pg=$(docker inspect -f '{{.State.Health.Status}}' interviewer-postgres 2>/dev/null || echo starting)
  rd=$(docker inspect -f '{{.State.Health.Status}}' interviewer-redis 2>/dev/null || echo starting)
  echo "  postgres=$pg redis=$rd"
  if [[ "$pg" == "healthy" && "$rd" == "healthy" ]]; then
    break
  fi
  sleep 2
done

docker compose ps
docker compose exec -T postgres psql -U interviewer -d interviewer -c 'SELECT 1;'
docker compose exec -T redis redis-cli ping
docker compose down

echo "TASK-001 checks OK"
