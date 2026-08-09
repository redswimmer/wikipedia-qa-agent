import pytest
from pydantic import ValidationError
from pydantic_ai.models import KnownModelName, Model

from app import query_agent
from app.runner import RunTranscript, ToolCallRecord


def test_format_transcript_includes_question_tool_calls_and_answer():
    transcript = RunTranscript(
        question="What is the capital of France?",
        tool_calls=[
            ToolCallRecord(
                tool_name="search_wikipedia",
                args={"query": "capital of France"},
                result="Paris is the capital and largest city of France...",
            )
        ],
        answer="Paris is the capital of France.",
    )

    output = query_agent.format_transcript(transcript)

    assert "Question: What is the capital of France?" in output
    assert "search_wikipedia(query='capital of France')" in output
    assert "Paris is the capital and largest city of France..." in output
    assert "Answer:" in output
    assert output.strip().endswith("Paris is the capital of France.")


def test_main_exits_with_friendly_message_when_api_key_missing(capsys):
    def raise_validation_error() -> Model | KnownModelName:
        raise ValidationError.from_exception_data(
            "Settings", [{"type": "missing", "loc": ("anthropic_api_key",), "input": {}}]
        )

    with pytest.raises(SystemExit) as exc_info:
        query_agent.main(["irrelevant question"], model_factory=raise_validation_error)

    assert exc_info.value.code == 1
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err
