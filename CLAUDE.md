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

These are binding constraints on how `app/` code gets structured, not just
style preferences:

- **Clean Code / SOLID.** Small, single-responsibility functions and classes.
  Depend on abstractions at seams that need to be swapped or faked in tests,
  not on concrete I/O clients directly. The `agent.py` / `prompts.py` /
  `tools.py` split is itself an SRP boundary — keep it that way as the
  implementation grows rather than collapsing logic back into one file.
- **Functional core, imperative shell** ([cosmicpython ch. 3](https://www.cosmicpython.com/book/chapter_03_abstractions.html)).
  Keep business logic — deciding what to search for, how to combine search
  results into an answer, eval scoring — as pure functions over plain data
  (dicts, dataclasses, tuples), separate from the I/O shell (real Wikipedia
  HTTP calls, real Anthropic API calls). Reach for a simplifying data
  structure (e.g. a plain `SearchResult`) before reaching for a class
  hierarchy.
- **Carve out a seam for Wikipedia access.** Put the real Wikipedia
  integration behind a small interface (e.g. a `WikipediaClient` protocol
  with a `search(query) -> ...` method) so `app/tools.py` depends on that
  abstraction, not directly on `requests`/MediaWiki specifics. Tests should
  inject a fake implementation rather than `mock.patch`-ing the real one —
  fakes surface design problems that patching hides.
- **Test pyramid: high gear vs. low gear** ([cosmicpython ch. 5](https://www.cosmicpython.com/book/chapter_05_high_gear_low_gear.html)).
  Most tests should sit at the "service layer": running the agent
  edge-to-edge against a fake `WikipediaClient` and Pydantic AI's
  `TestModel`/`FunctionModel` (see `ai:building-pydantic-ai-agents` skill),
  exercising real business-logic edge cases without real network/API calls.
  Keep a small number of true unit tests for pure domain logic fiddly enough
  to want direct coverage, and delete them once service-layer tests cover
  the same ground. Reserve real end-to-end tests (real Anthropic + real
  Wikipedia) for a handful of smoke cases — that's the eval suite's job, not
  the pytest suite's.

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
