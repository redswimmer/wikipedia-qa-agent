import asyncio
from typing import cast

import pytest
from pydantic import ValidationError
from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent, RunContext
from pydantic_ai.messages import (
    PartDeltaEvent,
    PartStartEvent,
    RetryPromptPart,
    TextPart,
    TextPartDelta,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import KnownModelName, Model

from app import query_agent


def test_format_progress_line_for_tool_call():
    event = FunctionToolCallEvent(
        part=ToolCallPart(
            tool_name="search_wikipedia", args={"query": "Ada Lovelace"}, tool_call_id="1"
        )
    )

    assert query_agent._format_progress_line(event) == "  → search_wikipedia(query='Ada Lovelace')"


def test_format_progress_line_for_tool_result():
    event = FunctionToolResultEvent(
        part=ToolReturnPart(
            tool_name="search_wikipedia",
            content="Ada Lovelace was a mathematician.",
            tool_call_id="1",
        )
    )

    assert query_agent._format_progress_line(event) == "  ← Ada Lovelace was a mathematician."


def test_format_progress_line_for_retried_tool_result():
    event = FunctionToolResultEvent(
        part=RetryPromptPart(
            tool_name="search_wikipedia", content="No article found", tool_call_id="1"
        )
    )

    assert query_agent._format_progress_line(event) == "  ← [retry] No article found"


def test_format_progress_line_for_unrelated_event_is_none():
    event = PartStartEvent(index=0, part=TextPart(content="hi"))

    assert query_agent._format_progress_line(event) is None


def test_text_delta_extracts_content_from_text_part_delta():
    event = PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Ada Love"))

    assert query_agent._text_delta(event) == "Ada Love"


def test_text_delta_extracts_initial_content_from_part_start_event():
    event = PartStartEvent(index=0, part=TextPart(content="Ada Lovelace (born"))

    assert query_agent._text_delta(event) == "Ada Lovelace (born"


def test_text_delta_for_part_start_event_with_tool_call_part_is_none():
    event = PartStartEvent(
        index=0, part=ToolCallPart(tool_name="search_wikipedia", args={}, tool_call_id="1")
    )

    assert query_agent._text_delta(event) is None


def test_text_delta_for_unrelated_event_is_none():
    event = FunctionToolCallEvent(
        part=ToolCallPart(tool_name="search_wikipedia", args={}, tool_call_id="1")
    )

    assert query_agent._text_delta(event) is None


def test_print_progress_streams_text_deltas_to_stdout_and_tool_events_to_stderr(capsys):
    events = [
        FunctionToolCallEvent(
            part=ToolCallPart(
                tool_name="search_wikipedia", args={"query": "Ada Lovelace"}, tool_call_id="1"
            )
        ),
        PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Ada")),
        PartDeltaEvent(index=0, delta=TextPartDelta(content_delta=" Lovelace")),
    ]

    async def event_stream():
        for event in events:
            yield event

    asyncio.run(query_agent._print_progress(cast(RunContext, None), event_stream()))

    captured = capsys.readouterr()
    assert captured.out == "\nAnswer:\nAda Lovelace"
    assert captured.err == "Tool calls:\n  → search_wikipedia(query='Ada Lovelace')\n"


def test_main_exits_with_friendly_message_when_api_key_missing(capsys):
    def raise_validation_error() -> Model | KnownModelName:
        raise ValidationError.from_exception_data(
            "Settings", [{"type": "missing", "loc": ("anthropic_api_key",), "input": {}}]
        )

    with pytest.raises(SystemExit) as exc_info:
        query_agent.main(["irrelevant question"], model_factory=raise_validation_error)

    assert exc_info.value.code == 1
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err
