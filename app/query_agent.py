"""CLI entrypoint: ask the agent one question, print an auditable report."""

import argparse
import sys
from collections.abc import Callable, Sequence

import httpx
from pydantic import ValidationError
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.agent import agent
from app.config import Settings
from app.runner import RunTranscript, run_agent
from app.tools import WIKIPEDIA_USER_AGENT


def _resolve_real_model() -> Model | KnownModelName:
    """Resolve the real Anthropic model from Settings (.env)."""
    settings = Settings()
    return AnthropicModel(
        settings.anthropic_model,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key.get_secret_value()),
    )


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
    model_factory: Callable[[], Model | KnownModelName] = _resolve_real_model,
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

    with httpx.Client(headers={"User-Agent": WIKIPEDIA_USER_AGENT}, timeout=30.0) as client:
        transcript = run_agent(agent, args.question, deps=client, model=model)

    print(format_transcript(transcript))


if __name__ == "__main__":
    main()
