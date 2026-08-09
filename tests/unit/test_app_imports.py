"""Smoke tests that catch import-time errors in the app package."""

import importlib


def test_app_modules_import():
    for module in ("app.agent", "app.prompts", "app.tools"):
        importlib.import_module(module)
