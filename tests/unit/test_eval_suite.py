"""Wiring of the eval suite: which judges each dataset is graded by, and the
single task entrypoint every case runs through.

Nothing here calls the API. These are the mistakes that produce a confident,
all-green report rather than a visible failure.
"""

import httpx
import pytest
from pydantic_ai.models.function import FunctionModel
from pydantic_evals.evaluators import LLMJudge

from app.config import Settings
from evaluations import judges
from evaluations.run import DATASETS_DIR
from evaluations.task import production_task
from tests.unit.fakes import EXTRACT, TITLE, search_then_answer


def _names(evaluators: list[LLMJudge]) -> set[str]:
    """`assertion` is `bool | dict`; every judge here configures the dict form."""
    return {e.assertion["evaluation_name"] for e in evaluators if isinstance(e.assertion, dict)}


@pytest.mark.parametrize(
    ("dataset", "expected"),
    [
        ("refusal", {"refusal_quality", "safety"}),
        ("answer_quality", {"safety", "faithfulness", "relevance", "correctness"}),
    ],
)
def test_each_dataset_gets_its_rubrics_and_they_exist_on_disk(dataset, expected):
    """Building an LLMJudge reads its rubric file, so this also proves every
    referenced judge_prompts/*.md is present — otherwise the first evidence is a
    FileNotFoundError partway through a billed live run."""
    evaluators = judges.for_dataset(dataset)

    assert _names(evaluators) == expected
    assert all(e.rubric.strip() for e in evaluators)


def test_every_committed_dataset_has_judges_configured():
    """`for_dataset` returns [] for a name it doesn't know, so a dataset added
    without a `_DATASET_JUDGES` entry grades with zero judges and reports a
    clean sweep — the worst failure mode an eval harness has. Asserting the bare
    [] contract wouldn't catch that; walking the committed datasets does."""
    datasets = sorted(DATASETS_DIR.glob("*.yaml"))

    assert datasets
    for path in datasets:
        assert judges.for_dataset(path.stem), f"{path.name} has no judges configured"


def test_only_correctness_judges_against_the_gold_answer():
    """If every judge saw the expected output, faithfulness and relevance would
    stop measuring the retrieved evidence — silent eval-validity corruption."""
    graded_against_gold = _names(
        [e for e in judges.for_dataset("answer_quality") if e.include_expected_output]
    )

    assert graded_against_gold == {"correctness"}


def test_judge_model_differs_from_the_agent_default_to_avoid_self_grading():
    agent_model = Settings(anthropic_api_key="fake-key", _env_file=None).anthropic_model
    judge_model = judges.JUDGE_MODEL.split(":", 1)[-1]  # strip the "anthropic:" prefix

    assert agent_model != judge_model


def test_production_task_runs_a_question_through_the_real_agent(wikipedia_mock_transport):
    """The one entrypoint all eval cases use. Its deps are injectable purely so
    this can be asserted without an API key."""
    with (
        httpx.Client(transport=wikipedia_mock_transport) as client,
        production_task(model=FunctionModel(search_then_answer), client=client) as answer,
    ):
        transcript = answer("Who was Ada Lovelace?")

    assert transcript.question == "Who was Ada Lovelace?"
    assert [c.tool_name for c in transcript.tool_calls] == ["search_wikipedia"]
    assert transcript.tool_calls[0].args == {"query": TITLE}
    assert transcript.answer == EXTRACT


def test_production_task_leaves_an_injected_client_open_for_its_owner(wikipedia_mock_transport):
    client = httpx.Client(transport=wikipedia_mock_transport)
    with production_task(model=FunctionModel(search_then_answer), client=client):
        pass

    assert not client.is_closed
    client.close()
