"""Composition root: resolves real production dependencies"""

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.config import Settings


def resolve_real_model(settings: Settings | None = None) -> Model:
    """Resolve the real Anthropic model from Settings (.env)."""
    settings = settings or Settings()
    return AnthropicModel(
        settings.anthropic_model,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key.get_secret_value()),
    )
