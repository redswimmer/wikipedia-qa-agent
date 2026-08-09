import httpx
import pytest
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.agent import build_agent
from app.runner import run_agent


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
    agent = build_agent(FunctionModel(_search_then_answer))

    with httpx.Client(transport=wikipedia_mock_transport) as client:
        transcript = run_agent(agent, "Who was Ada Lovelace?", deps=client)

    assert transcript.question == "Who was Ada Lovelace?"
    assert len(transcript.tool_calls) == 1
    assert transcript.tool_calls[0].tool_name == "search_wikipedia"
    assert transcript.tool_calls[0].args == {"query": "Ada Lovelace"}
    assert transcript.tool_calls[0].result == "Ada Lovelace was a mathematician."
    assert transcript.answer == "Ada Lovelace was a mathematician."


def test_run_agent_with_no_tool_call_has_empty_tool_calls(wikipedia_mock_transport):
    agent = build_agent(FunctionModel(_answer_without_searching))

    with httpx.Client(transport=wikipedia_mock_transport) as client:
        transcript = run_agent(agent, "What is 2 + 2?", deps=client)

    assert transcript.tool_calls == []
    assert transcript.answer == "4"


def test_run_agent_propagates_exhausted_retries():
    agent = build_agent(FunctionModel(_always_fail_search))

    with (
        pytest.raises(UnexpectedModelBehavior),
        httpx.Client(transport=httpx.MockTransport(_fake_no_results_transport)) as client,
    ):
        run_agent(agent, "Who is nobody?", deps=client)
