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

## TASK-001 — Скаффолд монорепо и dev-окружение
- **Дата:** 2026-09-04
- **Статус:** in_progress
- **Что сделано:** добавлены `backend/app`, `frontend/src`, `infra`, корневой `docker-compose.yml` с `postgres` и `redis`, `pyproject.toml` для `ruff`/`pytest`, базовый тест `tests/test_task_001_scaffold.py` на структуру скаффолда и наличие ключевых конфигов; в тесте добавлен модульный docstring, чтобы проходил `ruff`.
- **Как проверено:** `python3 -m py_compile backend/app/__init__.py tests/test_task_001_scaffold.py` проходит; `ruff check /home/artur/projects/one-two-one` из доступного локального venv проходит; `pytest /home/artur/projects/one-two-one/tests/test_task_001_scaffold.py` проходит (`3 passed`); прямой запуск `uv run ruff check .` и `uv run pytest` остаётся заблокированным, потому что в проектном окружении нет установленных пакетов, а `uv sync` не может скачать их из-за недоступности `pypi.org` в этой среде; `docker compose` test_steps не выполнены, потому что `docker` отсутствует в окружении.
- **Коммиты:** будет создан отдельный commit по `TASK-001` после обновления журнала
- **Заметки:** статус `tasks.json` оставлен `in_progress`; для закрытия задачи следующей итерации нужно запустить именно `uv run ruff check .`, `uv run pytest` в среде с доступом к пакетам Python и выполнить все три шага `docker compose` из `TASK-001` на хосте, где установлен Docker.

## TASK-001 — Скаффолд монорепо и dev-окружение
- **Дата:** 2026-09-04
- **Статус:** in_progress
- **Что сделано:** поднят локальный toolchain внутри проектного `.venv`: установлены `uv`, `ruff` и `pytest`, после чего дополнительно перепроверен уже существующий scaffold без изменений в коде задачи.
- **Как проверено:** `.venv/bin/uv run ruff check .` проходит (`All checks passed!`); `.venv/bin/uv run pytest` проходит (`3 passed`); обязательные `test_steps` из `tasks.json` всё ещё не закрыты, потому что в текущем окружении отсутствует `docker`, а значит нельзя выполнить `docker compose up -d`, проверить `healthy` у контейнеров и сделать `psql`/`redis-cli` smoke test.
- **Коммиты:** будет создан отдельный commit по обновлению журнала прогресса
- **Заметки:** статус `TASK-001` в [tasks.json](/home/artur/projects/one-two-one/tasks.json) оставлен `in_progress`; следующей итерации нужен хост с установленным Docker для прохождения трёх acceptance `test_steps` без изменений в репозитории.

## TASK-001 — Скаффолд монорепо и dev-окружение
- **Дата:** 2026-09-04
- **Статус:** in_progress
- **Что сделано:** уточнён конфиг `ruff` в `pyproject.toml`: из lint scope исключён `.codex-home`, чтобы dev-проверка охватывала только код и конфиги репозитория в рамках `TASK-001`.
- **Как проверено:** `uv run ruff check .` проходит (`All checks passed!`); `uv run pytest` проходит (`3 passed`); `docker --version` доступен; `docker compose up -d` стартовал, но упёрся в скачивание `redis:7-alpine` из Docker Hub с ошибкой `network is unreachable`; `docker compose down -v` выполнен для cleanup.
- **Коммиты:** будет создан отдельный commit по обновлению конфигурации и журнала прогресса
- **Заметки:** `TASK-001` в [tasks.json](/home/artur/projects/one-two-one/tasks.json) оставлен `in_progress`; для завершения задачи следующей итерации нужно повторить `docker compose up -d`, дождаться `healthy` у `postgres` и `redis`, затем выполнить smoke check через `psql` и `redis-cli` внутри контейнеров в среде с доступом Docker к registry.

## TASK-001 — Скаффолд монорепо и dev-окружение
- **Дата:** 2026-09-04
- **Статус:** in_progress
- **Что сделано:** для `redis` в [docker-compose.yml](/home/artur/projects/one-two-one/docker-compose.yml) заменён образ `redis:7-alpine` на официальный mirror `public.ecr.aws/docker/library/redis:7-alpine`, чтобы обойти сбой pull из Docker Hub по IPv6 и сохранить тот же Redis 7 Alpine в dev-окружении.
- **Как проверено:** `UV_CACHE_DIR=/tmp/uv-cache ./.venv/bin/uv run ruff check .` проходит (`All checks passed!`); `UV_CACHE_DIR=/tmp/uv-cache ./.venv/bin/uv run pytest` проходит (`3 passed`); хостовый `docker pull postgres:16-alpine` ранее проходит, а `docker pull redis:7-alpine` падал на `registry-1.docker.io ... network is unreachable`; проверка обновлённого compose внутри этой среды не выполнена, потому что shell-инструменты текущей сессии не имеют доступа к хостовому `docker`.
- **Коммиты:** pending
- **Заметки:** `TASK-001` в [tasks.json](/home/artur/projects/one-two-one/tasks.json) оставлен `in_progress`; после этой правки нужно повторить `docker compose up -d`, дождаться `healthy` у `postgres` и `redis`, затем выполнить smoke check через `psql` и `redis-cli` на хосте.

