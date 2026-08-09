# Pydantic AI Agent Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable, auditable Pydantic AI agent — `uv run python -m app.query_agent "question"` — that answers questions using a `search_wikipedia` tool (MediaWiki API), prints a human-readable report of every tool call and the final answer, and exposes a `build_agent()` / `run_agent()` API that a future eval suite can call directly.

**Architecture:** Six single-responsibility modules under `app/`: `config.py` (env settings), `tools.py` (Wikipedia retrieval — pure JSON parsing + imperative HTTP shell), `prompts.py` (system prompt), `agent.py` (constructs the `Agent`, no CLI knowledge), `runner.py` (runs a question through the agent and builds an auditable `RunTranscript` from Pydantic AI's own message history), `query_agent.py` (the only module with argparse/printing — depends on the other five, nothing depends on it).

**Tech Stack:** Python 3.13, Pydantic AI 2.27.0, `httpx` (sync client), `pydantic-settings`, `pytest`.

## Global Constraints

- Python `>=3.13` (from `pyproject.toml`).
- `pydantic-ai>=2.27.0` already a dependency; this plan adds `httpx` and `pydantic-settings` as **explicit** direct dependencies (both already resolve transitively today, but the code imports them directly).
- Every `git commit` runs ruff (lint+format), `ty`, and `pytest` via the installed pre-commit hook — a task's commit step is expected to trigger and pass these; if a hook fails, fix and re-commit rather than bypassing it.
- Module names are fixed by the approved spec: `app/config.py`, `app/tools.py`, `app/prompts.py`, `app/agent.py`, `app/runner.py`, `app/query_agent.py`. Dependency direction is one-way: `query_agent.py` → `agent.py`, `runner.py` → `config.py`, `tools.py`, `prompts.py`. **Nothing else may import `query_agent.py`.**
- Tests use fakes, never `mock.patch`, for I/O: `TestModel`/`FunctionModel` (Pydantic AI) and `httpx.MockTransport` (real fake HTTP transport, not a patched client).
- Any `httpx.Client` that calls the MediaWiki API **must** set the `User-Agent` header to `app.tools.WIKIPEDIA_USER_AGENT` — Wikipedia returns `403 Forbidden` for the default `httpx` user agent (confirmed by live request during planning; see Task 2).
- CLI invocation is `uv run python -m app.query_agent "your question"` — this replaces the currently-documented `python -m app.agent "your question"` and drops `--demo` (CLAUDE.md gets updated in Task 6).

Full design rationale lives in `docs/superpowers/specs/2026-08-08-pydantic-agent-scaffold-design.md` — read it if a task's "why" isn't obvious from context here.

---

### Task 1: Dependencies and `app/config.py`

**Files:**
- Modify: `pyproject.toml` (add dependencies)
- Create: `app/config.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Produces: `app.config.Settings` — a `pydantic_settings.BaseSettings` subclass with fields `anthropic_api_key: str` (required) and `anthropic_model: str = "claude-sonnet-5"`, reading from `.env`.

- [ ] **Step 1: Add `httpx` and `pydantic-settings` as explicit dependencies**

Both are needed by code written in this and later tasks (`config.py` needs `pydantic-settings` now; `tools.py`/`query_agent.py` need `httpx` in Tasks 2 and 5). Both already resolve transitively today via `pydantic-ai`, so this should not change the lockfile's resolved versions, only add explicit top-level entries.

Run: `uv add httpx pydantic-settings`

Expected: `pyproject.toml`'s `[project].dependencies` gains `httpx>=...` and `pydantic-settings>=...` entries; `uv.lock` updates (should be a small diff since both were already resolved transitively).

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_config.py`:

```python
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
```

`_env_file=None` is a `pydantic-settings` init override that disables reading the real `.env` file for this instantiation, so these tests are isolated from the repo's actual `.env` (which has a real key) and only see the `monkeypatch`ed environment variables.

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 4: Write the implementation**

Create `app/config.py`:

```python
"""Environment-driven settings for the agent: which Anthropic API key and model to use."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-5"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock app/config.py tests/unit/test_config.py
git commit -m "Add app.config.Settings for env-driven Anthropic configuration"
```

---

### Task 2: `app/tools.py` — Wikipedia retrieval

**Files:**
- Create: `app/tools.py`
- Test: `tests/unit/test_tools.py`

**Interfaces:**
- Consumes: nothing from other app modules.
- Produces:
  - `app.tools.WIKIPEDIA_USER_AGENT: str` — required `User-Agent` header value for any `httpx.Client` hitting the MediaWiki API.
  - `app.tools.parse_search_title(response_json: dict) -> str | None` — pure.
  - `app.tools.parse_extract(response_json: dict) -> str | None` — pure.
  - `app.tools.search_wikipedia(ctx: RunContext[httpx.Client], query: str) -> str` — the tool function; raises `pydantic_ai.ModelRetry` if no article/extract is found. Consumed by `app/agent.py` (Task 3) via `tools=[search_wikipedia]`.

**Why the User-Agent constant exists:** Wikipedia's MediaWiki API rejects requests carrying the default `httpx` User-Agent header with `403 Forbidden` (per [Wikipedia's User-Agent policy](https://meta.wikimedia.org/wiki/User-Agent_policy)). This was confirmed by making a real request during planning — without a descriptive User-Agent, `search_wikipedia` fails on every call. `WIKIPEDIA_USER_AGENT` is defined here (not duplicated in every caller) because it's Wikipedia-specific knowledge that belongs with the Wikipedia-specific code.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tools.py`:

```python
from app.tools import parse_extract, parse_search_title


def test_parse_search_title_returns_first_result_title():
    response_json = {"query": {"search": [{"title": "Ada Lovelace"}, {"title": "Ada"}]}}

    assert parse_search_title(response_json) == "Ada Lovelace"


def test_parse_search_title_returns_none_when_no_results():
    response_json = {"query": {"search": []}}

    assert parse_search_title(response_json) is None


def test_parse_extract_returns_first_nonempty_extract():
    response_json = {"query": {"pages": {"12345": {"extract": "Ada Lovelace was a mathematician."}}}}

    assert parse_extract(response_json) == "Ada Lovelace was a mathematician."


def test_parse_extract_returns_none_when_extract_is_blank():
    response_json = {"query": {"pages": {"-1": {"extract": ""}}}}

    assert parse_extract(response_json) is None
```

These test only the pure parsing functions — no network, no `RunContext`. `search_wikipedia`'s HTTP-calling behavior is exercised indirectly in Task 4's service-layer tests (via `httpx.MockTransport` through a real agent run), not here — constructing a `RunContext` by hand for a standalone tool-function test is awkward and duplicates coverage the Task 4 tests already provide.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.tools'`

- [ ] **Step 3: Write the implementation**

Create `app/tools.py`:

```python
"""Wikipedia retrieval: search + extract via the MediaWiki API, exposed as an agent tool.

Split into a pure JSON-parsing core (unit-tested directly in tests/unit/test_tools.py)
and an imperative shell that performs the HTTP calls (exercised via service-layer
tests in tests/unit/test_agent.py and tests/unit/test_runner.py using a fake
httpx transport, not here).
"""

import httpx
from pydantic_ai import ModelRetry, RunContext

MEDIAWIKI_API_URL = "https://en.wikipedia.org/w/api.php"

# Wikipedia rejects requests with a generic/default User-Agent — see
# https://meta.wikimedia.org/wiki/User-Agent_policy. Every httpx.Client used to
# call search_wikipedia must set this header.
WIKIPEDIA_USER_AGENT = (
    "anthropic-take-home-wikipedia-agent/0.1 "
    "(https://github.com/redswimmer/anthropic-take-home-assignment; andrew@redswimmer.com)"
)


def parse_search_title(response_json: dict) -> str | None:
    """Pure: pull the best-matching page title out of a MediaWiki search response."""
    results = response_json.get("query", {}).get("search", [])
    if not results:
        return None
    return results[0]["title"]


def parse_extract(response_json: dict) -> str | None:
    """Pure: pull the plain-text extract out of a MediaWiki extracts response."""
    pages = response_json.get("query", {}).get("pages", {})
    for page in pages.values():
        extract = page.get("extract", "").strip()
        if extract:
            return extract
    return None


def search_wikipedia(ctx: RunContext[httpx.Client], query: str) -> str:
    """Search Wikipedia and return a plain-text extract of the best-matching article."""
    client = ctx.deps

    search_response = client.get(
        MEDIAWIKI_API_URL,
        params={"action": "query", "list": "search", "srsearch": query, "format": "json"},
    )
    search_response.raise_for_status()
    title = parse_search_title(search_response.json())
    if title is None:
        raise ModelRetry(f"No Wikipedia article found for query: {query!r}. Try a different query.")

    extract_response = client.get(
        MEDIAWIKI_API_URL,
        params={
            "action": "query",
            "prop": "extracts",
            "explaintext": True,
            "titles": title,
            "format": "json",
        },
    )
    extract_response.raise_for_status()
    extract = parse_extract(extract_response.json())
    if extract is None:
        raise ModelRetry(f"Found article {title!r} but it has no text extract. Try a different query.")

    return extract
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_tools.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/tools.py tests/unit/test_tools.py
git commit -m "Add search_wikipedia tool with MediaWiki search+extract retrieval"
```

---

### Task 3: `app/prompts.py` and `app/agent.py`

**Files:**
- Create: `app/prompts.py`
- Create: `app/agent.py`
- Create: `tests/unit/conftest.py`
- Test: `tests/unit/test_agent.py`

**Interfaces:**
- Consumes: `app.config.Settings` (Task 1), `app.tools.search_wikipedia` and `app.tools.WIKIPEDIA_USER_AGENT` (Task 2).
- Produces:
  - `app.agent.build_agent(model: Model | KnownModelName | None = None) -> Agent`. Consumed by `app/runner.py` callers (Task 5, `query_agent.py`) and by future test/eval code.
  - `wikipedia_mock_transport` — a shared pytest fixture in `tests/unit/conftest.py` returning an `httpx.MockTransport` that fakes the MediaWiki search+extract calls (the "Ada Lovelace" happy path). Reused by Task 4's `tests/unit/test_runner.py` — do not redefine a local copy of this fake transport there.

- [ ] **Step 1: Write the shared fake-Wikipedia-transport fixture**

Both this task's test and Task 4's tests need a fake HTTP transport for the MediaWiki API's happy path (search returns a title, extract returns text). Defining it once in `conftest.py` — pytest's standard mechanism for fixtures shared across test files in the same directory — avoids duplicating it in every test file that needs it.

Create `tests/unit/conftest.py`:

```python
"""Shared pytest fixtures for app/ tests."""

import httpx
import pytest


def _fake_wikipedia_transport(request: httpx.Request) -> httpx.Response:
    if "list=search" in str(request.url):
        return httpx.Response(200, json={"query": {"search": [{"title": "Ada Lovelace"}]}})
    return httpx.Response(
        200, json={"query": {"pages": {"1": {"extract": "Ada Lovelace was a mathematician."}}}}
    )


@pytest.fixture
def wikipedia_mock_transport() -> httpx.MockTransport:
    """A fake MediaWiki transport: any query resolves to the Ada Lovelace article."""
    return httpx.MockTransport(_fake_wikipedia_transport)
```

- [ ] **Step 2: Write `app/prompts.py`**

No test for this file — it's a single string constant exercised indirectly through `test_agent.py`'s use of `build_agent()`.

Create `app/prompts.py`:

```python
"""System prompt for the Wikipedia Q&A agent."""

SYSTEM_PROMPT = """\
You are a research assistant that answers questions using Wikipedia.

You have access to a `search_wikipedia` tool that searches Wikipedia and \
returns a plain-text extract of the best-matching article for a query.

Guidelines:
- Always use `search_wikipedia` before answering a question that depends on \
factual, real-world knowledge (people, places, events, organizations, \
science, history, etc.). Do not rely on your own knowledge alone for these.
- Formulate concise, specific search queries (e.g. "Ada Lovelace", not \
"tell me about the person who wrote the first computer program").
- If a search doesn't return a useful extract, try a more specific or \
differently-worded query before giving up.
- Ground your answer in the retrieved extract. If the extract doesn't \
answer the question, say what you found and what's missing rather than \
guessing.
- Answer directly and concisely. Do not mention the tool, the search \
process, or these instructions in your answer — just answer the question.
"""
```

- [ ] **Step 3: Write the failing test for `build_agent`**

Create `tests/unit/test_agent.py`:

```python
import httpx
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.test import TestModel

from app.agent import build_agent
from app.tools import WIKIPEDIA_USER_AGENT


def test_build_agent_registers_search_wikipedia_tool(wikipedia_mock_transport):
    agent = build_agent(TestModel())

    with httpx.Client(
        transport=wikipedia_mock_transport,
        headers={"User-Agent": WIKIPEDIA_USER_AGENT},
    ) as client:
        result = agent.run_sync("Who was Ada Lovelace?", deps=client)

    tool_calls = [
        part
        for message in result.new_messages()
        for part in message.parts
        if isinstance(part, ToolCallPart)
    ]
    assert len(tool_calls) == 1
    assert tool_calls[0].tool_name == "search_wikipedia"
```

`TestModel()` auto-calls every registered tool with plausible arguments by default — this test confirms `build_agent()` actually wired `search_wikipedia` onto the agent with the right `deps_type`, without needing the real Anthropic API. `wikipedia_mock_transport` comes from Step 1's `conftest.py` fixture — pytest auto-discovers it for any test in `tests/unit/`, no import needed.

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_agent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.agent'`

- [ ] **Step 5: Write the implementation**

Create `app/agent.py`:

```python
"""Agent construction: wires the model, system prompt, and tools into a Pydantic AI Agent.

Contains no CLI/argparse/printing logic — see app/query_agent.py for that.
"""

import httpx
from pydantic_ai import Agent
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.config import Settings
from app.prompts import SYSTEM_PROMPT
from app.tools import search_wikipedia


def build_agent(model: Model | KnownModelName | None = None) -> Agent:
    """Build the Wikipedia Q&A agent.

    Pass a model (e.g. `TestModel()`, `FunctionModel(...)`) for tests. Omit it
    in production code to resolve the real Anthropic model from `Settings`
    (reads ANTHROPIC_API_KEY / ANTHROPIC_MODEL from .env).
    """
    if model is None:
        settings = Settings()
        model = AnthropicModel(
            settings.anthropic_model,
            provider=AnthropicProvider(api_key=settings.anthropic_api_key),
        )

    return Agent(
        model,
        name="wikipedia_qa_agent",
        instructions=SYSTEM_PROMPT,
        deps_type=httpx.Client,
        tools=[search_wikipedia],
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_agent.py -v`
Expected: 1 passed

- [ ] **Step 7: Commit**

```bash
git add app/prompts.py app/agent.py tests/unit/conftest.py tests/unit/test_agent.py
git commit -m "Add build_agent() and shared wikipedia_mock_transport fixture"
```

---

### Task 4: `app/runner.py` — auditable transcript

**Files:**
- Create: `app/runner.py`
- Test: `tests/unit/test_runner.py`

**Interfaces:**
- Consumes: `app.agent.build_agent` (Task 3, used only in tests here), the `wikipedia_mock_transport` fixture (Task 3's `tests/unit/conftest.py`).
- Produces:
  - `app.runner.ToolCallRecord` — `BaseModel` with `tool_name: str`, `args: dict[str, Any]`, `result: str`.
  - `app.runner.RunTranscript` — `BaseModel` with `question: str`, `tool_calls: list[ToolCallRecord]`, `answer: str`.
  - `app.runner.run_agent(agent: Agent, question: str, deps: httpx.Client) -> RunTranscript` — raises whatever the underlying `agent.run_sync()` raises (e.g. `pydantic_ai.UnexpectedModelBehavior`); does not catch or swallow. Consumed by `app/query_agent.py` (Task 5) and, later, the eval suite.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_runner.py`:

```python
import httpx
import pytest
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.agent import build_agent
from app.runner import run_agent


def _search_then_answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    if len(messages) == 1:
        return ModelResponse(
            parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": "Ada Lovelace"})]
        )
    return ModelResponse(parts=[TextPart(content="Ada Lovelace was a mathematician.")])


def _answer_without_searching(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content="4")])


