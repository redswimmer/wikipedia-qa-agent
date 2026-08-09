"""Smoke tests that catch import-time errors in the app and evaluations packages."""

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


def test_evaluations_modules_import():
    for module in (
        "evaluations.models",
        "evaluations.evaluators",
        "evaluations.task",
        "evaluations.run",
    ):
        importlib.import_module(module)
