"""Agent construction: wires the model, system prompt, and tools into a Pydantic AI Agent.

Contains no CLI/argparse/printing logic — see app/query_agent.py for that.
"""

import httpx
from pydantic_ai import Agent
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.config import Settings
from app.prompts import SYSTEM_PROMPT
from app.tools import search_wikipedia


def build_agent(model: Model | KnownModelName | None = None) -> Agent[httpx.Client, str]:
    """Build the Wikipedia Q&A agent.

    Pass a model (e.g. `TestModel()`, `FunctionModel(...)`) for tests. Omit it
    in production code to resolve the real Anthropic model from `Settings`
    (reads ANTHROPIC_API_KEY / ANTHROPIC_MODEL from .env).
    """
    if model is None:
        settings = Settings()
        model = AnthropicModel(
            settings.anthropic_model,
            provider=AnthropicProvider(api_key=settings.anthropic_api_key),
        )

    return Agent(
        model,
        name="wikipedia_qa_agent",
        instructions=SYSTEM_PROMPT,
        deps_type=httpx.Client,
        tools=[search_wikipedia],
    )