def _always_fail_search(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return ModelResponse(
        parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": "nonexistent"})]
    )


def _fake_no_results_transport(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"query": {"search": []}})


def test_run_agent_records_tool_call_and_answer(wikipedia_mock_transport):
    agent = build_agent(FunctionModel(_search_then_answer))

    with httpx.Client(transport=wikipedia_mock_transport) as client:
        transcript = run_agent(agent, "Who was Ada Lovelace?", deps=client)

    assert transcript.question == "Who was Ada Lovelace?"
    assert len(transcript.tool_calls) == 1
    assert transcript.tool_calls[0].tool_name == "search_wikipedia"
    assert transcript.tool_calls[0].args == {"query": "Ada Lovelace"}
    assert transcript.tool_calls[0].result == "Ada Lovelace was a mathematician."
    assert transcript.answer == "Ada Lovelace was a mathematician."


def test_run_agent_with_no_tool_call_has_empty_tool_calls(wikipedia_mock_transport):
    agent = build_agent(FunctionModel(_answer_without_searching))

    with httpx.Client(transport=wikipedia_mock_transport) as client:
        transcript = run_agent(agent, "What is 2 + 2?", deps=client)

    assert transcript.tool_calls == []
    assert transcript.answer == "4"


def test_run_agent_propagates_exhausted_retries():
    agent = build_agent(FunctionModel(_always_fail_search))

    with pytest.raises(UnexpectedModelBehavior):
        with httpx.Client(transport=httpx.MockTransport(_fake_no_results_transport)) as client:
            run_agent(agent, "Who is nobody?", deps=client)
