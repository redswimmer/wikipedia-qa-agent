"""CLI entrypoint: ask the agent one question, print an auditable report."""

import argparse
import asyncio
import sys
from collections.abc import AsyncIterable, Callable, Sequence

from pydantic import ValidationError
from pydantic_ai import AgentStreamEvent, FunctionToolCallEvent, FunctionToolResultEvent, RunContext
from pydantic_ai.messages import (
    PartDeltaEvent,
    PartStartEvent,
    RetryPromptPart,
    TextPart,
    TextPartDelta,
)
from pydantic_ai.models import KnownModelName, Model

from app.agent import agent
from app.bootstrap import resolve_real_model
from app.runner import run_agent_streaming
from app.tools import build_wikipedia_client


def _format_progress_line(event: AgentStreamEvent) -> str | None:
    if isinstance(event, FunctionToolCallEvent):
        args_str = ", ".join(f"{k}={v!r}" for k, v in event.part.args_as_dict().items())
        return f"  → {event.part.tool_name}({args_str})"
    if isinstance(event, FunctionToolResultEvent):
        if isinstance(event.part, RetryPromptPart):
            return f"  ← [retry] {event.part.content}"
        return f"  ← {event.part.content}"
    return None


def _text_delta(event: AgentStreamEvent) -> str | None:
    if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
        return event.part.content
    if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
        return event.delta.content_delta
    return None


async def _print_progress(ctx: RunContext, events: AsyncIterable[AgentStreamEvent]) -> None:
    tool_calls_started = False
    answer_started = False
    async for event in events:
        delta = _text_delta(event)
        if delta is not None:
            if not answer_started:
                print("\nAnswer:")
                answer_started = True
            print(delta, end="", flush=True)
            continue
        line = _format_progress_line(event)
        if line is not None:
            if not tool_calls_started:
                print("Tool calls:", file=sys.stderr)
                tool_calls_started = True
            print(line, file=sys.stderr)


def main(
    argv: Sequence[str] | None = None,
    *,
    model_factory: Callable[[], Model | KnownModelName] = resolve_real_model,
) -> None:
    parser = argparse.ArgumentParser(description="Ask the Wikipedia Q&A agent a question.")
    parser.add_argument("question")
    args = parser.parse_args(argv)

    try:
        model = model_factory()
    except ValidationError:
        print(
            "Error: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        sys.exit(1)

    with build_wikipedia_client() as client:
        asyncio.run(
            run_agent_streaming(
                agent,
                args.question,
                deps=client,
                model=model,
                event_stream_handler=_print_progress,
            )
        )

    print()


if __name__ == "__main__":
    main()
