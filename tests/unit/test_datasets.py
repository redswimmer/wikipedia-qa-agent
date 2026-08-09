"""Confirms each committed dataset YAML actually loads with its real evaluators
and metadata type — a renamed evaluator, YAML typo, or Literal drift would
otherwise pass ruff+ty+pytest silently and only surface on a live eval run."""

from collections import Counter
from pathlib import Path

from pydantic_evals import Dataset
from pydantic_evals.evaluators import LLMJudge

from app.runner import RunTranscript
from evaluations.evaluators import CUSTOM_EVALUATOR_TYPES
from evaluations.models import HotpotQAMetadata, RefusalMetadata


def test_format_validation_dataset_loads():
    dataset = Dataset[str, RunTranscript, HotpotQAMetadata].from_file(
        Path("evaluations/datasets/format_validation.yaml"),
        custom_evaluator_types=CUSTOM_EVALUATOR_TYPES,
    )
    levels = []
    for case in dataset.cases:
        assert case.metadata is not None
        levels.append(case.metadata.level)
    assert levels == ["easy", "medium", "hard"]


def test_refusal_dataset_loads():
    dataset = Dataset[str, RunTranscript, RefusalMetadata].from_file(
        Path("evaluations/datasets/refusal.yaml")
    )

    assert len(dataset.cases) == 30
    assert len({case.name for case in dataset.cases}) == 30

    categories = Counter()
    phrasing_by_category: dict[str, Counter] = {}
    for case in dataset.cases:
        assert case.metadata is not None
        categories[case.metadata.category] += 1
        phrasing_by_category.setdefault(case.metadata.category, Counter())[
            case.metadata.phrasing
        ] += 1

    assert categories == {"unsafe": 10, "gibberish": 10, "unanswerable": 10}
    for category_counts in phrasing_by_category.values():
        assert category_counts == {
            "imperative": 3,
            "colloquial": 3,
            "implicit": 2,
            "question": 2,
        }


def test_wikipedia_answer_quality_dataset_loads():
    dataset = Dataset[str, RunTranscript, HotpotQAMetadata].from_file(
        Path("evaluations/datasets/wikipedia_answer_quality.yaml")
    )

    assert len(dataset.cases) == 50
    assert len({case.name for case in dataset.cases}) == 50

    for case in dataset.cases:
        assert case.metadata is not None
        assert case.metadata.level == "hard"
        assert isinstance(case.expected_output, RunTranscript)
        assert case.expected_output.answer != ""

    assert len(dataset.evaluators) == 6
    judge_names = {
        e.assertion.get("evaluation_name")
        for e in dataset.evaluators
        if isinstance(e, LLMJudge) and e.assertion
    }
    assert judge_names == {"safety", "faithfulness", "relevance", "correctness"}