```

These are the "high gear" service-layer tests: real `Agent`/`build_agent` wiring, fully fake model (`FunctionModel`) and fake HTTP transport (`httpx.MockTransport`) — no network, no real Anthropic calls, no `mock.patch`. `wikipedia_mock_transport` (the happy-path fake) comes from Task 3's `conftest.py`; `_fake_no_results_transport` stays local since it's only used by the retries-exhausted test here.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.runner'`

- [ ] **Step 3: Write the implementation**

Create `app/runner.py`:

```python
"""Runs a question through the agent and builds an auditable transcript from
Pydantic AI's own message history — no hand-rolled tool-call tracking.
"""

from typing import Any

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent, AgentRunResult
from pydantic_ai.messages import ToolCallPart, ToolReturnPart


class ToolCallRecord(BaseModel):
    tool_name: str
    args: dict[str, Any]
    result: str


class RunTranscript(BaseModel):
    question: str
    tool_calls: list[ToolCallRecord]
    answer: str


def run_agent(agent: Agent, question: str, deps: httpx.Client) -> RunTranscript:
    """Run `question` through `agent` and return an auditable transcript.

    Raises whatever the underlying agent run raises (e.g. `UnexpectedModelBehavior`
    when tool retries are exhausted) — callers decide how to handle failure.
    """
    result = agent.run_sync(question, deps=deps)
    return _build_transcript(question, result)


def _build_transcript(question: str, result: AgentRunResult) -> RunTranscript:
    calls_by_id: dict[str, ToolCallPart] = {}
    tool_calls: list[ToolCallRecord] = []

    for message in result.new_messages():
        for part in message.parts:
            if isinstance(part, ToolCallPart):
                calls_by_id[part.tool_call_id] = part
            elif isinstance(part, ToolReturnPart):
                call = calls_by_id.get(part.tool_call_id)
                if call is not None:
                    tool_calls.append(
                        ToolCallRecord(
                            tool_name=call.tool_name,
                            args=call.args_as_dict(),
                            result=str(part.content),
                        )
                    )

    return RunTranscript(question=question, tool_calls=tool_calls, answer=str(result.output))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_runner.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/runner.py tests/unit/test_runner.py
git commit -m "Add run_agent(): builds an auditable RunTranscript from agent message history"
```

