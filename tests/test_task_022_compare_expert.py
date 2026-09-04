"""Харнесс сравнения с экспертной разметкой (TASK-022)."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.compare_expert import compare_with_expert, load_comparison_input

REPORT_SAMPLE = (
    Path(__file__).resolve().parents[1] / "scripts" / "compare_expert_sample_report.json"
)
EXPERT_SAMPLE = (
    Path(__file__).resolve().parents[1] / "scripts" / "compare_expert_sample_expert.json"
)


def test_compare_expert_produces_agreement_percent() -> None:
    summary = compare_with_expert(
        load_comparison_input(REPORT_SAMPLE),
        load_comparison_input(EXPERT_SAMPLE),
    )

    assert summary["recommendation_agreement"] == {
        "matched": 3,
        "total": 3,
        "agreement_rate": 1.0,
        "threshold": 0.8,
        "passed": True,
    }
    assert summary["topic_status_agreement"] == {
        "matched": 4,
        "total": 5,
        "agreement_rate": 0.8,
    }


def test_compare_expert_builds_confusion_matrices_and_uses_system_status() -> None:
    summary = compare_with_expert(
        load_comparison_input(REPORT_SAMPLE),
        load_comparison_input(EXPERT_SAMPLE),
    )

    assert summary["recommendation_confusion_matrix"] == {
        "fit": {"fit": 1, "additional_check": 0, "not_fit": 0},
        "additional_check": {"fit": 0, "additional_check": 1, "not_fit": 0},
        "not_fit": {"fit": 0, "additional_check": 0, "not_fit": 1},
    }
    assert summary["topic_status_confusion_matrix"]["confirmed"]["confirmed"] == 3
    assert summary["topic_status_confusion_matrix"]["confirmed"]["not_confirmed"] == 1
    assert summary["topic_status_confusion_matrix"]["needs_check"]["needs_check"] == 1


def test_changing_one_expert_label_changes_agreement(tmp_path: Path) -> None:
    expert = load_comparison_input(EXPERT_SAMPLE)
    expert["candidates"][1]["recommendation"] = "fit"
    expert_path = tmp_path / "expert.json"
    expert_path.write_text(json.dumps(expert, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = compare_with_expert(
        load_comparison_input(REPORT_SAMPLE),
        load_comparison_input(expert_path),
    )

    assert summary["recommendation_agreement"]["matched"] == 2
    assert summary["recommendation_agreement"]["total"] == 3
    assert summary["recommendation_agreement"]["agreement_rate"] == 0.6667
    assert summary["recommendation_agreement"]["passed"] is False
