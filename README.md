# ИИ-интервьюер

Веб-платформа асинхронного видеоинтервью для первичной технической оценки ИТ-кандидатов.
Кандидат по персональной ссылке в удобное время проходит интервью с камерой и микрофоном:
система показывает и озвучивает вопросы, записывает и транскрибирует ответы и формирует
**карту покрытия требований вакансии**.

Единица оценки — не балл кандидата, а **покрытие требований**. По каждому топику система
выдаёт статус ✅ подтверждено / ❓ требует проверки / ❌ не подтверждено с обязательным
**evidence** (цитата из транскрипта + таймкод видео). Итоговое кадровое решение всегда
принимает человек.

## Ключевые принципы

- **Решение принимает человек.** LLM не выносит вердикт и не выставляет числовой AI-score.
- **Рекомендация детерминирована** — чистая функция от матрицы статусов топиков, не суждение модели.
- **`system_status` неизменяем.** Правки эксперта идут в `current_status` + append-only лог.
- **Изоляция топиков.** Оценивается только требование того топика, к которому задан вопрос.
- **«Требует проверки» — состояние по умолчанию.** Автоотказ — только при явном стоп-факторе.
- **RBAC.** Рекрутер настраивает всё, но не меняет статусы; hard-топики закрывает техспециалист,
  soft — нанимающий менеджер.
- **Вопросы — только устные.** Никаких заданий на написание кода/SQL/лайв-кодинг.
- **Персонализация.** Экспертное «ядро» вопросов — каркас; для каждого кандидата вопросы
  раскрываются под его резюме, не меняя предмета проверки.

Полный контекст — в [`data/PRD-AI-Interviewer-2026-09-04.md`](data/PRD-AI-Interviewer-2026-09-04.md).
Правила разработки — [`CLAUDE.md`](CLAUDE.md) / [`AGENTS.md`](AGENTS.md).

## Стек

| Слой | Технологии |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Очередь | Celery + Redis (worker + beat для retention) |
| Хранилище | S3-совместимое (dev — MinIO; загрузка ответов чанками) |
| БД | PostgreSQL |
| LLM | LangChain `ChatOpenAI` по OpenAI-совместимому протоколу (`OPENAI_BASE_URL`), native structured outputs |
| Оркестрация интервью | LangGraph (сколько уточнений задать, когда закрыть топик) |
| ASR / TTS | OpenAI-совместимые Whisper (транскрипт с таймкодами) и TTS (стриминг, кеш ядра вопросов) |
| Frontend | React 18 + TypeScript + Vite, MediaRecorder API |
| Пакеты | `uv` (backend), `npm` (frontend) |
| Auth | JWT для внутренних ролей (таблица `staff_user`) + магические ссылки для кандидатов |

### Как устроено

```
Браузер кандидата ──HTTPS──┐
Браузер команды  ──HTTPS──┤
                          ▼
                  Frontend (Vite/React, :5173)
                          │  REST + JWT
                          ▼
                  FastAPI (:8000) ──► PostgreSQL
                     │      │    └──► S3 / MinIO (видео, аудио, кеш TTS)
                     │      └───────► LLM / ASR / TTS (внешние API)
                     ▼
                  Redis ◄──► Celery worker (транскрибация → анализ → сборка результата)
                            Celery beat  (retention)
```

## Структура репозитория

```
backend/            FastAPI-приложение
  app/api/          HTTP-эндпоинты
  app/services/     детерминированная бизнес-логика (тестируется без сети)
  app/integrations/ обёртки над LLM / ASR / TTS / S3
  app/models/       ORM-модели, alembic/ — миграции
frontend/           React + TypeScript (Vite)
prompts/            промпты моделей (по одному .md на промпт)
docker-compose.yml  инфраструктура (postgres, redis, minio, celery)
scripts/            локальный запуск и утилиты
data/               PRD (ПДн и датасеты не коммитятся)
```

## Быстрый старт (локально)

