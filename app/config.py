"""Environment-driven settings for the agent: which Anthropic API key and model to use."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-5"