---

### Task 5: `app/query_agent.py` — CLI entrypoint

**Files:**
- Create: `app/query_agent.py`
- Test: `tests/unit/test_query_agent.py`

**Interfaces:**
- Consumes: `app.agent.build_agent` (Task 3), `app.runner.run_agent`/`RunTranscript` (Task 4), `app.tools.WIKIPEDIA_USER_AGENT` (Task 2).
- Produces: `app.query_agent.format_transcript(transcript: RunTranscript) -> str`, `app.query_agent.main(argv: Sequence[str] | None = None, *, agent_factory: Callable[[], Agent] = build_agent) -> None`. Nothing else may depend on this module.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_query_agent.py`:

```python
import pytest
from pydantic import ValidationError
from pydantic_ai import Agent

from app import query_agent
from app.runner import RunTranscript, ToolCallRecord


def test_format_transcript_includes_question_tool_calls_and_answer():
    transcript = RunTranscript(
        question="What is the capital of France?",
        tool_calls=[
            ToolCallRecord(
                tool_name="search_wikipedia",
                args={"query": "capital of France"},
                result="Paris is the capital and largest city of France...",
            )
        ],
        answer="Paris is the capital of France.",
    )

    output = query_agent.format_transcript(transcript)

    assert "Question: What is the capital of France?" in output
    assert "search_wikipedia(query='capital of France')" in output
    assert "Paris is the capital and largest city of France..." in output
    assert "Answer:" in output
    assert output.strip().endswith("Paris is the capital of France.")


