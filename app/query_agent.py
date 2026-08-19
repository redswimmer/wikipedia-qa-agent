"""CLI entrypoint: ask the agent one question, print an auditable report."""

import argparse
import asyncio
import sys
from collections.abc import AsyncIterable, Callable, Sequence

import httpx
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

_YELLOW = "\033[33m"
_BOLD_CYAN = "\033[1;36m"
_RESET = "\033[0m"


def _colorize(text: str, code: str, *, enabled: bool) -> str:
    return f"{code}{text}{_RESET}" if enabled else text


def _progress_parts(event: AgentStreamEvent) -> tuple[str, str] | None:
    if isinstance(event, FunctionToolCallEvent):
        args_str = ", ".join(f"{k}={v!r}" for k, v in event.part.args_as_dict().items())
        return "→", f"{event.part.tool_name}({args_str})"
    if isinstance(event, FunctionToolResultEvent):
        if isinstance(event.part, RetryPromptPart):
            return "←", f"[retry] {event.part.content}"
        return "←", str(event.part.content)
    return None


def _text_delta(event: AgentStreamEvent) -> str | None:
    if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
        return event.part.content
    if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
        return event.delta.content_delta
    return None


async def _print_progress(ctx: RunContext, events: AsyncIterable[AgentStreamEvent]) -> None:
    stdout_color = sys.stdout.isatty()
    stderr_color = sys.stderr.isatty()
    tool_calls_started = False
    answer_started = False
    async for event in events:
        delta = _text_delta(event)
        if delta is not None:
            if not answer_started:
                print(_colorize("\nAnswer:", _BOLD_CYAN, enabled=stdout_color))
                answer_started = True
            print(delta, end="", flush=True)
            continue
        parts = _progress_parts(event)
        if parts is not None:
            if not tool_calls_started:
                print(_colorize("Tool calls:", _YELLOW, enabled=stderr_color), file=sys.stderr)
                tool_calls_started = True
            arrow, rest = parts
            print(f"  {_colorize(arrow, _YELLOW, enabled=stderr_color)} {rest}", file=sys.stderr)


def main(
    argv: Sequence[str] | None = None,
    *,
    model_factory: Callable[[], Model | KnownModelName] = resolve_real_model,
    client_factory: Callable[[], httpx.Client] = build_wikipedia_client,
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

    with client_factory() as client:
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
