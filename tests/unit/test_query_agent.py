"""The CLI entrypoint, driven through `main()` with a fake model and transport.

Previously ten tests asserted on `_progress_parts`/`_text_delta`/`_colorize`
directly, because `main()` hardcoded its Wikipedia client and the happy path
was untestable. With `client_factory` injectable, two edge-to-edge tests cover
the same branches and additionally prove the CLI's output routing.
"""

import httpx
import pytest
from pydantic import ValidationError
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models import KnownModelName, Model
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


def test_colorize_wraps_text_in_ansi_code_when_enabled():
    """The only branch the edge-to-edge tests can't reach: capsys is never a tty,
    so `main()` always takes the colors-disabled path."""
    assert query_agent._colorize("hi", "\033[2m", enabled=True) == "\033[2mhi\033[0m"


def test_main_exits_with_friendly_message_when_api_key_missing(capsys):
    def raise_validation_error() -> Model | KnownModelName:
        raise ValidationError.from_exception_data(
            "Settings", [{"type": "missing", "loc": ("anthropic_api_key",), "input": {}}]
        )

    with pytest.raises(SystemExit) as exc_info:
        query_agent.main(["irrelevant question"], model_factory=raise_validation_error)

    assert exc_info.value.code == 1
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err
