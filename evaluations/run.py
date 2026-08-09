"""Generic runner: load a dataset by name, run it against the production agent, print the report."""

import argparse
from pathlib import Path

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
    dataset = Dataset[str, RunTranscript, HotpotQAMetadata].from_file(
        dataset_path, custom_evaluator_types=CUSTOM_EVALUATOR_TYPES
    )
    with production_task() as answer_question:
        report = dataset.evaluate_sync(answer_question)
    report.print()


if __name__ == "__main__":
    main()
