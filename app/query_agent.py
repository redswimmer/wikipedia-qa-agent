"""CLI entrypoint: ask the agent one question, print an auditable report.

This is the only module in app/ with argparse/printing/CLI-specific error
handling. It depends on app.agent and app.runner; nothing else depends on it.
"""

import argparse
import sys
from collections.abc import Callable, Sequence

import httpx
from pydantic import ValidationError
from pydantic_ai import Agent

from app.agent import build_agent
from app.runner import RunTranscript, run_agent
from app.tools import WIKIPEDIA_USER_AGENT


def format_transcript(transcript: RunTranscript) -> str:
    lines = [f"Question: {transcript.question}", ""]

    if transcript.tool_calls:
        lines.append("Tool calls:")
        for i, call in enumerate(transcript.tool_calls, start=1):
            args_str = ", ".join(f"{k}={v!r}" for k, v in call.args.items())
            lines.append(f"  {i}. {call.tool_name}({args_str})")
            lines.append(f"     → {call.result}")
        lines.append("")

    lines.append("Answer:")
    lines.append(transcript.answer)
    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None,
    *,
    agent_factory: Callable[[], Agent[httpx.Client, str]] = build_agent,
) -> None:
    parser = argparse.ArgumentParser(description="Ask the Wikipedia Q&A agent a question.")
    parser.add_argument("question")
    args = parser.parse_args(argv)

    try:
        agent = agent_factory()
    except ValidationError:
        print(
            "Error: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        sys.exit(1)

    with httpx.Client(headers={"User-Agent": WIKIPEDIA_USER_AGENT}) as client:
        transcript = run_agent(agent, args.question, deps=client)

    print(format_transcript(transcript))


if __name__ == "__main__":
    main()
