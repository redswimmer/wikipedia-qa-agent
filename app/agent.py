"""Wires the system prompt and tools into a Pydantic AI Agent."""

import httpx
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.config import Settings
from app.prompts import SYSTEM_PROMPT
from app.tools import search_wikipedia

agent: Agent[httpx.Client, str] = Agent(
    name="wikipedia_qa_agent",
    instructions=SYSTEM_PROMPT,
    deps_type=httpx.Client,
    tools=[search_wikipedia],
)


def resolve_real_model(settings: Settings | None = None) -> Model:
    """Resolve the real Anthropic model from Settings (.env)."""
    settings = settings or Settings()
    return AnthropicModel(
        settings.anthropic_model,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key.get_secret_value()),
    )
