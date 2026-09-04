# ИИ-интервьюер

Веб-платформа асинхронного видеоинтервью для первичной технической оценки
ИТ-кандидатов. Кандидат по персональной ссылке проходит интервью с камерой и
микрофоном; система озвучивает вопросы, записывает и транскрибирует ответы и
формирует карту покрытия требований вакансии. Финальное решение принимает человек.

- **Правила разработки:** [`CLAUDE.md`](CLAUDE.md) (Claude) / [`AGENTS.md`](AGENTS.md) (Codex) — держать в синхроне.
- **Полный PRD:** [`data/PRD-AI-Interviewer-2026-09-04.md`](data/PRD-AI-Interviewer-2026-09-04.md)
- **План работ:** [`tasks.json`](tasks.json) · журнал прогресса: [`progress.md`](progress.md)

## Стек

Python 3.12+ · FastAPI · PostgreSQL · Celery + Redis · React + TypeScript ·
OpenAI (LLM `gpt-4o`/`gpt-4o-mini`, Whisper ASR, TTS) · LangChain + LangGraph · S3-хранилище.

## Онбординг

```bash
# 1. Клонировать и войти в проект
git clone <repo-url> && cd one-two-one

# 2. Dev-инфра (Postgres + Redis)
docker compose up -d     # healthcheck: interviewer-postgres, interviewer-redis
# проверка: docker compose ps
# psql:  docker compose exec postgres psql -U interviewer -d interviewer
#        (host port 5433 → container 5432; см. DATABASE_URL в .env.example)
# redis: docker compose exec redis redis-cli ping
# стоп:  docker compose down

# 3. Python-окружение (uv)
uv sync                  # ставит зависимости из pyproject.toml (.venv)

# 4. Секреты
cp .env.example .env     # затем заполнить значения — см. комментарии в файле

# 5. Аутентификация ассистента (один раз, у себя)
claude login            # для Claude Code
codex login             # для Codex   (или задать OPENAI_API_KEY / ANTHROPIC_API_KEY)
```

Структура монорепо: `backend/app`, `frontend/src`, `infra`, `docs`.

## Разработка по задачам

Работаем **по одной задаче за сессию** из `tasks.json`. Порядок и правила —
в `CLAUDE.md` (раздел «Рабочий процесс»). Автоматический прогон циклом Ralph:

```bash
./ralph.sh 5 codex artur    # выполнить 5 задач через Codex, исполнитель artur
./ralph.sh 3 cursor zakhar  # Cursor CLI (не Claude Code), исполнитель zakhar
./ralph.sh 3 claude zakhar  # Claude Code CLI, если он установлен
./ralph.sh                  # все оставшиеся задачи, агент — автоопределение
./ralph.sh --help      # справка
```

Скрипт берёт `pending`-задачи с наивысшим приоритетом, проверяет их зависимости,
прогоняет линт/тесты, помечает выполненные `done` и пишет заметки в `progress.md`.
Если есть `task-owners.json`, Ralph выдаёт разработчику только его задачи.

## Совместная работа

Двое (и больше) могут вести разработку параллельно: каждый берёт свою порцию задач,
`ralph.sh` бронирует задачи через `status: in_progress` + `assignee`, продвигает их до `done`, а прогресс фиксируется в git и `progress.md`.
Для схемы `artur + zakhar` используйте [`docs/parallel-workflow.md`](/home/artur/projects/one-two-one/docs/parallel-workflow.md):
там есть готовые ветки, разделение задач и команды для merge через `integration/arthur-zakhar`.
