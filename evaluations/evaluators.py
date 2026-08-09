"""Evaluators for grading agent runs. Grows by addition as new eval purposes are added."""

from dataclasses import dataclass

from pydantic_evals.evaluators import Evaluator, EvaluatorContext, EvaluatorOutput

from app.runner import RunTranscript
from evaluations.models import HotpotQAMetadata


@dataclass
class TranscriptWellFormed(Evaluator[str, RunTranscript, HotpotQAMetadata]):
    """Structural smoke check only — not correctness, faithfulness, or
    whether search was used. Those are separate future datasets.

    `tool_calls_well_formed` is `all(...)` over `transcript.tool_calls`, which
    is vacuously `True` when the agent made no tool calls at all -- this
    evaluator does not check whether search happened in the first place, only
    that any calls that did happen are well-formed. Whether search was used
    (relevancy) is explicitly out of scope here; see the design doc's "Out of
    scope" section."""

    def evaluate(
        self, ctx: EvaluatorContext[str, RunTranscript, HotpotQAMetadata]
    ) -> EvaluatorOutput:
        transcript = ctx.output
        return {
            "answer_non_empty": bool(transcript.answer.strip()),
            "tool_calls_well_formed": all(
                call.tool_name.strip() and str(call.result).strip()
                for call in transcript.tool_calls
            ),
        }


CUSTOM_EVALUATOR_TYPES = (TranscriptWellFormed,)
