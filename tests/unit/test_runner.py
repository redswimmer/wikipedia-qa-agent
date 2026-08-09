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
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from app.agent import agent
from app.runner import run_agent, run_agent_streaming


def _search_then_answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    if len(messages) == 1:
        return ModelResponse(
            parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": "Ada Lovelace"})]
        )
    return ModelResponse(parts=[TextPart(content="Ada Lovelace was a mathematician.")])


def _answer_without_searching(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content="4")])


def _always_fail_search(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return ModelResponse(
        parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": "nonexistent"})]
    )


def _fake_no_results_transport(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"query": {"search": []}})


def test_run_agent_records_tool_call_and_answer(wikipedia_mock_transport):
    with httpx.Client(transport=wikipedia_mock_transport) as client:
        transcript = run_agent(
            agent, "Who was Ada Lovelace?", deps=client, model=FunctionModel(_search_then_answer)
        )

    assert transcript.question == "Who was Ada Lovelace?"
    assert len(transcript.tool_calls) == 1
    assert transcript.tool_calls[0].tool_name == "search_wikipedia"
    assert transcript.tool_calls[0].args == {"query": "Ada Lovelace"}
    assert transcript.tool_calls[0].result == "Ada Lovelace was a mathematician."
    assert transcript.answer == "Ada Lovelace was a mathematician."


def test_run_agent_with_no_tool_call_has_empty_tool_calls(wikipedia_mock_transport):
    with httpx.Client(transport=wikipedia_mock_transport) as client:
        transcript = run_agent(
            agent, "What is 2 + 2?", deps=client, model=FunctionModel(_answer_without_searching)
        )

    assert transcript.tool_calls == []
    assert transcript.answer == "4"


def test_run_agent_propagates_exhausted_retries():
    with (
        pytest.raises(UnexpectedModelBehavior),
        httpx.Client(transport=httpx.MockTransport(_fake_no_results_transport)) as client,
    ):
        run_agent(agent, "Who is nobody?", deps=client, model=FunctionModel(_always_fail_search))


def _always_search(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": "x"})])


def _rate_limited_transport(request: httpx.Request) -> httpx.Response:
    return httpx.Response(429, json={})


def test_run_agent_treats_429_as_retry_not_crash():
    with (
        pytest.raises(UnexpectedModelBehavior),
        httpx.Client(transport=httpx.MockTransport(_rate_limited_transport)) as client,
    ):
        run_agent(agent, "who knows", deps=client, model=FunctionModel(_always_search))


def _search_fails_then_succeeds(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    last_part = messages[-1].parts[-1]
    if isinstance(last_part, RetryPromptPart):
        return ModelResponse(
            parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": "Ada Lovelace"})]
        )
    if len(messages) == 1:
        return ModelResponse(
            parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": "nonexistent"})]
        )
    return ModelResponse(parts=[TextPart(content="Ada Lovelace was a mathematician.")])


def _fake_transport_fails_once_then_succeeds(request: httpx.Request) -> httpx.Response:
    if "srsearch=nonexistent" in str(request.url):
        return httpx.Response(200, json={"query": {"search": []}})
    if "list=search" in str(request.url):
        return httpx.Response(200, json={"query": {"search": [{"title": "Ada Lovelace"}]}})
    return httpx.Response(
        200, json={"query": {"pages": {"1": {"extract": "Ada Lovelace was a mathematician."}}}}
    )


def test_run_agent_records_failed_retry_before_successful_call():
    with httpx.Client(
        transport=httpx.MockTransport(_fake_transport_fails_once_then_succeeds)
    ) as client:
        transcript = run_agent(
            agent,
            "Who was Ada Lovelace?",
            deps=client,
            model=FunctionModel(_search_fails_then_succeeds),
        )

    assert len(transcript.tool_calls) == 2
    assert transcript.tool_calls[0].tool_name == "search_wikipedia"
    assert transcript.tool_calls[0].args == {"query": "nonexistent"}
    assert transcript.tool_calls[0].result.startswith("[retry]")
    assert transcript.tool_calls[1].tool_name == "search_wikipedia"
    assert transcript.tool_calls[1].args == {"query": "Ada Lovelace"}
    assert transcript.tool_calls[1].result == "Ada Lovelace was a mathematician."


async def _search_then_answer_stream(messages: list[ModelMessage], info: AgentInfo):
    if len(messages) == 1:
        yield {0: DeltaToolCall(name="search_wikipedia", json_args='{"query": "Ada Lovelace"}')}
    else:
        yield "Ada Lovelace was a mathematician."


def test_run_agent_streaming_records_tool_call_and_answer_and_emits_events(
    wikipedia_mock_transport,
):
    received: list[AgentStreamEvent] = []

    async def collect(ctx: RunContext, events) -> None:
        async for event in events:
            received.append(event)

    async def run() -> None:
        with httpx.Client(transport=wikipedia_mock_transport) as client:
            transcript = await run_agent_streaming(
                agent,
                "Who was Ada Lovelace?",
                deps=client,
                model=FunctionModel(
                    _search_then_answer, stream_function=_search_then_answer_stream
                ),
                event_stream_handler=collect,
            )

        assert transcript.question == "Who was Ada Lovelace?"
        assert len(transcript.tool_calls) == 1
        assert transcript.tool_calls[0].tool_name == "search_wikipedia"
        assert transcript.tool_calls[0].result == "Ada Lovelace was a mathematician."
        assert transcript.answer == "Ada Lovelace was a mathematician."

    asyncio.run(run())

    call_events = [e for e in received if isinstance(e, FunctionToolCallEvent)]
    result_events = [e for e in received if isinstance(e, FunctionToolResultEvent)]
    assert len(call_events) == 1
    assert call_events[0].part.tool_name == "search_wikipedia"
    assert len(result_events) == 1
