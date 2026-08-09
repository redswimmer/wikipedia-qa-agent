import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_defaults_model_when_unset(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key == "test-key"
    assert settings.anthropic_model == "claude-sonnet-5"


def test_settings_reads_model_override(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-5")

    settings = Settings(_env_file=None)

    assert settings.anthropic_model == "claude-opus-5"