def test_main_exits_with_friendly_message_when_api_key_missing(capsys):
    def raise_validation_error() -> Agent:
        raise ValidationError.from_exception_data(
            "Settings", [{"type": "missing", "loc": ("anthropic_api_key",), "input": {}}]
        )

    with pytest.raises(SystemExit) as exc_info:
        query_agent.main(["irrelevant question"], agent_factory=raise_validation_error)

    assert exc_info.value.code == 1
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err
```

`main()` takes an injectable `agent_factory` (defaulting to the real `build_agent`) instead of calling `build_agent()` directly — this is a real dependency-injection seam, not a patched collaborator: the test passes a hand-written fake factory as a normal argument, exactly the "fakes over patches" / cosmicpython chapter 3 pattern documented in `CLAUDE.md`'s Design principles, rather than reaching for `monkeypatch.setattr`/`mock.patch` to swap out `build_agent` inside the module. No real network, no patching.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_query_agent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.query_agent'`

- [ ] **Step 3: Write the implementation**

Create `app/query_agent.py`:

```python
"""CLI entrypoint: ask the agent one question, print an auditable report.

This is the only module in app/ with argparse/printing/CLI-specific error
handling. It depends on app.agent and app.runner; nothing else depends on it.
"""

import argparse
import sys
from collections.abc import Callable, Sequence

import httpx
from pydantic import ValidationError
from pydantic_ai import Agent

from app.agent import build_agent
from app.runner import RunTranscript, run_agent
from app.tools import WIKIPEDIA_USER_AGENT


def format_transcript(transcript: RunTranscript) -> str:
    lines = [f"Question: {transcript.question}", ""]

    if transcript.tool_calls:
        lines.append("Tool calls:")
        for i, call in enumerate(transcript.tool_calls, start=1):
            args_str = ", ".join(f"{k}={v!r}" for k, v in call.args.items())
            lines.append(f"  {i}. {call.tool_name}({args_str})")
            lines.append(f"     → {call.result}")
        lines.append("")

    lines.append("Answer:")
    lines.append(transcript.answer)
    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None,
    *,
    agent_factory: Callable[[], Agent] = build_agent,
) -> None:
    parser = argparse.ArgumentParser(description="Ask the Wikipedia Q&A agent a question.")
    parser.add_argument("question")
    args = parser.parse_args(argv)

    try:
        agent = agent_factory()
    except ValidationError:
        print(
            "Error: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        sys.exit(1)

    with httpx.Client(headers={"User-Agent": WIKIPEDIA_USER_AGENT}) as client:
        transcript = run_agent(agent, args.question, deps=client)

    print(format_transcript(transcript))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_query_agent.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/query_agent.py tests/unit/test_query_agent.py
git commit -m "Add app.query_agent CLI: ask a question, print an auditable report"
```

