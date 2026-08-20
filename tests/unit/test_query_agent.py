"""The CLI entrypoint, driven through `main()` with a fake model and transport.

Covers what a user sees: the answer streamed to stdout, tool progress to
stderr, retries surfaced rather than swallowed, and colour only on a terminal.
"""

import json
import sys

import httpx
import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from app import query_agent
from tests.unit.fakes import EXTRACT, TITLE, streaming_model, wikipedia_handler


def _run(capsys, model: Model, transport: httpx.BaseTransport):
    query_agent.main(
        ["Who was Ada Lovelace?"],
        model_factory=lambda: model,
        client_factory=lambda: httpx.Client(transport=transport),
    )
    return capsys.readouterr()


def test_main_streams_the_answer_to_stdout_and_tool_progress_to_stderr(
    capsys, wikipedia_mock_transport
):
    captured = _run(capsys, streaming_model(), wikipedia_mock_transport)

    assert "Answer:" in captured.out
    assert captured.out.count("Answer:") == 1  # header printed once, not per delta
    assert captured.out.strip().endswith(EXTRACT)

    # Progress on stderr only, so `... > answer.txt` captures just the answer.
    assert "Answer:" not in captured.err
    assert "Tool calls:" in captured.err
    assert f"→ search_wikipedia(query='{TITLE}')" in captured.err
    assert f"← {EXTRACT}" in captured.err


def test_main_reports_a_failed_search_as_a_retry_in_the_progress_log(capsys):
    """A search that finds nothing is surfaced to the user rather than silently
    swallowed before the successful retry."""

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if isinstance(messages[-1].parts[-1], RetryPromptPart):
            return ModelResponse(
                parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": TITLE})]
            )
        if len(messages) == 1:
            return ModelResponse(
                parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": "zzz"})]
            )
        return ModelResponse(parts=[TextPart(content=EXTRACT)])

    async def stream(messages: list[ModelMessage], info: AgentInfo):
        part = model(messages, info).parts[0]
        if isinstance(part, ToolCallPart):
            yield {0: DeltaToolCall(name=part.tool_name, json_args=part.args_as_json_str())}
        else:
            yield EXTRACT

    transport = httpx.MockTransport(wikipedia_handler(no_results_for=("zzz",)))
    captured = _run(capsys, FunctionModel(model, stream_function=stream), transport)

    assert "← [retry] No Wikipedia article found" in captured.err
    assert captured.out.strip().endswith(EXTRACT)


@pytest.mark.parametrize("is_terminal", [False, True])
def test_main_colorizes_only_when_the_stream_is_a_terminal(
    capsys, monkeypatch, wikipedia_mock_transport, is_terminal
):
    """Redirected output must stay clean — escape codes would corrupt
    `... > answer.txt` — while an interactive terminal gets the highlighting."""
    if is_terminal:
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        monkeypatch.setattr(sys.stderr, "isatty", lambda: True)

    captured = _run(capsys, streaming_model(), wikipedia_mock_transport)

    assert ("\033[" in captured.out) is is_terminal
    assert ("\033[" in captured.err) is is_terminal


def test_main_exits_with_a_friendly_message_when_the_api_key_is_blank(capsys, monkeypatch):
    """Runs the real Settings -> resolve_real_model chain, so this also covers
    the `min_length=1` guard: a blank key is how an unset key usually arrives,
    and it must fail at startup rather than as a 401 partway through a run. The
    env var beats any .env on disk, so this holds locally and in CI alike."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    with pytest.raises(SystemExit) as exc_info:
        query_agent.main(["irrelevant question"])

    assert exc_info.value.code == 1
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err


def test_main_exits_with_a_friendly_message_when_the_search_cap_trips(capsys):
    """A runaway run must end in a clean error, not a traceback mid-stream."""

    def reword_forever(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        query = f"reworded {len(messages)}"
        return ModelResponse(
            parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": query})]
        )

    async def reword_forever_stream(messages: list[ModelMessage], info: AgentInfo):
        query = f"reworded {len(messages)}"
        yield {0: DeltaToolCall(name="search_wikipedia", json_args=json.dumps({"query": query}))}

    with pytest.raises(SystemExit) as exc_info:
        query_agent.main(
            ["runaway question"],
            model_factory=lambda: FunctionModel(
                reword_forever, stream_function=reword_forever_stream
            ),
            client_factory=lambda: httpx.Client(transport=httpx.MockTransport(wikipedia_handler())),
        )

    assert exc_info.value.code == 1
    assert "too many searches" in capsys.readouterr().err
