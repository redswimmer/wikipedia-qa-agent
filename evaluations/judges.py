"""LLM-as-judge evaluators, built at load time from `evaluations/rubrics/*.md`.

Each rubric lives in its own markdown file whose entire content *is* the prompt
string the judge receives — so the file a reviewer reads is byte-for-byte what
the judge is sent. That's why the files are read verbatim here (no strip, no
templating) and why they carry no headings or fences of their own.
"""

from pathlib import Path

from pydantic_evals.evaluators import LLMJudge

RUBRICS_DIR = Path(__file__).parent / "rubrics"

# Judging is done by Opus while the agent under test runs Sonnet, to reduce
# self-grading bias. Round-trips through pydantic_evals as a plain model string,
# resolved from ANTHROPIC_API_KEY in the environment (see run.py).
JUDGE_MODEL = "anthropic:claude-opus-5"

# `safety` is deliberately shared: an unsafe response is a failure whether the
# agent answered or declined.
_DATASET_JUDGES = {
    "refusal": ["refusal_quality", "safety"],
    "answer_quality": ["safety", "faithfulness", "relevance", "correctness"],
}


def _judge(name: str) -> LLMJudge:
    return LLMJudge(
        rubric=(RUBRICS_DIR / f"{name}.md").read_text(),
        model=JUDGE_MODEL,
        include_input=True,
        # Only correctness grades against a gold answer; the others judge the
        # response on its own terms (or against the retrieved evidence).
        include_expected_output=name == "correctness",
        assertion={"include_reason": True, "evaluation_name": name},
    )


def for_dataset(name: str) -> list[LLMJudge]:
    """The judges a named dataset is graded by. Unknown dataset -> no judges."""
    return [_judge(rubric) for rubric in _DATASET_JUDGES.get(name, [])]
