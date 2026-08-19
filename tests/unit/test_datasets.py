"""Each committed dataset YAML loads with its real metadata model and evaluators.

Assertions here deliberately describe *properties* of a dataset, not its exact
census: pinning per-category counts means adding a good case fails the suite,
which trains you to update the numbers reflexively until they guard nothing.
"""

from collections import Counter

import pytest
from pydantic_evals import Dataset
from pydantic_evals.evaluators import MaxToolCalls

from app.runner import RunTranscript
from evaluations.models import HotpotQAMetadata, RefusalMetadata
from evaluations.run import DATASETS_DIR

# Resolved from the production constant, so these tests pass from any cwd.
REFUSAL = DATASETS_DIR / "refusal.yaml"
ANSWER_QUALITY = DATASETS_DIR / "answer_quality.yaml"


@pytest.mark.parametrize("path", [REFUSAL, ANSWER_QUALITY])
def test_dataset_case_names_are_unique(path):
    """Duplicate names make a report ambiguous about which case failed."""
    dataset = Dataset[str, RunTranscript, dict].from_file(path)

    assert dataset.cases
    assert len({case.name for case in dataset.cases}) == len(dataset.cases)


def test_refusal_dataset_covers_every_refusal_category_and_phrasing():
    dataset = Dataset[str, RunTranscript, RefusalMetadata].from_file(REFUSAL)

    categories = Counter(case.metadata.category for case in dataset.cases if case.metadata)
    phrasings = Counter(case.metadata.phrasing for case in dataset.cases if case.metadata)

    assert set(categories) == {"unsafe", "gibberish", "unanswerable"}
    assert set(phrasings) == {"imperative", "colloquial", "implicit", "question"}
    # Roughly balanced, so no single category can dominate the headline score.
    assert min(categories.values()) >= len(dataset.cases) // 5


def test_refusal_dataset_forbids_any_tool_call():
    """The dataset's entire pass criterion. Raise this above 0 and the refusal
    eval silently stops testing refusal."""
    dataset = Dataset[str, RunTranscript, RefusalMetadata].from_file(REFUSAL)

    budgets = [e.max_calls for e in dataset.evaluators if isinstance(e, MaxToolCalls)]

    assert budgets == [0]


def test_answer_quality_dataset_is_hard_hotpotqa_with_gold_answers():
    dataset = Dataset[str, RunTranscript, HotpotQAMetadata].from_file(ANSWER_QUALITY)

    for case in dataset.cases:
        assert case.metadata is not None
        assert case.metadata.level == "hard"
        # An empty gold answer would pass the correctness judge silently.
        assert isinstance(case.expected_output, RunTranscript)
        assert case.expected_output.answer.strip()


def test_answer_quality_dataset_budgets_tool_calls():
    dataset = Dataset[str, RunTranscript, HotpotQAMetadata].from_file(ANSWER_QUALITY)

    budgets = [e.max_calls for e in dataset.evaluators if isinstance(e, MaxToolCalls)]

    assert budgets and budgets[0] > 0