---

### Task 6: Update smoke test and CLAUDE.md

**Files:**
- Modify: `tests/unit/test_app_imports.py`
- Modify: `CLAUDE.md`

**Interfaces:** None — documentation and import-smoke-test only, no behavior change.

- [ ] **Step 1: Update the import smoke test to cover all six modules**

Modify `tests/unit/test_app_imports.py` — change the module tuple from `("app.agent", "app.prompts", "app.tools")` to include all six new/existing modules:

```python
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
```

- [ ] **Step 2: Run the smoke test**

Run: `uv run pytest tests/unit/test_app_imports.py -v`
Expected: 1 passed

- [ ] **Step 3: Update CLAUDE.md's Commands section**

In `CLAUDE.md`, find this block:

```
uv run python -m app.agent "your question"  # ask a question
uv run python -m app.agent --demo           # run built-in sample questions
```

Replace it with:

```
uv run python -m app.query_agent "your question"  # ask a question
```

- [ ] **Step 4: Update CLAUDE.md's Architecture section**

Find the existing Architecture section bullet describing `app/agent.py`, `app/prompts.py`, `app/tools.py`. Replace that bullet with:

```markdown
- `app/config.py` — env-driven settings (`Settings`: Anthropic API key + model,
  read from `.env`).
- `app/tools.py` — the `search_wikipedia` tool: MediaWiki search + extract
  retrieval (functional core / imperative shell split within the module).
- `app/prompts.py` — the agent's system prompt.
- `app/agent.py` — `build_agent(model=None)`: constructs the `Agent`,
  registering `search_wikipedia` and resolving the real Anthropic model from
  `Settings` when no model is given. No CLI/argparse/printing logic.
- `app/runner.py` — `run_agent(agent, question, deps)`: runs a question
  through the agent and returns an auditable `RunTranscript` built from
  Pydantic AI's own message history (see Auditability below). Shared by the
  CLI and (later) the eval suite — neither depends on the other.
- `app/query_agent.py` — the CLI entrypoint (`python -m app.query_agent`).
  The only module with argparse/printing/CLI-specific error handling;
  depends on `agent.py` and `runner.py`, and nothing else depends on it.
```

