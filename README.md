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

ASR (Whisper): `integrations.asr.OpenAIWhisperClient` — транскрипт с сегментами и таймкодами,
словарь вакансии через `prompt` (audio-провайдер из `AUDIO_*`/`ASR_MODEL`). Транскрибация
ответа (M5) — Celery-задача `app.transcribe_answer` (`services.transcription.transcribe_answer`):
`recorded→transcribing→ready`; пустая/битая дорожка → `error` и топик получает `needs_check`.
Оркестрация обработки ответа (M5): Celery-задача `app.process_answer`
(`services.pipeline.process_answer`) — транскрибация → анализ → сборка `InterviewResult`;
статусы recorded→transcribing→analyzing→ready, сбой LLM не блокирует (топик → needs_check).
Смена статуса экспертом (Р21): `PATCH /topic-assessments/{id}/status` — обязательный
комментарий, RBAC (hard→техспец, soft→НМ), `system_status` неизменен, каждая смена —
append-only запись в `StatusChangeLog`.

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

## Согласие кандидата

Персональное приглашение открывается на `/interview?token=<InterviewLink.token>`.
После обмена ссылки на сессию кандидат видит `/interview/consent`; токен приглашения
убирается из адреса, JWT хранится в `sessionStorage` текущей вкладки.
Кнопка продолжения доступна после явного согласия, переход на `/interview/equipment`
происходит только после сохранения `Candidate.consent_given_at` сервером.
На шаге оборудования браузер запрашивает камеру и микрофон. Кнопка «Записать 3 секунды»
создаёт локальную пробу с воспроизведением; запись не загружается на сервер.
При отказе в доступе или отключении устройства появляется предупреждение и доступна
повторная проверка. Для доступа к устройствам нужен HTTPS либо localhost.

`GET/POST /candidate-auth/consent` читают/сохраняют согласие (`{"accepted": true}`),
`GET /candidate-auth/equipment-check` проверяет допуск к следующему шагу.
Все эти запросы требуют кандидатский Bearer JWT и действующую ссылку.
Отправка интервью также требует согласия. Новые кандидатские эндпоинты записи
должны использовать dependency `require_candidate_consent`.

Проверки экрана: `cd frontend` и `npm test`; проверка типов и сборка: `npm run build`.
Текст согласия основан на разделе 8 PRD; юридическое согласование заказчиком
предусмотрено тем же разделом перед использованием в реальном подборе.

## Озвучка вопросов (TASK-029)

`get_question_audio_service()` из `app.services.question_audio` собирает TTS и S3.
`service.stream_audio(question)` — асинхронный генератор MP3-чанков для будущего
плеера интервью (TASK-030). При досрочном прекращении чтения закрывайте генератор
через `contextlib.aclosing`; неполученное до конца аудио не кешируется.

Core-вопрос: сначала чтение S3, при отсутствии объекта — потоковый синтез и
сохранение полного MP3 с `Content-Type: audio/mpeg`. Повторный запрос не вызывает
TTS. Персональные и уточняющие вопросы каждый раз синтезируются без кеширования.
Ключ `tts/core/v1/<sha256>.mp3` зависит от id и текста вопроса, адреса провайдера,
модели, голоса и формата; смена текста или голоса не отдаёт старую озвучку.
Ошибки доступа к S3 не считаются промахом кеша; ошибки провайдера возвращаются
как `TTSClientError`. Параллельные первые запросы могут независимо синтезировать
один вопрос; распределённая блокировка не добавлена.

Настройки: `AUDIO_API_KEY`, `AUDIO_BASE_URL`, `TTS_MODEL=tts-1`, `TTS_VOICE=alloy`,
`TTS_TIMEOUT_SECONDS=30` и существующие `S3_*`. Бакет должен быть создан через
настройку окружения (dev: профиль `storage` Docker Compose).
Ключ LLM/OpenRouter не подставляется вместо отдельного аудиоключа.
Используется [Speech API с потоковым ответом](https://developers.openai.com/api/docs/guides/text-to-speech).
При подключении плеера нужно явно сообщить кандидату, что голос синтезирован.

Проверки без сети: `uv run pytest tests/test_task_029_tts.py tests/test_task_008_storage.py`.

## Экран ответа (TASK-030)

После пробной записи на `/interview/equipment` кнопка подтверждения переводит на
`/interview/session`. Вопрос показывается текстом и озвучивается синтезированным
голосом. MP3 передаётся через авторизованный fetch и MediaSource; без поддержки
MSE браузер использует Blob. При запрете autoplay доступна кнопка запуска озвучки.

Запись ответа начинается после события `ended` аудиоплеера, таймер — после
события `start` MediaRecorder. Основной/персональный вопрос: 120 секунд,
уточнение: 60 секунд. Отсчёт использует абсолютный срок окончания, поэтому
задержка таймеров фоновой вкладки не добавляет время ответа. Запись прекращается
по лимиту либо по кнопке «Закончить ответ». Перезаписи нет; сбои озвучки до начала
ответа допускают повторную попытку. Отключение устройств прекращает запись.

`GET /candidate-interview/questions` и `/candidate-interview/questions/{id}/audio`
требуют действующую кандидатскую сессию и согласие; доступны только core-вопросы
закреплённой версии вакансии, без внутренних оснований оценки. Генерация и выдача
адаптивных уточнений остаётся задачей 45; UI-лимит уточнения проверен на тестовом
вопросе. Текущая страница последовательно показывает готовое ядро вопросов.

До TASK-031/032 ответы остаются локально во вкладке, доступны для скачивания и
не считаются отправленными на сервер. Загрузка чанков и финальная отправка здесь
не реализованы. Уход со страницы освобождает устройства, таймеры и object URL.

## Приём записей (TASK-032)

API требует Bearer-сессию кандидата и согласие на запись. Доступны только
core-вопросы его вакансии, как и в API выдачи вопросов.

- `POST /candidate-interview/questions/{question_id}/uploads` с JSON
  `{"upload_id":"<UUID клиента>"}` резервирует запись. Тот же UUID допускает
  безопасный повтор запроса, другой UUID для того же вопроса получает 409.
- `PUT /candidate-interview/uploads/{id}/{video|audio}/{index}` принимает multipart
  с полем `file`. Индексы каждой дорожки начинаются с 0 и идут последовательно.
  Идентичный повтор допустим; пропуск индекса или изменение принятой части — 409.
- `POST /candidate-interview/uploads/{id}/complete` с JSON
  `{"video_chunks":3,"audio_chunks":3,"duration_sec":4}` собирает обе дорожки и
  возвращает `Answer` со статусом `recorded`. Повтор завершения идемпотентен.

Части сохраняются в `answers/{candidate_id}/{upload_id}/parts/{video|audio}/`.
Итоговые файлы лежат рядом как `video.webm`/`audio.webm` (расширение зависит от
MIME). Сборка выполняется вне event loop, с группировкой малых частей до минимума
S3 multipart 5 МиБ. Ограничения: 8 МиБ на чанк, 256 МиБ на ответ, до 300 частей
каждой дорожки, длительность 1–120 секунд. `Answer` создаётся только после успешной
сборки обеих дорожек; `video_url`/`audio_url` содержат приватные `s3://` адреса.

Перед запуском примените `uv run alembic upgrade head`. Миграция добавляет
`answer.candidate_id` и таблицу манифестов `answer_upload`. Старые ответы сохраняют
NULL в `candidate_id`: надёжно восстановить владельца из прежней схемы нельзя.
Новые ответы всегда связаны с кандидатом. Очистка частей относится к TASK-048.
