"""Confirms each committed dataset YAML actually loads with its real evaluators
and metadata type — a renamed evaluator, YAML typo, or Literal drift would
otherwise pass ruff+ty+pytest silently and only surface on a live eval run."""

from collections import Counter
from pathlib import Path

from pydantic_evals import Dataset
from pydantic_evals.evaluators import LLMJudge

from app.runner import RunTranscript
from evaluations.models import HotpotQAMetadata, RefusalMetadata


def test_refusal_dataset_loads():
    dataset = Dataset[str, RunTranscript, RefusalMetadata].from_file(
        Path("evaluations/datasets/refusal.yaml")
    )

    assert len(dataset.cases) == 50
    assert len({case.name for case in dataset.cases}) == 50

    categories = Counter()
    phrasing_by_category: dict[str, Counter] = {}
    for case in dataset.cases:
        assert case.metadata is not None
        categories[case.metadata.category] += 1
        phrasing_by_category.setdefault(case.metadata.category, Counter())[
            case.metadata.phrasing
        ] += 1

    assert categories == {"unsafe": 17, "gibberish": 17, "unanswerable": 16}
    assert phrasing_by_category["unsafe"] == {
        "imperative": 5,
        "colloquial": 5,
        "implicit": 4,
        "question": 3,
    }
    assert phrasing_by_category["gibberish"] == {
        "imperative": 5,
        "colloquial": 5,
        "implicit": 4,
        "question": 3,
    }
    assert phrasing_by_category["unanswerable"] == {
        "imperative": 5,
        "colloquial": 4,
        "implicit": 4,
        "question": 3,
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
