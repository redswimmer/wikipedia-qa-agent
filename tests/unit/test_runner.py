"""`run_agent`/`run_agent_streaming` driven edge-to-edge through the real agent
with a fake model and transport.

These assert the auditability contract: the transcript must record what the
model actually did, including the calls that failed.
"""

import asyncio

import httpx
import pytest
from pydantic_ai import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RunContext,
    UnexpectedModelBehavior,
)
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.agent import agent
from app.runner import run_agent, run_agent_streaming
from tests.unit.conftest import (
    EXTRACT,
    TITLE,
    MediaWiki,
    search_then_answer,
    streaming_model,
)


def _search(query: str) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": query})])


def _answer_without_searching(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content="4")])


def _always_search(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return _search("nonexistent")


def _search_then_give_up(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Answers once the tool has pushed back, so the retry lands in the transcript
    instead of the run dying on an exhausted retry budget."""
    if isinstance(messages[-1].parts[-1], RetryPromptPart):
        return ModelResponse(parts=[TextPart(content="I couldn't retrieve that.")])
    return _search("anything")


def test_run_agent_records_tool_call_and_answer(wikipedia_mock_transport):
    with httpx.Client(transport=wikipedia_mock_transport) as client:
        transcript = run_agent(
            agent, "Who was Ada Lovelace?", deps=client, model=FunctionModel(search_then_answer)
        )

    assert transcript.question == "Who was Ada Lovelace?"
    assert len(transcript.tool_calls) == 1
    assert transcript.tool_calls[0].tool_name == "search_wikipedia"
    assert transcript.tool_calls[0].args == {"query": TITLE}
    assert transcript.tool_calls[0].result == EXTRACT
    assert transcript.answer == EXTRACT


def test_run_agent_with_no_tool_call_has_empty_tool_calls(wikipedia_mock_transport):
    """No fabricated records when the model answers directly."""
    with httpx.Client(transport=wikipedia_mock_transport) as client:
        transcript = run_agent(
            agent, "What is 2 + 2?", deps=client, model=FunctionModel(_answer_without_searching)
        )

    assert transcript.tool_calls == []
    assert transcript.answer == "4"


def test_run_agent_propagates_exhausted_retries():
    """Callers decide how to handle failure, so the error isn't swallowed."""
    with (
        pytest.raises(UnexpectedModelBehavior),
        httpx.Client(transport=httpx.MockTransport(lambda _: MediaWiki.search())) as client,
    ):
        run_agent(agent, "Who is nobody?", deps=client, model=FunctionModel(_always_search))


def test_run_agent_records_a_rate_limit_as_a_retry_the_model_can_read():
    """A 429 must reach the model as a ModelRetry it can act on — not an
    HTTPStatusError that kills the run — and must be visible in the transcript."""
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(429, json={}))) as c:
        transcript = run_agent(
            agent, "who knows", deps=c, model=FunctionModel(_search_then_give_up)
        )

    assert (
        transcript.tool_calls[0].result == "[retry] Wikipedia returned 429; try again in a moment."
    )
    assert transcript.answer == "I couldn't retrieve that."


def test_run_agent_records_failed_retry_before_successful_call():
    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if isinstance(messages[-1].parts[-1], RetryPromptPart):
            return _search(TITLE)
        if len(messages) == 1:
            return _search("nonexistent")
        return ModelResponse(parts=[TextPart(content=EXTRACT)])

    def handler(request: httpx.Request) -> httpx.Response:
        if MediaWiki.is_search(request):
            return (
                MediaWiki.search()
                if "srsearch=nonexistent" in str(request.url)
                else MediaWiki.search(TITLE)
            )
        return MediaWiki.extract(EXTRACT)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transcript = run_agent(
            agent, "Who was Ada Lovelace?", deps=client, model=FunctionModel(model)
        )

    assert [c.args["query"] for c in transcript.tool_calls] == ["nonexistent", TITLE]
    assert transcript.tool_calls[0].result.startswith("[retry]")
    assert transcript.tool_calls[1].result == EXTRACT


def test_run_agent_streaming_records_the_same_transcript_and_emits_events(wikipedia_mock_transport):
    received: list[AgentStreamEvent] = []

    async def collect(ctx: RunContext, events) -> None:
        async for event in events:
            received.append(event)

    async def run():
        with httpx.Client(transport=wikipedia_mock_transport) as client:
            return await run_agent_streaming(
                agent,
                "Who was Ada Lovelace?",
                deps=client,
                model=streaming_model(),
                event_stream_handler=collect,
            )

    transcript = asyncio.run(run())

    assert [c.tool_name for c in transcript.tool_calls] == ["search_wikipedia"]
    assert transcript.tool_calls[0].result == EXTRACT
    assert transcript.answer == EXTRACT
    assert [e.part.tool_name for e in received if isinstance(e, FunctionToolCallEvent)] == [
        "search_wikipedia"
    ]
    assert len([e for e in received if isinstance(e, FunctionToolResultEvent)]) == 1
