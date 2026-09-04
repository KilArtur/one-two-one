"""CLI сравнения system-отчёта с экспертной разметкой.

Использование:
    uv run python scripts/compare_expert.py
        <system_report.json> <expert.json|expert.csv> [-o summary.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.compare_expert import compare_with_expert, load_comparison_input  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Сравнение system-отчёта с экспертной разметкой")
    parser.add_argument("system_report", help="Путь к JSON-отчёту системы")
    parser.add_argument("expert_labels", help="Путь к экспертной разметке (.json или .csv)")
    parser.add_argument("-o", "--output", help="Путь для итогового JSON (по умолчанию stdout)")
    args = parser.parse_args()

    summary = compare_with_expert(
        load_comparison_input(args.system_report),
        load_comparison_input(args.expert_labels),
    )
    payload = json.dumps(summary, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(
            "Сводка сохранена: "
            f"{args.output} ({summary['recommendation_agreement']['matched']}/"
            f"{summary['recommendation_agreement']['total']} рекомендаций совпало)"
        )
        return

    print(payload)


if __name__ == "__main__":
    main()
