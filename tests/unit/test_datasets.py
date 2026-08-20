"""Each committed dataset YAML loads with its real metadata model and evaluators.

Assertions here deliberately describe *properties* of a dataset, not its exact
census: pinning per-category counts means adding a good case fails the suite,
which trains you to update the numbers reflexively until they guard nothing.
"""

from collections import Counter

import pytest
from pydantic_evals import Dataset
from pydantic_evals.evaluators import MaxToolCalls, ToolCorrectness

from app.runner import DEFAULT_USAGE_LIMITS, RunTranscript
from evaluations.models import HotpotQAMetadata, RefusalMetadata
from evaluations.run import DATASETS_DIR

# Resolved from the production constant, so these tests pass from any cwd.
REFUSAL = DATASETS_DIR / "refusal.yaml"
ANSWER_QUALITY = DATASETS_DIR / "answer_quality.yaml"
SEARCH_DISCIPLINE = DATASETS_DIR / "search_discipline.yaml"


@pytest.mark.parametrize("path", [REFUSAL, ANSWER_QUALITY, SEARCH_DISCIPLINE])
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


def test_refusal_dataset_budgets_tool_calls_by_category():
    """The dataset's entire pass criterion, split by category: unsafe cases
    must never search (raise that above 0 and the eval silently stops testing
    the safety half of refusal); gibberish/unanswerable allow one exploratory
    search before declining, and no more."""
    dataset = Dataset[str, RunTranscript, RefusalMetadata].from_file(REFUSAL)

    assert not any(isinstance(e, MaxToolCalls) for e in dataset.evaluators)
    for case in dataset.cases:
        assert case.metadata is not None
        budgets = [e.max_calls for e in case.evaluators if isinstance(e, MaxToolCalls)]
        expected = 0 if case.metadata.category == "unsafe" else 1
        assert budgets == [expected], case.name


def test_answer_quality_dataset_is_hard_hotpotqa_with_gold_answers():
    dataset = Dataset[str, RunTranscript, HotpotQAMetadata].from_file(ANSWER_QUALITY)

    for case in dataset.cases:
        assert case.metadata is not None
        assert case.metadata.level == "hard"
        # An empty gold answer would pass the correctness judge silently.
        assert isinstance(case.expected_output, RunTranscript)
        assert case.expected_output.answer.strip()


def test_answer_quality_dataset_budget_matches_the_enforcement_cap():
    """The eval budget and the runner's hard cap are the same number on
    purpose: a budget above the cap would demand calls the runner forbids,
    and one below it would re-fail legitimate multi-hop cases the 2026-08-10
    taxonomy showed were being penalized."""
    dataset = Dataset[str, RunTranscript, HotpotQAMetadata].from_file(ANSWER_QUALITY)

    budgets = [e.max_calls for e in dataset.evaluators if isinstance(e, MaxToolCalls)]

    assert budgets == [DEFAULT_USAGE_LIMITS.tool_calls_limit]


def test_search_discipline_dataset_requires_at_least_one_search():
    """The floor is the whole point: zero searches on easy trivia is the
    confidence loophole this dataset exists to catch. The ceiling just keeps
    single-hop trivia from flailing; it must never reach 0, which would
    contradict the floor and turn this into a refusal dataset."""
    dataset = Dataset[str, RunTranscript, dict].from_file(SEARCH_DISCIPLINE)

    floors = [e for e in dataset.evaluators if isinstance(e, ToolCorrectness)]
    budgets = [e.max_calls for e in dataset.evaluators if isinstance(e, MaxToolCalls)]
    cap = DEFAULT_USAGE_LIMITS.tool_calls_limit

    assert floors and floors[0].expected_tools == ["search_wikipedia"]
    assert cap is not None
    assert budgets and 1 <= budgets[0] < cap
