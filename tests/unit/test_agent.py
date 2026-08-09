import httpx
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.test import TestModel

from app.agent import agent
from app.tools import WIKIPEDIA_USER_AGENT


def test_agent_registers_search_wikipedia_tool(wikipedia_mock_transport):
    with httpx.Client(
        transport=wikipedia_mock_transport,
        headers={"User-Agent": WIKIPEDIA_USER_AGENT},
    ) as client:
        result = agent.run_sync("Who was Ada Lovelace?", deps=client, model=TestModel())

    tool_calls = [
        part
        for message in result.new_messages()
        for part in message.parts
        if isinstance(part, ToolCallPart)
    ]
    assert len(tool_calls) == 1
    assert tool_calls[0].tool_name == "search_wikipedia"