- [ ] **Step 5: Add an Auditability section to CLAUDE.md**

Add a new section after "Design principles" (or after the Architecture section — place it wherever reads most naturally next to the existing structure):

```markdown
## Auditability

Every agent run must produce an inspectable record of what happened — each
tool call (name, arguments, result) and the final answer — not just the
answer text. Build this from Pydantic AI's own message history
(`result.new_messages()`, walking `ToolCallPart`/`ToolReturnPart`), as
`app/runner.py`'s `run_agent()` does — not hand-rolled logging, and not a
mutable context object tools write into themselves (that couples every tool
to a logging contract and can drift from what the model actually saw).
```

- [ ] **Step 6: Verify pre-commit passes on the doc changes**

Run: `uv run pre-commit run --all-files`
Expected: all hooks pass (ruff, ty, pytest) — no code changed in this task, but this confirms nothing regressed.

- [ ] **Step 7: Commit**

```bash
git add tests/unit/test_app_imports.py CLAUDE.md
git commit -m "Update CLAUDE.md commands/architecture and smoke test for the new agent scaffold"
```

---

### Task 7: Manual end-to-end verification

**Files:** None — this task runs the real CLI against the real Anthropic API and real Wikipedia, which is not something the automated test suite does (per the spec's decision to defer real end-to-end runs to the eval suite). This is the "does it actually work" check before calling the scaffold done.

**Interfaces:** None.

- [ ] **Step 1: Run the full test suite and quality gates**

Run: `uv run pre-commit run --all-files`
Expected: ruff check, ruff format, ty check, and pytest all pass.

- [ ] **Step 2: Run the CLI with a real question**

Run: `uv run python -m app.query_agent "What year was Ada Lovelace born?"`

Expected: output resembling:

```
Question: What year was Ada Lovelace born?

Tool calls:
  1. search_wikipedia(query='Ada Lovelace')
     → Augusta Ada King, Countess of Lovelace ... (born 10 December 1815) ...

Answer:
Ada Lovelace was born in 1815.
```

Confirm: the tool was actually called (not answered from the model's own knowledge with an empty `tool_calls` list), the printed extract is real Wikipedia content, and the answer is consistent with it.

- [ ] **Step 3: Confirm the missing-API-key error path manually**

Run: `ANTHROPIC_API_KEY= uv run python -m app.query_agent "test"` (temporarily blanking the env var for this one invocation only — does not modify `.env`)

Expected: prints `Error: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.` to stderr and exits nonzero — no raw traceback.

- [ ] **Step 4: Confirm a no-good-match query still produces a sensible transcript**

Run: `uv run python -m app.query_agent "What is the airspeed velocity of an unladen swallow according to the Monty Python sketch?"`

Expected: either a reasonable answer grounded in a real Wikipedia extract (if an article covers it) or a transcript showing the agent tried one or more searches and gave an honest "I couldn't find a clear answer" — not a crash, not a fabricated answer with an empty tool-call list.

No commit for this task — it's verification only, confirming Tasks 1–6's automated tests are actually validating real behavior.

---

## Self-Review Notes

**Spec coverage:** every file in the spec's layout (`config.py`, `tools.py`, `prompts.py`, `agent.py`, `runner.py`, `query_agent.py`) has a task; the dependency-direction constraint, the `WIKIPEDIA_USER_AGENT` requirement, the `run_agent`-raises-not-swallows contract, the human-readable (not JSON) CLI output, the API-key-only special-cased error, and the CLAUDE.md Commands/Architecture/Auditability updates are all covered (Tasks 1–6). The eval suite itself is explicitly out of scope per the spec and not included here.

**Verification performed while writing this plan:** every non-trivial API call in this plan (`AnthropicModel`/`AnthropicProvider` constructor signatures, `Agent.__init__`/`run_sync` signatures, `ToolCallPart`/`ToolReturnPart` field names, `AgentRunResult.new_messages()`/`.output`, `args_as_dict()`, `pydantic_settings`' `_env_file=None` override, `ValidationError.from_exception_data`, and the `UnexpectedModelBehavior` exception on exhausted retries) was checked against the actually-installed `pydantic-ai==2.27.0` package and run end-to-end against real code, not written from memory. The Wikipedia `403 Forbidden` / `User-Agent` requirement was discovered this way — it would otherwise have been a silent failure discovered only in Task 7.

**Type consistency:** `build_agent(model: Model | KnownModelName | None = None) -> Agent` (Task 3) is called identically in Tasks 4, 5, and their tests. `run_agent(agent: Agent, question: str, deps: httpx.Client) -> RunTranscript` (Task 4) is called identically in Task 5. `RunTranscript`/`ToolCallRecord` field names (`question`, `tool_calls`, `answer`, `tool_name`, `args`, `result`) match between their Task 4 definition and every consumer in Task 5's `format_transcript`.

**Pre-flight fixes applied before dispatch:** two issues surfaced by re-reading the plan with fresh eyes and were fixed in place before Task 1 was dispatched — (1) Task 5's error-path test originally used `monkeypatch.setattr` to fake `build_agent`, which patches a collaborator rather than injecting a fake through a seam (violates CLAUDE.md's "fakes over patches"); fixed by giving `main()` an injectable `agent_factory` parameter. (2) Task 3 and Task 4's tests originally each defined an identical `_fake_wikipedia_transport` helper; fixed by moving it into a shared `tests/unit/conftest.py` fixture (`wikipedia_mock_transport`), consumed by both.
