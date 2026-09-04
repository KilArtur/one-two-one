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
- **Коммиты:** edfbbbb
- **Заметки:**
  - На этой машине `unix:///var/run/docker.sock` недоступен (user не в группе `docker`); работал Docker Desktop: `systemctl --user start docker-desktop` + `docker context use desktop-linux`.
  - Следующая задача по critical path: **TASK-002** (скелет FastAPI `/health`).

## TASK-002 — скелет FastAPI: config, CORS, /health
- **Дата:** 2026-09-04
- **Статус:** done
- **Что сделано:**
  - `backend/app/config.py` — pydantic-settings (`Settings` + `get_settings`), чтение `.env`, `CORS_ORIGINS` через запятую
  - `backend/app/main.py` — FastAPI app, CORS middleware, `GET /health` → `{status: ok}`, Swagger `/docs`
  - Зависимости: fastapi, uvicorn[standard], pydantic-settings, httpx
  - Тесты: `backend/tests/test_health.py` (health, docs, settings из env)
  - Обновлены `.env.example` (`CORS_ORIGINS`) и `README.md` (команда uvicorn)
- **Как проверено:**
  1. `uv run ruff check .` — OK
  2. `uv run pytest` — 5 passed
  3. `uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000` — старт без ошибок
  4. `curl /health` → HTTP 200 `{"status":"ok"}`
  5. `curl /docs` → HTTP 200, Swagger UI
- **Коммиты:** 113bfae
- **Заметки:**
  - Запуск: `uv run uvicorn app.main:app --app-dir backend --reload --port 8000`
  - Следующая по critical path: **TASK-003** (PostgreSQL + Alembic + `get_db`)
  - В Settings пока только `app_env` / `secret_key` / `cors_origins` — остальные ключи из `.env.example` добавятся по мере задач

## TASK-003 — PostgreSQL + Alembic + get_db
- **Дата:** 2026-09-04
- **Статус:** done
- **Что сделано:**
  - Зависимости: `sqlalchemy[asyncio]`, `asyncpg`, `alembic`
  - `Settings.database_url` (из `DATABASE_URL` / `.env`)
  - `backend/app/db.py` — async engine (`NullPool`), `AsyncSessionLocal`, FastAPI-зависимость `get_db`
  - `GET /health/db` — `SELECT 1` через `get_db`, ответ `{"status":"ok"}`
  - Alembic: `backend/alembic.ini`, `backend/alembic/env.py` (async), ревизия `0001_baseline` (пустой baseline)
  - Тесты: `backend/tests/test_db.py`; README — команды миграций и `/health/db`
- **Как проверено:**
  1. `uv run ruff check .` — OK
  2. `uv run pytest` — 9 passed
  3. `uv run alembic -c backend/alembic.ini upgrade head` — OK (`0001_baseline`)
  4. `curl /health/db` → HTTP 200 `{"status":"ok"}`
  5. `uv run alembic -c backend/alembic.ini downgrade -1` затем `upgrade head` — OK
- **Коммиты:** 6b2d527
- **Заметки:**
  - Миграции: `uv run alembic -c backend/alembic.ini upgrade head` / `downgrade -1`
  - `NullPool` выбран из‑за asyncpg + pytest event loop; при нагрузке можно вернуть QueuePool
  - Baseline пустой — таблицы Vacancy/Topic появятся в **TASK-004**
  - Следующая по critical path: **TASK-004** (ORM Vacancy + Topic)

## TASK-004 — ORM Vacancy + Topic + миграция
- **Дата:** 2026-09-04
- **Статус:** done
- **Что сделано:**
  - `backend/app/models/` — Base, enums (grade/status/skill_type/importance), Vacancy, Topic
  - Поля по PRD §5: `stop_factors` (text[]), `version`, FK `topic.vacancy_id` CASCADE
  - `verifiable_by_interview` default/server_default = true
  - Alembic-ревизия `0002_vacancy_topic`; `env.py` подключён к `Base.metadata`
  - Тесты: `backend/tests/test_models_vacancy_topic.py`
- **Как проверено:**
  1. `uv run ruff check .` — OK
  2. `uv run pytest` — 13 passed
  3. `alembic upgrade head` → `0002_vacancy_topic`
  4. `\d vacancy` / `\d topic` — все поля PRD на месте, FK и default `verifiable_by_interview=true`
  5. psql INSERT vacancy + topic — JOIN ок, CASCADE delete
- **Коммиты:** dee2e40
- **Заметки:**
  - Enum `vacancy_grade` хранит значение `middle+` как в PRD
  - Колонка топика `"order"` (зарезервированное слово SQL) — в psql нужна кавычка
  - Следующая по critical path: **TASK-005** (Candidate, InterviewLink, Question)
