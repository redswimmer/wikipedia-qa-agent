"""Runs a question through the agent and builds an auditable transcript from
Pydantic AI's own message history — no hand-rolled tool-call tracking.
"""

from typing import Any

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent, AgentRunResult
from pydantic_ai.messages import ToolCallPart, ToolReturnPart


class ToolCallRecord(BaseModel):
    tool_name: str
    args: dict[str, Any]
    result: str


class RunTranscript(BaseModel):
    question: str
    tool_calls: list[ToolCallRecord]
    answer: str


def run_agent(agent: Agent[httpx.Client, str], question: str, deps: httpx.Client) -> RunTranscript:
    """Run `question` through `agent` and return an auditable transcript.

    Raises whatever the underlying agent run raises (e.g. `UnexpectedModelBehavior`
    when tool retries are exhausted) — callers decide how to handle failure.
    """
    result = agent.run_sync(question, deps=deps)
    return _build_transcript(question, result)


def _build_transcript(question: str, result: AgentRunResult) -> RunTranscript:
    calls_by_id: dict[str, ToolCallPart] = {}
    tool_calls: list[ToolCallRecord] = []

    for message in result.new_messages():
        for part in message.parts:
            if isinstance(part, ToolCallPart):
                calls_by_id[part.tool_call_id] = part
            elif isinstance(part, ToolReturnPart):
                call = calls_by_id.get(part.tool_call_id)
                if call is not None:
                    tool_calls.append(
                        ToolCallRecord(
                            tool_name=call.tool_name,
                            args=call.args_as_dict(),
                            result=str(part.content),
                        )
                    )

    return RunTranscript(question=question, tool_calls=tool_calls, answer=str(result.output))
