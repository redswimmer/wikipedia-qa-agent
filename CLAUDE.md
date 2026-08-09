# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

An Anthropic take-home assignment: build a question-answering system that uses
Claude plus a `search_wikipedia(query: str)` tool, and an eval suite that
measures how well it works. Full spec: `docs/assignment_instructions.md`. Key
constraint from that spec — no built-in hosted search/RAG tools (e.g.
Anthropic's `web_search` tool type); the retrieval integration must be
hand-built.

## Commands

```bash
uv sync                          # install deps
uv run pre-commit install        # one-time: wire up git hooks

uv run ruff check .              # lint
uv run ruff format .             # format
uv run ty check                  # type check
uv run pytest                    # full test suite
uv run pytest tests/unit/test_app_imports.py::test_app_modules_import  # single test
uv run pre-commit run --all-files  # run every quality gate without committing

uv run python -m app.agent "your question"  # ask a question
uv run python -m app.agent --demo           # run built-in sample questions
```

Every commit runs ruff (lint + format), `ty`, and pytest via pre-commit; the
same checks run in CI (`.github/workflows/ci.yml`). A hook failure blocks the
commit — fix and re-commit rather than bypassing it.

**Workspace note:** this project is a member of a `uv` workspace rooted two
directories up (`development/pyproject.toml`, `[tool.uv.workspace]`). `uv
sync`/`uv run` here resolve against that shared workspace environment and
lockfile, not an isolated venv.

## Design principles

Guiding constraints for how code in this repo should be shaped — apply
judgment about what they mean concretely once the actual design takes shape;
don't treat any specific class/module name below as prescribed. See
[`docs/architecture-notes.md`](docs/architecture-notes.md) for a fuller,
offline summary of the cosmicpython chapters referenced below.

- **Clean Code / SOLID.** Small, single-responsibility units. Depend on
  abstractions at seams that need to be swapped or faked in tests, not on
  concrete I/O clients directly.
- **Functional core, imperative shell** ([cosmicpython ch. 3](https://www.cosmicpython.com/book/chapter_03_abstractions.html)).
  Keep business logic as pure functions over plain data, separate from the
  I/O shell (network/API calls). Favor a simplifying data structure over a
  class hierarchy when one will do.
- **Fakes over patches.** Put I/O integrations behind an abstraction so tests
  can inject a fake implementation rather than `mock.patch`-ing the real
  one — fakes surface design problems that patching hides.
- **Test pyramid: high gear vs. low gear** ([cosmicpython ch. 5](https://www.cosmicpython.com/book/chapter_05_high_gear_low_gear.html)).
  Most tests should sit at the service layer — edge-to-edge, with fakes
  standing in for I/O — exercising business-logic edge cases without real
  network/API calls. Keep a small core of true unit tests for pure logic
  fiddly enough to want direct coverage. Reserve real end-to-end runs for a
  handful of smoke cases.

## Architecture

- `app/agent.py`, `app/prompts.py`, `app/tools.py` — the agent split into
  wiring, system instructions, and tool implementations respectively. Built
  on [Pydantic AI](https://ai.pydantic.dev); see the `ai:building-pydantic-ai-agents`
  skill for framework patterns (tool registration, structured output,
  `TestModel`, etc.) rather than re-deriving them here.
- `tests/unit/test_app_imports.py` is currently a smoke test only (import-time
  check on the three `app` modules) — the real eval suite (deliverable #3 of
  the assignment) still needs to be built out.
- `pyproject.toml` sets `pythonpath = ["."]` under `[tool.pytest.ini_options]`.
  This is required: `app/` has no `__init__.py`/package install, so without it
  pytest's default import mode can't resolve `app.*` imports even though a
  plain `python -c "import app.agent"` from the repo root works fine.
- Anthropic API key is read from `.env` (see `.env.example` for the variable
  name); `.env` is gitignored.
- README.md is consumer-facing (setup + usage for someone running the
  prototype); CONTRIBUTING.md is contributor-facing (dev environment, quality
  gates). Keep that split when adding docs.
