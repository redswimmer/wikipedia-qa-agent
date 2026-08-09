"""Environment-driven settings for the agent: which Anthropic API key and model to use."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    anthropic_api_key: SecretStr = Field(min_length=1)
    anthropic_model: str = "claude-sonnet-5"
