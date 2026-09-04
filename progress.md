# Progress Log — ИИ-интервьюер

Журнал прогресса агентов. Каждый агент после завершения задачи добавляет запись сюда.

Формат записи:

```
## TASK-XXX — <краткое название>
- **Дата:** YYYY-MM-DD
- **Статус:** done
- **Что сделано:** краткое описание изменений
- **Как проверено:** результат прохождения test_steps
- **Коммиты:** <хэши>
- **Заметки:** отклонения, TODO, обнаруженные проблемы
```

---

<!-- Записи агентов добавляются ниже -->

## TASK-001 — скаффолд монорепо + docker-compose
- **Дата:** 2026-09-04
- **Статус:** done
- **Что сделано:**
  - `docker-compose.yml` — Postgres 16 + Redis 7 с healthcheck (creds = `.env.example`)
  - Host-порт Postgres: **5433→5432** (на машине уже слушает system PostgreSQL на 5432)
  - Структура: `backend/app/`, `backend/tests/`, `frontend/src/`, `infra/`, `docs/`
  - `pyproject.toml` + `uv.lock` (uv, ruff, pytest, mypy) + smoke-тесты scaffold
  - Обновлены `.env.example` (`DATABASE_URL` → `:5433`), `README.md`, `.gitignore`
  - Скрипт проверки: `scripts/verify-task-001.sh`
- **Как проверено:**
  1. `uv run ruff check .` — OK
  2. `uv run pytest` — 2 passed
  3. `docker compose up -d` → postgres+redis **healthy**
  4. `psql -c 'SELECT 1'` и `redis-cli ping` → OK; `docker compose down` очищает
- **Коммиты:** (хеш после commit ниже)
- **Заметки:**
  - На этой машине `unix:///var/run/docker.sock` недоступен (user не в группе `docker`); работал Docker Desktop: `systemctl --user start docker-desktop` + `docker context use desktop-linux`.
  - Следующая задача по critical path: **TASK-002** (скелет FastAPI `/health`).
