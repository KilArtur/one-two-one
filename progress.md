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