## TASK-001 — Скаффолд монорепо и dev-окружение
- **Дата:** 2026-09-04
- **Статус:** done
- **Что сделано:** пройдены все `test_steps` на хосте с рабочим Docker. Docker Hub снова доступен (`docker pull redis:7-alpine` проходит), поэтому в [docker-compose.yml](/home/artur/projects/one-two-one/docker-compose.yml) убран временный mirror `public.ecr.aws/docker/library/redis:7-alpine` и возвращён канонический `redis:7-alpine` — симметрично `postgres:16-alpine`. Зафиксирован `uv.lock` для воспроизводимости dev-зависимостей (`ruff`, `pytest`).
- **Как проверено:** `docker compose up -d` — оба контейнера стартуют без ошибок; `docker inspect` показывает `postgres=healthy redis=healthy`; `docker exec interviewer-postgres psql -U interviewer -d interviewer -c "SELECT 1"` возвращает строку, `docker exec interviewer-redis redis-cli PING` -> `PONG`, `SET/GET/DEL` работают; порты `5432` и `6379` доступны с хоста; `docker compose down` удаляет контейнеры и сеть, `docker ps -a --filter name=interviewer-` пуст. `uv run ruff check .` — `All checks passed!`; `uv run pytest` — `3 passed`. Acceptance criteria закрыты: compose поднимается, `.env.example` содержит все ключи, структура `backend/app`, `frontend/src`, `infra`, `docs` на месте.
- **Коммиты:** `feat: complete TASK-001 dev environment scaffold` (последний коммит ветки `artur`)
- **Заметки:** статус `TASK-001` переведён в `done`. Следующая задача по критическому пути — `TASK-002` (скелет FastAPI: `app/main.py`, `config.py` на pydantic-settings, CORS, `/health`); её зависимость `TASK-001` теперь выполнена. `backend/app` пока содержит только пустой `__init__.py` — приложение появляется в `TASK-002`. Если pull образов снова упрётся в Docker Hub по IPv6, рабочий обходной путь — mirror `public.ecr.aws/docker/library/<image>`.

## TASK-002 — Скелет FastAPI: config, CORS, /health
- **Дата:** 2026-09-04
- **Статус:** done
- **Что сделано:** добавлены [backend/app/config.py](/home/artur/projects/one-two-one/backend/app/config.py) (`Settings` на pydantic-settings, `env_file` привязан к корню репо, `extra="ignore"`, кеш через `get_settings()`) и [backend/app/main.py](/home/artur/projects/one-two-one/backend/app/main.py) (фабрика `create_app`, `CORSMiddleware` из `cors_origins`, async-эндпоинт `GET /health` с pydantic-моделью `HealthResponse`). В `pyproject.toml` добавлены рантайм-зависимости `fastapi`, `uvicorn[standard]`, `pydantic-settings`, dev-зависимость `httpx`, а также `pytest.pythonpath = ["backend"]` и `ruff.src = ["backend"]`, чтобы `app.*` резолвился как first-party. В `.env.example` добавлен ключ `CORS_ORIGINS` (JSON-список). Тесты — [tests/test_task_002_api.py](/home/artur/projects/one-two-one/tests/test_task_002_api.py). README дополнен секцией «Запуск backend».
- **Как проверено:** `uv run ruff check .` — `All checks passed!`; `uv run pytest` — `7 passed`. Все три `test_steps` выполнены вживую: (1) `uv run uvicorn app.main:app --app-dir backend --port 8123` стартует без ошибок (`Application startup complete`); (2) `curl /health` -> `HTTP 200` и `{"status":"ok","app_env":"development","version":"0.1.0"}`; (3) `curl /docs` -> `HTTP 200` с разметкой `swagger-ui`, `/openapi.json` содержит путь `/health`. Дополнительно: preflight `OPTIONS /health` с `Origin: http://localhost:5173` возвращает `access-control-allow-origin`, а запуск с `APP_ENV=staging` отдаёт `"app_env":"staging"` — конфигурация действительно читается из окружения.
- **Коммиты:** `feat: add FastAPI skeleton with config and health endpoint`
- **Заметки:** статус `TASK-002` переведён в `done`. Приложение импортируется как `app.main:app` при `--app-dir backend` (пакет `backend/app`) — этот же путь понадобится для Celery и Alembic. `cors_origins` задаётся JSON-списком в `.env`, ручного парсинга строки нет намеренно. Следующая задача критического пути — `TASK-003` (PostgreSQL + Alembic, `get_db`): БД-настройки стоит добавить в тот же `Settings` (`DATABASE_URL` уже есть в `.env.example`), сессию — async (`asyncpg` в URL). `TestClient` печатает `StarletteDeprecationWarning` про `httpx2` — не блокирует, при желании поменять dev-зависимость позже.

