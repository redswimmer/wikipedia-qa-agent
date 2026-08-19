"""The CLI entrypoint, driven through `main()` with a fake model and transport.

Ten tests used to assert on `_progress_parts`/`_text_delta`/`_colorize`
directly: with only `model_factory` injectable, any path where the model called
a tool would hit live Wikipedia, so the display logic was reachable only from
below. With `client_factory` too, these cover the same branches through the
real entrypoint and additionally pin the output routing and colour rules.
"""

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
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from app import query_agent
from tests.unit.conftest import EXTRACT, TITLE, MediaWiki, streaming_model


def _run(capsys, model, transport):
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

    # Answer on stdout, under a single header, with the deltas in order.
    assert "Answer:" in captured.out
    assert captured.out.count("Answer:") == 1
    assert captured.out.strip().endswith(EXTRACT)

    # Tool progress on stderr only, so `... > answer.txt` captures just the answer.
    assert "Answer:" not in captured.err
    assert "Tool calls:" in captured.err
    assert f"→ search_wikipedia(query='{TITLE}')" in captured.err
    assert f"← {EXTRACT}" in captured.err


def test_main_reports_a_failed_search_as_a_retry_in_the_progress_log(capsys):
    """The `RetryPromptPart` branch: a search that finds nothing is surfaced to
    the user rather than silently swallowed before the successful retry."""

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
        response = model(messages, info)
        part = response.parts[0]
        if isinstance(part, ToolCallPart):
            yield {0: DeltaToolCall(name=part.tool_name, json_args=part.args_as_json_str())}
        else:
            yield EXTRACT

    def handler(request: httpx.Request) -> httpx.Response:
        if MediaWiki.is_search(request):
            return (
                MediaWiki.search()
                if "srsearch=zzz" in str(request.url)
                else MediaWiki.search(TITLE)
            )
        return MediaWiki.extract(EXTRACT)

    captured = _run(
        capsys, FunctionModel(model, stream_function=stream), httpx.MockTransport(handler)
    )

    assert "← [retry] No Wikipedia article found" in captured.err
    assert captured.out.strip().endswith(EXTRACT)


def test_main_colorizes_only_when_the_stream_is_a_terminal(
    capsys, monkeypatch, wikipedia_mock_transport
):
    """Redirected output must stay clean — escape codes would corrupt
    `... > answer.txt` — while an interactive terminal gets the highlighting."""
    piped = _run(capsys, streaming_model(), wikipedia_mock_transport)

    assert "\033[" not in piped.out
    assert "\033[" not in piped.err

    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    colored = _run(capsys, streaming_model(), wikipedia_mock_transport)

    assert "\033[" in colored.out
    assert "\033[" in colored.err


def test_main_exits_with_a_friendly_message_when_the_api_key_is_blank(capsys, monkeypatch):
    """Runs the real Settings -> resolve_real_model chain, so it also covers the
    `min_length=1` guard: a blank key is how an unset key usually arrives, and
    it must fail at startup rather than as a 401 partway through a run. The env
    var takes precedence over any .env on disk, so this holds locally and in CI."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    with pytest.raises(SystemExit) as exc_info:
        query_agent.main(["irrelevant question"])

    assert exc_info.value.code == 1
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err
