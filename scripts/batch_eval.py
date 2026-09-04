"""CLI batch-оценки транскриптов без видео (ключ Этапа 1 PRD).

Использование:
    uv run python scripts/batch_eval.py <input.json|input.csv> [-o report.json]

Читает транскрипты по топикам, оценивает каждый топик через LLM (изоляция Р16),
выдаёт статус, рекомендацию (Р5) и Coverage (Р4) по каждому кандидату. Модель/провайдер
и prompt_version берутся из окружения (.env) и конфигурации — код не меняется.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402
from app.services.batch_eval import load_input, run_batch  # noqa: E402
from app.services.topic_assessment import TOPIC_ASSESSMENT_PROMPT_VERSION  # noqa: E402


async def _run(input_path: str, output_path: str | None) -> None:
    candidates = load_input(input_path)
    report = await run_batch(
        candidates,
        model_version=get_settings().llm_model,
        prompt_version=TOPIC_ASSESSMENT_PROMPT_VERSION,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if output_path:
        Path(output_path).write_text(payload, encoding="utf-8")
        print(f"Отчёт сохранён: {output_path} ({len(report['candidates'])} кандидатов)")
    else:
        print(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-оценка транскриптов без видео")
    parser.add_argument("input", help="Путь к входному файлу (.json или .csv)")
    parser.add_argument("-o", "--output", help="Путь для отчёта JSON (по умолчанию stdout)")
    args = parser.parse_args()
    asyncio.run(_run(args.input, args.output))


if __name__ == "__main__":
    main()
