"""Only the choices this project made — pydantic's own required-field and
env-reading behaviour isn't retested here."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_rejects_empty_api_key(monkeypatch):
    """`min_length=1` is a deliberate addition: an empty string is how an unset
    key usually arrives, and it would otherwise sail through to a 401."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_has_a_model_default_and_honours_an_override(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    assert Settings(
        _env_file=None
    ).anthropic_model  # a default exists; its value is a config choice

    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-5")

    assert Settings(_env_file=None).anthropic_model == "claude-opus-5"
