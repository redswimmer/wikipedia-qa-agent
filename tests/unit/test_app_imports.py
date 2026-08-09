"""Smoke tests that catch import-time errors in the app package."""

import importlib


def test_app_modules_import():
    for module in (
        "app.config",
        "app.tools",
        "app.prompts",
        "app.agent",
        "app.runner",
        "app.query_agent",
    ):
        importlib.import_module(module)
