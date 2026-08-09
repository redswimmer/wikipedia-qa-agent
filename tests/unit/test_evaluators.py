from pydantic_evals.evaluators import EvaluatorContext
from pydantic_evals.otel import SpanTreeRecordingError

from app.runner import RunTranscript, ToolCallRecord
from evaluations.evaluators import TranscriptWellFormed
from evaluations.models import HotpotQAMetadata


def _ctx(transcript: RunTranscript) -> EvaluatorContext[str, RunTranscript, HotpotQAMetadata]:
    return EvaluatorContext(
        name="test case",
        inputs=transcript.question,
        metadata=HotpotQAMetadata(level="easy", type="bridge", hotpotqa_id="abc123"),
        expected_output=None,
        output=transcript,
        duration=0.1,
        _span_tree=SpanTreeRecordingError("not needed for this evaluator"),
        attributes={},
        metrics={},
    )


def test_well_formed_transcript_passes_both_checks():
    transcript = RunTranscript(
        question="Who was Ada Lovelace?",
        tool_calls=[
            ToolCallRecord(
                tool_name="search_wikipedia",
                args={"query": "Ada Lovelace"},
                result="Ada Lovelace was a mathematician.",
            )
        ],
        answer="Ada Lovelace was an English mathematician.",
    )

    result = TranscriptWellFormed().evaluate_sync(_ctx(transcript))

    assert result == {"answer_non_empty": True, "tool_calls_well_formed": True}


def test_empty_answer_fails_answer_check():
    transcript = RunTranscript(question="Who was Ada Lovelace?", tool_calls=[], answer="   ")

    result = TranscriptWellFormed().evaluate_sync(_ctx(transcript))

    assert result["answer_non_empty"] is False  # type: ignore


def test_empty_tool_call_result_fails_tool_calls_check():
    transcript = RunTranscript(
        question="Who was Ada Lovelace?",
        tool_calls=[ToolCallRecord(tool_name="search_wikipedia", args={"query": "x"}, result="")],
        answer="Ada Lovelace was a mathematician.",
    )

    result = TranscriptWellFormed().evaluate_sync(_ctx(transcript))

    assert result["tool_calls_well_formed"] is False  # type: ignore