## TASK-003 — PostgreSQL + Alembic + зависимость get_db
- **Дата:** 2026-09-04
- **Статус:** done
- **Что сделано:** добавлен слой доступа к БД [backend/app/db/](/home/artur/projects/one-two-one/backend/app/db): `base.py` (`Base` на `DeclarativeBase` — общая метадата для моделей и Alembic) и `session.py` (async-движок `create_async_engine` с `pool_pre_ping`, фабрика `async_sessionmaker`, зависимость `get_db`, `dispose_engine` для закрытия пула). Движок и фабрика кешируются через `lru_cache`, поэтому в тестах их можно перенацелить сбросом кеша. В `Settings` добавлены `database_url` и `database_echo`, в `.env.example` — `DATABASE_ECHO`. В [backend/app/main.py](/home/artur/projects/one-two-one/backend/app/main.py) появились `lifespan` (освобождает пул на остановке сервиса) и пробный эндпоинт `GET /health/db`, который выполняет `SELECT 1` через сессию из `get_db`. Alembic настроен на корневой [alembic.ini](/home/artur/projects/one-two-one/alembic.ini) (`script_location=%(here)s/backend/alembic`, `prepend_sys_path=%(here)s/backend`, `sqlalchemy.url` намеренно убран), окружение — [backend/alembic/env.py](/home/artur/projects/one-two-one/backend/alembic/env.py) на async-движке с URL из `Settings`; `script.py.mako` переписан под стиль проекта (`str | Sequence[str] | None`, русские докстринги), чтобы автогенерируемые ревизии проходили `ruff`. Первая ревизия `11d73faaed8f_initial_baseline` — базовая точка отсчёта цепочки (таблицы доменной модели идут в `TASK-004`). Зависимости: `sqlalchemy[asyncio]`, `alembic`, `asyncpg`, dev — `aiosqlite`. Тесты — [tests/test_task_003_db.py](/home/artur/projects/one-two-one/tests/test_task_003_db.py).
- **Как проверено:** `uv run ruff check .` — `All checks passed!`; `uv run pytest` — `12 passed`. Все три `test_steps` выполнены вживую на поднятом `docker compose` (postgres/redis `healthy`): (1) `uv run alembic upgrade head` -> `Running upgrade -> 11d73faaed8f`, `alembic current` = `11d73faaed8f (head)`, в psql видна таблица `alembic_version` с этой версией; (2) `uvicorn app.main:app --app-dir backend --port 8124` стартует, `curl /health/db` -> `HTTP 200` и `{"status":"ok","database":"ok"}`, путь `/health/db` есть в `/openapi.json`; (3) `uv run alembic downgrade base` -> `Running downgrade 11d73faaed8f -> `, `alembic current` пуст, `SELECT count(*) FROM alembic_version` = 0, повторный `upgrade head` снова даёт `head`. Дополнительно: `docker compose stop postgres` переводит `/health/db` в `HTTP 500`, после `start` эндпоинт снова отдаёт 200 — запрос действительно ходит в БД, а `pool_pre_ping` переживает рестарт; `alembic upgrade head --sql` (offline-режим) генерирует корректный SQL.
- **Коммиты:** `feat: add PostgreSQL session layer and Alembic baseline`
- **Заметки:** статус `TASK-003` переведён в `done`. Для `TASK-004` важно: `env.py` берёт метадату из `app.db.Base`, поэтому новые ORM-модели **нужно импортировать**, чтобы `--autogenerate` их увидел — заведи `backend/app/models/__init__.py` с реэкспортом моделей и добавь его импорт в `env.py`, иначе автогенерация выдаст пустую ревизию. Все `id` в PRD — `uuid`; расширение для этого не нужно, в Postgres 16 `gen_random_uuid()` встроен. Тесты гоняют `get_db` поверх `sqlite+aiosqlite:///:memory:`, чтобы `uv run pytest` не требовал Postgres, — если в задаче понадобятся Postgres-специфичные типы (`jsonb`, enum), тест придётся переводить на реальную БД. В рабочем дереве остаются несвязанные с задачей правки `.gitignore` и `ralph.sh` (тулинг Codex) — в коммит `TASK-003` они намеренно не попали.
