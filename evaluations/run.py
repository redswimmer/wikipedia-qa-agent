"""Generic runner: load a dataset by name, run it against the production agent, print the report."""

import argparse
import contextlib
import os
import sys
from pathlib import Path
from typing import Any

import logfire
from pydantic import ValidationError
from pydantic_ai.retries import RetryConfig
from pydantic_evals import Dataset
from tenacity import stop_after_attempt, wait_exponential

from app.config import Settings
from app.runner import RunTranscript
from evaluations import judges
from evaluations.task import production_task

# Local-only unless LOGFIRE_TOKEN is set — required for span-based evaluators
# (e.g. MaxToolCalls) to capture anything; harmless no-op otherwise. Never
# called by the CLI, so plain `query_agent.py` usage is unaffected.
# console=False: we only need the registered tracer for span capture, not
# Logfire's live console span log — with cases running concurrently, those
# lines interleave with the progress bar and render unreadably once captured
# as flat text (e.g. piped to a file or pasted outside a real terminal).
logfire.configure(
    send_to_logfire="if-token-present",
    environment="development",
    service_name="evals",
    console=False,
)
logfire.instrument_pydantic_ai()

DATASETS_DIR = Path(__file__).parent / "datasets"


def _format_transcript(transcript: RunTranscript) -> str:
    """LLMJudge evaluators already grade against this full transcript (see
    app/runner.py); this surfaces the same evidence in the printed report so
    a verdict can be checked by eye instead of via Logfire."""
    sections = [f"Answer:\n{transcript.answer}"]
    if transcript.tool_calls:
        # No square brackets in labels: Rich's Table treats "[...]" as markup
        # and silently drops anything it doesn't recognize as a valid style.
        calls = "\n\n".join(
            f"{call.tool_name} → {call.args.get('query', call.args)!r}:\n{call.result}"
            for call in transcript.tool_calls
        )
        sections.append(f"Tool Calls:\n{calls}")
    return "\n\n".join(sections)


def _export_api_key_for_native_evaluators() -> None:
    """LLMJudge's `model` field always round-trips through YAML as a plain model
    string (pydantic_evals converts any Model instance to its model_id string on
    serialization — there's no way to bake an explicit provider/API key into a
    committed dataset file). At evaluate-time it's resolved via pydantic_ai's
    default provider construction, which reads ANTHROPIC_API_KEY from the process
    environment directly — not through this project's Settings/.env mechanism
    (which app.bootstrap.resolve_real_model uses explicitly for the agent under
    test). Exporting it here, once, is what lets any LLMJudge-based evaluator in
    a dataset file work at all."""
    with contextlib.suppress(
        ValidationError
    ):  # let the real error surface later, from resolve_real_model()
        os.environ.setdefault("ANTHROPIC_API_KEY", Settings().anthropic_api_key.get_secret_value())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run a named eval dataset against the agent.")
    parser.add_argument("dataset_name")
    args = parser.parse_args(argv)

    dataset_path = DATASETS_DIR / f"{args.dataset_name}.yaml"
    if not dataset_path.exists():
        available = ", ".join(sorted(p.stem for p in DATASETS_DIR.glob("*.yaml"))) or "(none found)"
        print(
            f"Error: no dataset named {args.dataset_name!r} "
            f"(expected {dataset_path}).\nAvailable datasets: {available}",
            file=sys.stderr,
        )
        sys.exit(1)

    _export_api_key_for_native_evaluators()

    # Metadata type intentionally loose here: each dataset defines its own metadata
    # model (see evaluations/models.py) and nothing in this generic runner reads
    # metadata fields, so it doesn't need to know which shape a given dataset uses.
    dataset = Dataset[str, RunTranscript, Any].from_file(dataset_path)
    # The LLMJudge evaluators aren't serialized in the YAML: their rubrics live in
    # evaluations/judge_prompts/ so the file a reviewer reads is byte-for-byte the
    # prompt the judge receives. Attached here, keyed by the dataset name that's
    # already this runner's only argument.
    dataset.evaluators.extend(judges.for_dataset(args.dataset_name))
    try:
        with production_task() as answer_question:
            # Unbounded concurrency previously caused 46-50% of answer_quality's 50
            # live cases to fail outright, overwhelming Wikipedia's rate limiter and
            # the agent's own tool-retry budget; max_concurrency=5 keeps concurrent
            # Wikipedia/Anthropic load modest. retry_task and retry_evaluators (same
            # backoff config) retry a failed case's task or LLMJudge calls
            # individually with exponential backoff, rather than losing the whole
            # case to one transient failure.
            retry_config = RetryConfig(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, max=20),
                reraise=True,
            )
            report = dataset.evaluate_sync(
                answer_question,
                max_concurrency=5,
                retry_task=retry_config,
                retry_evaluators=retry_config,
            )
    except ValidationError:
        print(
            "Error: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        sys.exit(1)
    report.print(
        include_input=True,
        include_output=True,
        output_config={"value_formatter": _format_transcript},
        include_reasons=True,
    )


if __name__ == "__main__":
    main()
