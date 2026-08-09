from app.bootstrap import resolve_real_model
from app.config import Settings


def test_resolve_real_model_uses_settings_model_name():
    settings = Settings(
        anthropic_api_key="fake-key", anthropic_model="claude-opus-5", _env_file=None
    )

    model = resolve_real_model(settings)

    assert model.model_name == "claude-opus-5"
