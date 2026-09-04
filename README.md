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

# 2. Python-окружение (uv)
uv venv                  # создаёт .venv
uv sync                  # ставит зависимости из pyproject.toml (после TASK-001)

# 3. Секреты
cp .env.example .env     # затем заполнить значения — см. комментарии в файле

# 4. Аутентификация ассистента (один раз, у себя)
claude login            # для Claude Code
codex login             # для Codex   (или задать OPENAI_API_KEY / ANTHROPIC_API_KEY)
```

> Скелет `backend/` и `frontend/` создаётся первыми задачами `tasks.json`
> (TASK-001…003). До этого репозиторий содержит только план и правила.

## Запуск backend

```bash
docker compose up -d                                        # postgres + redis
uv run alembic upgrade head                                 # накатить миграции
uv run uvicorn app.main:app --app-dir backend --reload      # API на localhost:8000
```

`GET /health` — проверка живости, `GET /health/db` — проверка соединения с БД,
`/docs` — Swagger UI. Конфигурация читается из окружения и `.env`
(см. `backend/app/config.py`).

CRUD вакансий с версионированием матрицы (M1): `POST/GET/PATCH /vacancies`,
`PUT /vacancies/{id}/topics` (замена состава активной вакансии создаёт новую версию-снимок;
валидация 5–9 топиков, Р8). CRUD топиков черновика: `POST /vacancies/{id}/topics`,
`PATCH`/`DELETE /vacancies/{id}/topics/{topic_id}`. ASR-словарь на вакансию с авто-подсказкой
из матрицы: `GET`/`PUT /vacancies/{id}/asr-dictionary`. Генерация ядра вопросов (M2)
через LLM: `POST /vacancies/{id}/core-questions` (1 core-вопрос на топик, кеш, повтор без дублей).
Промпты — в `prompts/*.md` (загрузчик `app.prompts.load_prompt`).

Оценка (сервисы, вызываются пайплайном): статус топика — детерминированное правило Р13
(`services.topic_status.resolve_topic_status`); LLM-оценка топика из транскрипта с evidence
и изоляцией Р16 (`services.topic_assessment.assess_topic`, `system_status` не перезаписывается);
стоп-факторы Р6 (`services.stop_factor` — авто «не подходит» только при явном ответе с high
confidence, флаг в отдельной таблице `stop_factor_flag`). Итоговая рекомендация Р5 —
детерминированная чистая функция (`services.recommendation.compute_recommendation`);
Coverage Р4 — тройка чисел + доли `mandatory_coverage`/`desired_coverage`
(`services.coverage.compute_coverage`), без единого балла/AI-score. Сборка результата —
`services.interview_result.assemble_interview_result` (агрегация TopicAssessment в
InterviewResult, фиксация версий, идемпотентно по `candidate_id`).

Batch-оценка транскриптов без видео (Этап 1): `uv run python scripts/batch_eval.py
<input.json|.csv> [-o report.json]` — статус/рекомендация/coverage по каждому кандидату
(core в `services.batch_eval`, пример — `scripts/batch_eval_sample.json`).

## Запуск frontend

```bash
cd frontend
npm install
npm run dev            # SPA на localhost:5173 (Vite + React + TS)
```

Базовый URL API берётся из `VITE_API_BASE_URL` (см. `frontend/.env.example`,
по умолчанию `http://localhost:8000`). `npm run build` — production-сборка,
`npm run typecheck` — проверка типов.

## Миграции

Alembic настроен на корневой [`alembic.ini`](alembic.ini), ревизии лежат в
`backend/alembic/versions`, URL берётся из `DATABASE_URL`.

```bash
uv run alembic revision --autogenerate -m "add vacancy"   # новая ревизия по моделям
uv run alembic upgrade head                               # накатить
uv run alembic downgrade -1                               # откатить одну ревизию
```

Модели наследуются от `app.db.Base`, сессия в эндпоинтах — через зависимость
`app.db.get_db`.

## Разработка по задачам

Работаем **по одной задаче за сессию** из `tasks.json`. Порядок и правила —
в `CLAUDE.md` (раздел «Рабочий процесс»). Автоматический прогон циклом Ralph:

```bash
./ralph.sh 5 codex artur   # выполнить 5 задач через Codex, исполнитель artur
./ralph.sh 3 claude zakhar # выполнить 3 задачи через Claude, исполнитель zakhar
./ralph.sh             # все оставшиеся задачи, агент — автоопределение
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