Требуется: Docker + Docker Compose, [`uv`](https://docs.astral.sh/uv/), Node.js 20+.

```bash
# 1. Секреты
cp .env.example .env            # заполнить ключи LLM/ASR/TTS и секреты (см. ниже)

# 2. Инфраструктура: Postgres + Redis + MinIO (+ создание бакета)
docker compose --profile storage up -d postgres redis minio minio-init

# 3. Backend
uv sync
export PYTHONPATH="$PWD/backend"
uv run alembic upgrade head                                   # миграции
uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# 4. Обработка ответов (в отдельных терминалах)
uv run celery -A app.celery_app:celery_app worker --concurrency=1 --loglevel=INFO
uv run celery -A app.celery_app:celery_app beat --loglevel=INFO

# 5. Frontend
npm --prefix frontend install
npm --prefix frontend run dev                                 # http://localhost:5173
```

Проверки: `GET /health` — живость, `GET /health/db` — соединение с БД, `/docs` — Swagger UI.

**Вход команды:** на экране входа выбрать роль, задать логин/пароль и **зарегистрироваться**
(таблица `staff_user`), затем входить этой парой.
**Кандидат:** открывает персональную ссылку `/, /interview?token=…`, даёт согласие, проходит
проверку камеры/микрофона и отвечает на вопросы.

> Есть скрипт `scripts/local.sh` (start/stop/status), который поднимает инфраструктуру и
> запускает API, worker, beat и фронт как `systemd --user` юниты — удобно для длительной сессии.

## Конфигурация (`.env`)

| Группа | Ключи |
|---|---|
| Приложение | `APP_ENV`, `CORS_ORIGINS`, `SECRET_KEY`, `JWT_SECRET_KEY`, `MAGIC_LINK_SECRET`, `CANDIDATE_JWT_ACCESS_TOKEN_TTL_SECONDS` |
| БД | `DATABASE_URL`, `DATABASE_ECHO` |
| LLM | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_DEFAULT_HEADERS`, `LLM_MODEL`, `LLM_FAST_MODEL`, `FOLLOWUP_DECISION_TIMEOUT_SECONDS` |
| Очередь | `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| Хранилище | `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET` |
| ASR / TTS | `AUDIO_API_KEY`, `AUDIO_BASE_URL`, `ASR_MODEL`, `TTS_MODEL`, `TTS_VOICE`, `TTS_TIMEOUT_SECONDS` |

Секреты только из окружения / `.env` (файл в `.gitignore`; шаблон — `.env.example`).
Провайдер LLM/ASR/TTS меняется через `*_BASE_URL` без правок кода (OpenAI-совместимый протокол).

## Тесты

```bash
uv run ruff check . && uv run pytest          # backend: линт + тесты
npm --prefix frontend run build               # frontend: типы (tsc) + сборка
npm --prefix frontend run test                # frontend: vitest
```

## Деплой для демонстрации

Демо-стенд рассчитан на показ, не на продовую нагрузку: один сервер, всё в Docker, после
демонстрации сервер выключается.

### Параметры сервера

| Ресурс | Рекомендация для демо |
|---|---|
| CPU / RAM | **2 vCPU / 4 GB** (комфортно — 4 vCPU / 8 GB) |
| Диск | 40 GB SSD |
| ОС | Ubuntu 24.04 LTS |
| Сеть | публичный IP + **исходящий интернет** (нужен для LLM/ASR/TTS API) |
| Порты | 80 и 443 (HTTPS), 22 (SSH) |
| Биллинг | почасовой — включил на время демо, потом выключил |

Подойдут Hetzner CPX21/CX22, DigitalOcean/Hetzner дроплет 2 vCPU/4 GB и аналоги.

> **Важно:** запись камеры и микрофона (`getUserMedia`) работает только в защищённом
> контексте — нужен **HTTPS с доменом** (или `localhost`). Для удалённого демо обязательно
> поднять TLS (проще всего через Caddy с автоматическим Let's Encrypt) — по «голому» IP по
> HTTP камера в браузере не включится.

### Порядок раскатки

```bash
# на сервере (Ubuntu): установить Docker + Compose plugin, uv, Node 20
git clone git@github.com:KilArtur/one-two-one.git && cd one-two-one
cp .env.example .env      # прописать реальные ключи; CORS_ORIGINS = https://<домен>

docker compose --profile storage up -d postgres redis minio minio-init
uv sync && PYTHONPATH="$PWD/backend" uv run alembic upgrade head
npm --prefix frontend install && npm --prefix frontend run build   # статика в frontend/dist

# API + worker + beat + отдача frontend/dist за reverse-proxy (Caddy/nginx) с TLS
```

Reverse-proxy отдаёт `frontend/dist` и проксирует `/…` API на `:8000`; TLS терминируется на
нём. После демонстрации: `docker compose down` и выключить/удалить сервер.

## Документация

- Продукт и требования: [`data/PRD-AI-Interviewer-2026-09-04.md`](data/PRD-AI-Interviewer-2026-09-04.md)
- Сценарий ручной проверки: [`docs/manual-qa-guide.md`](docs/manual-qa-guide.md)
- Правила разработки: [`CLAUDE.md`](CLAUDE.md) · [`AGENTS.md`](AGENTS.md)
