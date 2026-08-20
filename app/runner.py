"""Runs a question through the agent and builds an auditable transcript from
Pydantic AI's own message history.
"""

from collections.abc import AsyncIterable, Awaitable, Callable
from typing import Any

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent, AgentRunResult, AgentStreamEvent, RunContext
from pydantic_ai.messages import RetryPromptPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.usage import UsageLimits

# Hard ceiling on searches per run. The 2026-08-10 eval runs put every
# legitimate multi-hop case at <=7 tool calls while the one pathological case
# spiraled to 59-76 ($1.01-$1.52, up to 15 minutes; see evaluations/results/).
# 8 leaves legitimate runs headroom while a spiral fails in seconds instead.
DEFAULT_USAGE_LIMITS = UsageLimits(tool_calls_limit=8)


class ToolCallRecord(BaseModel):
    tool_name: str
    args: dict[str, Any]
    result: str


class RunTranscript(BaseModel):
    question: str
    tool_calls: list[ToolCallRecord]
    answer: str


def run_agent(
    agent: Agent[httpx.Client, str],
    question: str,
    deps: httpx.Client,
    model: Model | KnownModelName,
    usage_limits: UsageLimits = DEFAULT_USAGE_LIMITS,
) -> RunTranscript:
    """Raises whatever the underlying agent run raises (e.g. `UnexpectedModelBehavior`
    when tool retries are exhausted, `UsageLimitExceeded` past `usage_limits`) —
    callers decide how to handle failure."""
    result = agent.run_sync(question, deps=deps, model=model, usage_limits=usage_limits)
    return _build_transcript(question, result)


async def run_agent_streaming(
    agent: Agent[httpx.Client, str],
    question: str,
    deps: httpx.Client,
    model: Model | KnownModelName,
    event_stream_handler: Callable[[RunContext, AsyncIterable[AgentStreamEvent]], Awaitable[None]],
    usage_limits: UsageLimits = DEFAULT_USAGE_LIMITS,
) -> RunTranscript:
    """Same as `run_agent()`, but drives the run through `agent.run()` so
    `event_stream_handler` receives tool-call/result events as they happen.
    Raises whatever the underlying agent run raises, same as `run_agent()`."""
    result = await agent.run(
        question,
        deps=deps,
        model=model,
        event_stream_handler=event_stream_handler,
        usage_limits=usage_limits,
    )
    return _build_transcript(question, result)


def _build_transcript(question: str, result: AgentRunResult[str]) -> RunTranscript:
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
            elif isinstance(part, RetryPromptPart):
                call = calls_by_id.get(part.tool_call_id)
                if call is not None:
                    tool_calls.append(
                        ToolCallRecord(
                            tool_name=call.tool_name,
                            args=call.args_as_dict(),
                            result=f"[retry] {part.content}",
                        )
                    )

    return RunTranscript(question=question, tool_calls=tool_calls, answer=str(result.output))
