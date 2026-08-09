"""Generic runner: load a dataset by name, run it against the production agent, print the report."""

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError
from pydantic_evals import Dataset

from app.runner import RunTranscript
from evaluations.evaluators import CUSTOM_EVALUATOR_TYPES
from evaluations.models import HotpotQAMetadata
from evaluations.task import production_task

DATASETS_DIR = Path(__file__).parent / "datasets"


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

    dataset = Dataset[str, RunTranscript, HotpotQAMetadata].from_file(
        dataset_path, custom_evaluator_types=CUSTOM_EVALUATOR_TYPES
    )
    try:
        with production_task() as answer_question:
            report = dataset.evaluate_sync(answer_question)
    except ValidationError:
        print(
            "Error: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        sys.exit(1)
    report.print()


if __name__ == "__main__":
    main()
