# Pydantic Evals bootstrap: first eval dataset — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get one real `pydantic_evals.Dataset` running end-to-end against the
production Wikipedia Q&A agent — HotpotQA-sourced questions in, a printed
grading report out — proving the eval suite's scaffolding before scaling to
more datasets.

**Architecture:** A new `evaluations/` package (sibling to `app/`) holds a
single production entrypoint (`task.py`), a generic dataset runner
(`run.py`), and grading logic (`evaluators.py`, `models.py`). Two small
extractions from `query_agent.py` into `app/agent.py`/`app/tools.py` give
the CLI and the eval suite identical production wiring, so neither is
special-cased. The dataset itself (`evaluations/datasets/format_validation.yaml`)
is built once from real HotpotQA rows and committed — no build script is
kept in the repo (see the design doc for why).

**Tech Stack:** Python 3.13, `pydantic_evals` (already a dependency),
`pydantic_ai`, `datasets` (Hugging Face, dev-only), `uv`, `pytest`, `ruff`,
`ty`.

## Global Constraints

- Every commit must pass `uv run pre-commit run --all-files` (ruff check,
  ruff format, ty check, pytest) — these already run repo-wide with no path
  exclusions, so `evaluations/*.py` is covered automatically.
- No `evaluations/` code may import `app.query_agent` (dependency direction:
  `evaluations/*` → `app/*` only — same rule CLAUDE.md already states for
  `query_agent.py` itself).
- `datasets` (Hugging Face) is a **dev-only** dependency
  (`[dependency-groups] dev`) — never added to `[project.dependencies]`.
- No dataset-build script gets committed. HotpotQA sourcing happens
  interactively during Task 5 and only its output (the YAML + schema) is
  committed.
- Follow this repo's test pyramid: unit tests for pure/structural logic, no
  network calls in anything `pytest` runs automatically (`testpaths =
  ["tests"]`). The live eval run itself is a manual verification step, not
  an automated test.
- Design doc: `docs/superpowers/specs/2026-08-09-pydantic-evals-hotpotqa-design.md`
  — consult it for rationale behind any decision below.

---

## Task 1: Add the `datasets` (Hugging Face) dev dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Produces: `datasets` importable in the dev environment (`import datasets`),
  used later by Task 5's one-off sourcing step. Not imported by any
  committed application code.

- [ ] **Step 1: Add the dependency**

```bash
uv add --group dev datasets
```

This adds `"datasets>=5.0.1"` (or whatever current version resolves) to
`[dependency-groups] dev` in `pyproject.toml` and updates `uv.lock`. If
already present from earlier prep work, this command is idempotent — running
it again is a no-op.

- [ ] **Step 2: Verify it installs and imports**

Run: `uv run python -c "import datasets; print(datasets.__version__)"`
Expected: prints a version string (e.g. `5.0.1`), no error.

- [ ] **Step 3: Verify the committed lockfile actually matches**

This repo is a standalone `uv` project (not nested in any parent
workspace — see CONTRIBUTING.md's "Notes" section for why that matters and
what broke when it briefly was), so `uv add` in Step 1 updated this repo's
own `uv.lock` directly. Confirm:

Run: `uv sync --locked --all-groups`
Expected: succeeds with no "lockfile needs to be updated" error — this
means `uv.lock` and `pyproject.toml` genuinely match, so anyone cloning
this repo fresh (CI, a reviewer) gets a working `uv sync`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "$(cat <<'EOF'
Add datasets (Hugging Face) as a dev-only dependency

Needed for one-off HotpotQA case sourcing (see the eval-suite design
doc); never imported by shipped application code, so it stays out of
[project.dependencies].
EOF
)"
```

---

## Task 2: Extract shared production wiring into `app/agent.py` and `app/tools.py`

`query_agent.py` currently has a private `_resolve_real_model()` and an
inline `httpx.Client(headers=..., timeout=30.0)` construction. The eval
suite's `task.py` (Task 4) needs the exact same wiring — resolving the real
Anthropic model from `Settings`, and building a correctly-configured
Wikipedia client. Duplicating it risks silent drift (e.g. a timeout change
applied to one copy and not the other). This task promotes both pieces to
the modules that already own the concepts they configure, and updates
`query_agent.py` to use them — its own behavior must not change.

**Files:**
- Modify: `app/agent.py`
- Modify: `app/tools.py`
- Modify: `app/query_agent.py`
- Modify: `tests/unit/test_agent.py`
- Modify: `tests/unit/test_tools.py`

**Interfaces:**
- Produces: `app.agent.resolve_real_model(settings: Settings | None = None) -> Model` (narrower than
  originally drafted here — see the ruling note after Step 3 below)
- Produces: `app.tools.build_wikipedia_client(timeout: float = 30.0) -> httpx.Client`
- Consumes (Task 4/5/6): both of the above, plus the existing
  `app.agent.agent` and `app.runner.run_agent`.

- [ ] **Step 1: Write the failing test for `resolve_real_model`**

Add to `tests/unit/test_agent.py` (add `from app.agent import agent,
resolve_real_model` — replacing the current `from app.agent import agent` —
and `from app.config import Settings` to the imports at the top):

```python
def test_resolve_real_model_uses_settings_model_name():
    settings = Settings(
        anthropic_api_key="fake-key", anthropic_model="claude-opus-5", _env_file=None
    )

    model = resolve_real_model(settings)

    assert model.model_name == "claude-opus-5"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/unit/test_agent.py::test_resolve_real_model_uses_settings_model_name -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_real_model'`.

- [ ] **Step 3: Implement `resolve_real_model` in `app/agent.py`**

Replace the full contents of `app/agent.py` with:

```python
"""Wires the system prompt and tools into a Pydantic AI Agent."""

import httpx
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.config import Settings
from app.prompts import SYSTEM_PROMPT
from app.tools import search_wikipedia

agent: Agent[httpx.Client, str] = Agent(
    name="wikipedia_qa_agent",
    instructions=SYSTEM_PROMPT,
    deps_type=httpx.Client,
    tools=[search_wikipedia],
)


def resolve_real_model(settings: Settings | None = None) -> Model:
    """Resolve the real Anthropic model from Settings (.env)."""
    settings = settings or Settings()
    return AnthropicModel(
        settings.anthropic_model,
        provider=AnthropicProvider(api_key=settings.anthropic_api_key.get_secret_value()),
    )
```

**Ruling (recorded during execution, not the original draft):** this step
originally specified `-> Model | KnownModelName`, copied from the old
private `_resolve_real_model`'s signature without re-examining whether it
still fit. It doesn't: `resolve_real_model` always constructs and returns a
real `AnthropicModel` — never a bare `KnownModelName` string — and the
wider union breaks `ty check` the moment calling code narrows the result
(e.g. `model.model_name`, since `KnownModelName` is a large string-literal
union with no such attribute). Confirmed by directly testing both
annotations against this repo's real `ty check`. Ruled: use the narrower,
honest `-> Model` shown above. `query_agent.py`'s `model_factory: Callable[[],
Model | KnownModelName]` parameter (Step 9 below) keeps its wider type
unchanged — a callable returning `Model` is a valid substitute for one
typed to return `Model | KnownModelName`, so this stays compatible.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_agent.py -v`
Expected: both `test_agent_registers_search_wikipedia_tool` and
`test_resolve_real_model_uses_settings_model_name` PASS.

- [ ] **Step 5: Write the failing test for `build_wikipedia_client`**

Add to `tests/unit/test_tools.py` (add `build_wikipedia_client` and
`WIKIPEDIA_USER_AGENT` to the existing `from app.tools import parse_extract,
parse_search_title` line):

```python
def test_build_wikipedia_client_sets_user_agent_header():
    client = build_wikipedia_client()
    try:
        assert client.headers["User-Agent"] == WIKIPEDIA_USER_AGENT
    finally:
        client.close()


def test_build_wikipedia_client_defaults_to_30_second_timeout():
    client = build_wikipedia_client()
    try:
        assert client.timeout.read == 30.0
    finally:
        client.close()
```

- [ ] **Step 6: Run it to verify it fails**

Run: `uv run pytest tests/unit/test_tools.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_wikipedia_client'`.

- [ ] **Step 7: Implement `build_wikipedia_client` in `app/tools.py`**

Insert this function immediately after the `WIKIPEDIA_USER_AGENT`
assignment (before `def parse_search_title`):

```python
def build_wikipedia_client(timeout: float = 30.0) -> httpx.Client:
    """A correctly-configured but unopened client for calling search_wikipedia.
    Lifecycle (open/close) stays with the caller."""
    return httpx.Client(headers={"User-Agent": WIKIPEDIA_USER_AGENT}, timeout=timeout)
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_tools.py -v`
Expected: all `test_tools.py` tests PASS.

- [ ] **Step 9: Update `query_agent.py` to use both**

Replace the full contents of `app/query_agent.py` with:

```python
"""CLI entrypoint: ask the agent one question, print an auditable report."""

import argparse
import sys
from collections.abc import Callable, Sequence

from pydantic import ValidationError
from pydantic_ai.models import KnownModelName, Model

from app.agent import agent, resolve_real_model
from app.runner import RunTranscript, run_agent
from app.tools import build_wikipedia_client


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
    model_factory: Callable[[], Model | KnownModelName] = resolve_real_model,
) -> None:
    parser = argparse.ArgumentParser(description="Ask the Wikipedia Q&A agent a question.")
    parser.add_argument("question")
    args = parser.parse_args(argv)

    try:
        model = model_factory()
    except ValidationError:
        print(
            "Error: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        sys.exit(1)

    with build_wikipedia_client() as client:
        transcript = run_agent(agent, args.question, deps=client, model=model)

    print(format_transcript(transcript))


if __name__ == "__main__":
    main()
```

This removes `_resolve_real_model` (replaced by the imported
`resolve_real_model`), the inline `httpx.Client(...)` construction (replaced
by `build_wikipedia_client()`), and the now-unused `httpx`,
`app.tools.WIKIPEDIA_USER_AGENT`, `pydantic_ai.models.anthropic.AnthropicModel`,
and `pydantic_ai.providers.anthropic.AnthropicProvider` imports.

- [ ] **Step 10: Run the full test suite to confirm nothing broke**

Run: `uv run pytest -v`
Expected: all tests PASS, including the existing `test_query_agent.py` tests
unchanged (they pass their own `model_factory`, so the default's rename
doesn't affect them) and `test_runner.py`/`test_app_imports.py`.

- [ ] **Step 11: Run the full quality gate and commit**

```bash
uv run ruff check .
uv run ruff format .
uv run ty check
```

Fix anything flagged, then:

```bash
git add app/agent.py app/tools.py app/query_agent.py tests/unit/test_agent.py tests/unit/test_tools.py
git commit -m "$(cat <<'EOF'
Extract shared production wiring: resolve_real_model, build_wikipedia_client

query_agent.py's private _resolve_real_model() and inline Wikipedia
httpx.Client construction were the only copies of this wiring; the
upcoming eval suite needs the identical configuration. Promoted both to
the modules that already own the concepts they configure (app/agent.py,
app/tools.py) so CLI and evals share one source of truth instead of two
copies that could silently drift.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Build `evaluations/models.py` and `evaluations/evaluators.py`

**Files:**
- Create: `evaluations/models.py`
- Create: `evaluations/evaluators.py`
- Create: `tests/unit/test_evaluators.py`

**Interfaces:**
- Consumes: `app.runner.RunTranscript`, `app.runner.ToolCallRecord` (already
  exist).
- Produces: `evaluations.models.HotpotQAMetadata` (fields: `level: Literal["easy",
  "medium", "hard"]`, `type: Literal["comparison", "bridge"]`, `hotpotqa_id: str`).
- Produces: `evaluations.evaluators.TranscriptWellFormed` (a
  `pydantic_evals.evaluators.Evaluator[str, RunTranscript, HotpotQAMetadata]`)
  and `evaluations.evaluators.CUSTOM_EVALUATOR_TYPES` (a tuple, used by
  Task 4/5's `from_file`/`to_file` calls).

- [ ] **Step 1: Create `evaluations/models.py`**

```python
"""Shared, cross-cutting metadata for HotpotQA-sourced eval cases."""

from typing import Literal

from pydantic import BaseModel


class HotpotQAMetadata(BaseModel):
    """Cross-cutting provenance for a HotpotQA-sourced case. Purpose-specific
    grading data lives next to the evaluator that reads it, not here."""

    level: Literal["easy", "medium", "hard"]
    type: Literal["comparison", "bridge"]
    hotpotqa_id: str
```

- [ ] **Step 2: Write the failing tests for `TranscriptWellFormed`**

Create `tests/unit/test_evaluators.py`:

```python
from pydantic_evals.evaluators import EvaluatorContext
from pydantic_evals.otel import SpanTreeRecordingError

from app.runner import RunTranscript, ToolCallRecord
from evaluations.evaluators import TranscriptWellFormed
from evaluations.models import HotpotQAMetadata


def _ctx(transcript: RunTranscript) -> EvaluatorContext[str, RunTranscript, HotpotQAMetadata]:
    return EvaluatorContext(
        name="test case",
        inputs=transcript.question,
        metadata=HotpotQAMetadata(level="easy", type="bridge", hotpotqa_id="abc123"),
        expected_output=None,
        output=transcript,
        duration=0.1,
        _span_tree=SpanTreeRecordingError("not needed for this evaluator"),
        attributes={},
        metrics={},
    )


def test_well_formed_transcript_passes_both_checks():
    transcript = RunTranscript(
        question="Who was Ada Lovelace?",
        tool_calls=[
            ToolCallRecord(
                tool_name="search_wikipedia",
                args={"query": "Ada Lovelace"},
                result="Ada Lovelace was a mathematician.",
            )
        ],
        answer="Ada Lovelace was an English mathematician.",
    )

    result = TranscriptWellFormed().evaluate_sync(_ctx(transcript))

    assert result == {"answer_non_empty": True, "tool_calls_well_formed": True}


def test_empty_answer_fails_answer_check():
    transcript = RunTranscript(question="Who was Ada Lovelace?", tool_calls=[], answer="   ")

    result = TranscriptWellFormed().evaluate_sync(_ctx(transcript))

    assert result["answer_non_empty"] is False


def test_empty_tool_call_result_fails_tool_calls_check():
    transcript = RunTranscript(
        question="Who was Ada Lovelace?",
        tool_calls=[ToolCallRecord(tool_name="search_wikipedia", args={"query": "x"}, result="")],
        answer="Ada Lovelace was a mathematician.",
    )

    result = TranscriptWellFormed().evaluate_sync(_ctx(transcript))

    assert result["tool_calls_well_formed"] is False
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/unit/test_evaluators.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evaluations'`.

- [ ] **Step 4: Create `evaluations/evaluators.py`**

```python
"""Evaluators for grading agent runs. Grows by addition as new eval purposes are added."""

from dataclasses import dataclass

from pydantic_evals.evaluators import Evaluator, EvaluatorContext, EvaluatorOutput

from app.runner import RunTranscript
from evaluations.models import HotpotQAMetadata


@dataclass
class TranscriptWellFormed(Evaluator[str, RunTranscript, HotpotQAMetadata]):
    """Structural smoke check only — not correctness, faithfulness, or
    whether search was used. Those are separate future datasets."""

    def evaluate(
        self, ctx: EvaluatorContext[str, RunTranscript, HotpotQAMetadata]
    ) -> EvaluatorOutput:
        transcript = ctx.output
        return {
            "answer_non_empty": bool(transcript.answer.strip()),
            "tool_calls_well_formed": all(
                call.tool_name.strip() and str(call.result).strip()
                for call in transcript.tool_calls
            ),
        }


CUSTOM_EVALUATOR_TYPES = (TranscriptWellFormed,)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_evaluators.py -v`
Expected: all three tests PASS.

- [ ] **Step 6: Run the full quality gate and commit**

```bash
uv run ruff check .
uv run ruff format .
uv run ty check
uv run pytest
```

```bash
git add evaluations/models.py evaluations/evaluators.py tests/unit/test_evaluators.py
git commit -m "$(cat <<'EOF'
Add HotpotQAMetadata and the TranscriptWellFormed structural evaluator

Format-validation is a smoke check, not a schema check: RunTranscript is
already validated by construction, so this checks the model's fields are
actually populated meaningfully (non-empty answer, well-formed tool-call
records), not just present. Correctness/faithfulness/relevancy are
separate future evaluators — see the design doc.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Build `evaluations/task.py` and `evaluations/run.py`

These have no dedicated unit tests — both require either a live agent run or
a real dataset file to exercise meaningfully, and both get proven for real
in Task 5's end-to-end run. Type-checking (`ty`) and a manual `--help`
smoke check are this task's verification.

**Files:**
- Create: `evaluations/task.py`
- Create: `evaluations/run.py`

**Interfaces:**
- Consumes: `app.agent.agent`, `app.agent.resolve_real_model`,
  `app.tools.build_wikipedia_client`, `app.runner.run_agent`,
  `app.runner.RunTranscript` (all from Task 2 and pre-existing code);
  `evaluations.evaluators.CUSTOM_EVALUATOR_TYPES`,
  `evaluations.models.HotpotQAMetadata` (from Task 3).
- Produces: `evaluations.task.production_task()` — a context manager
  yielding `Callable[[str], RunTranscript]`. Consumed by `run.py` (this
  task) and reused unchanged by every future dataset's run.
- Produces: `evaluations.run.main(argv: list[str] | None = None) -> None`,
  invoked via `uv run python -m evaluations.run <dataset_name>`.

- [ ] **Step 1: Create `evaluations/task.py`**

```python
"""The one production entrypoint every eval dataset runs its cases through."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.agent import agent, resolve_real_model
from app.runner import RunTranscript, run_agent
from app.tools import build_wikipedia_client


@contextmanager
def production_task() -> Iterator[Callable[[str], RunTranscript]]:
    """One client, reused across every case in a run, for connection pooling —
    the CLI wants one client per question, the eval suite wants one per batch."""
    model = resolve_real_model()
    with build_wikipedia_client() as client:

        def answer_question(question: str) -> RunTranscript:
            return run_agent(agent, question, deps=client, model=model)

        yield answer_question
```

- [ ] **Step 2: Create `evaluations/run.py`**

```python
"""Generic runner: load a dataset by name, run it against the production agent, print the report."""

import argparse
from pathlib import Path

from pydantic_evals import Dataset

from app.runner import RunTranscript
from evaluations.evaluators import CUSTOM_EVALUATOR_TYPES
from evaluations.models import HotpotQAMetadata
from evaluations.task import production_task

DATASETS_DIR = Path(__file__).parent / "datasets"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run a named eval dataset against the agent.")
    parser.add_argument("dataset_name")
    args = parser.parse_args(argv)

    dataset_path = DATASETS_DIR / f"{args.dataset_name}.yaml"
    dataset = Dataset[str, RunTranscript, HotpotQAMetadata].from_file(
        dataset_path, custom_evaluator_types=CUSTOM_EVALUATOR_TYPES
    )
    with production_task() as answer_question:
        report = dataset.evaluate_sync(answer_question)
    report.print()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Type-check and smoke-test argument parsing**

Run: `uv run ty check`
Expected: no errors.

Run: `uv run python -m evaluations.run --help`
Expected: prints usage text (`usage: run.py [-h] dataset_name ...`), exit 0.
This confirms imports resolve and argparse wiring works, without needing a
real dataset file (which doesn't exist until Task 5) or hitting the network.

- [ ] **Step 4: Run the full quality gate and commit**

```bash
uv run ruff check .
uv run ruff format .
uv run pytest
```

```bash
git add evaluations/task.py evaluations/run.py
git commit -m "$(cat <<'EOF'
Add the eval suite's production task and generic dataset runner

production_task() is the one entrypoint every dataset's cases run
through - it resolves the real model and opens one Wikipedia client
reused across the whole batch (connection pooling), then delegates to
the same run_agent() the CLI uses. run.py never varies per dataset:
adding a new eval purpose later only means a new YAML file plus
whatever evaluators.py addition it needs, never a new runner.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Source HotpotQA cases, build the dataset, verify it runs end-to-end

**Files:**
- Create: `evaluations/datasets/format_validation.yaml`
- Create: `evaluations/datasets/format_validation_schema.json` (auto-generated)

**Interfaces:**
- Consumes: `evaluations.evaluators.TranscriptWellFormed`,
  `evaluations.evaluators.CUSTOM_EVALUATOR_TYPES`,
  `evaluations.models.HotpotQAMetadata` (Task 3); `evaluations.run.main`
  (Task 4, for the verification step).
- Produces: the `format_validation` dataset, loadable via
  `Dataset[str, RunTranscript, HotpotQAMetadata].from_file(...)` — the
  artifact every later dataset-addition task will follow the shape of.

Three real HotpotQA rows were already sourced during planning (streamed
from the `train` split, `distractor` config, one per difficulty level,
first short/clean match — see the design doc's "Source: HotpotQA" section
for full methodology):

| level | type | id | question | answer (not used — format-only) |
|---|---|---|---|---|
| easy | bridge | `5ade025e5542997dc790711e` | In which American football game was Malcolm Smith named Most Valuable player? | Super Bowl XLVIII |
| medium | comparison | `5a7a06935542990198eaf050` | Which magazine was started first Arthur's Magazine or First for Women? | Arthur's Magazine |
| hard | bridge | `5adf44985542993a75d2646d` | Which genus of moth in the world's seventh-largest country contains only one species? | Crambidae |

- [ ] **Step 1: Build and write the dataset**

Run this from the repo root (it writes to the relative path
`evaluations/datasets/format_validation.yaml`) as a one-off script (`uv run
python3 <<'EOF' ... EOF`, or a temp `.py` file you delete afterward — it
must **not** be committed, per the "no build
scripts" decision in the design doc):

```python
from pathlib import Path

from pydantic_evals import Case, Dataset

from app.runner import RunTranscript
from evaluations.evaluators import CUSTOM_EVALUATOR_TYPES, TranscriptWellFormed
from evaluations.models import HotpotQAMetadata

cases = [
    Case(
        name="easy_bridge_super_bowl_mvp",
        inputs="In which American football game was Malcolm Smith named Most Valuable player?",
        metadata=HotpotQAMetadata(
            level="easy", type="bridge", hotpotqa_id="5ade025e5542997dc790711e"
        ),
    ),
    Case(
        name="medium_comparison_magazine",
        inputs="Which magazine was started first Arthur's Magazine or First for Women?",
        metadata=HotpotQAMetadata(
            level="medium", type="comparison", hotpotqa_id="5a7a06935542990198eaf050"
        ),
    ),
    Case(
        name="hard_bridge_moth_genus",
        inputs="Which genus of moth in the world's seventh-largest country contains only one species?",
        metadata=HotpotQAMetadata(
            level="hard", type="bridge", hotpotqa_id="5adf44985542993a75d2646d"
        ),
    ),
]

dataset = Dataset[str, RunTranscript, HotpotQAMetadata](
    name="format_validation",
    cases=cases,
    evaluators=[TranscriptWellFormed()],
)

path = Path("evaluations/datasets/format_validation.yaml")
path.parent.mkdir(parents=True, exist_ok=True)
dataset.to_file(path, custom_evaluator_types=CUSTOM_EVALUATOR_TYPES)

header = """# Cases sourced from HotpotQA (Yang et al., 2018 -- arXiv:1809.09600,
# https://huggingface.co/datasets/hotpotqa/hotpot_qa), licensed CC-BY-SA-4.0.
# One case per difficulty level, from the `train` split (config
# "distractor" -- question/answer/level/type are identical between configs;
# only the unused `context` field differs), picked via streaming iteration,
# first short/clean match per level. See docs/hotpotqa_1809.09600v1.md and
# docs/superpowers/specs/2026-08-09-pydantic-evals-hotpotqa-design.md for
# full methodology. To source more/different cases, use the `datasets` dev
# dependency the same way -- see CONTRIBUTING.md.
"""
path.write_text(header + path.read_text())
print(path.read_text())
```

This was already dry-run during planning against a throwaway stand-in
module (confirming `Case`/`Dataset` construction, `to_file()`, and the
resulting YAML shape) — running it for real here against the actual
`evaluations.evaluators`/`evaluations.models` produces the same shape,
serializing `TranscriptWellFormed` into the YAML's `evaluators:` list.

- [ ] **Step 2: Verify the files exist and look right**

Run: `cat evaluations/datasets/format_validation.yaml`
Expected: the attribution header, `name: format_validation`, three `cases:`
entries (names matching the table above, correct `metadata`, `expected_output:
null`), and `evaluators:` containing `TranscriptWellFormed`.

Run: `ls evaluations/datasets/`
Expected: both `format_validation.yaml` and `format_validation_schema.json`
present.

- [ ] **Step 3: Run the live eval end-to-end**

This requires a real `ANTHROPIC_API_KEY` in `.env` (same requirement as
`query_agent.py`) and live network access to both Anthropic and Wikipedia.

Run: `uv run python -m evaluations.run format_validation`

Expected: a progress bar, then a report table with three rows (one per case
name from the table above) each showing `✔✔` (both `answer_non_empty` and
`tool_calls_well_formed` passing) and an `Averages` row at 100%. If any case
fails, inspect why before proceeding — a failing format check on real traffic
means either the agent produced something genuinely malformed (investigate
the agent) or the evaluator's logic is wrong (fix `evaluators.py`, back to
Task 3).

- [ ] **Step 4: Commit**

```bash
git add evaluations/datasets/format_validation.yaml evaluations/datasets/format_validation_schema.json
git commit -m "$(cat <<'EOF'
Add the format_validation dataset (3 HotpotQA cases, easy/medium/hard)

Sourced from HotpotQA's train split (Yang et al. 2018, CC-BY-SA-4.0),
one case per difficulty level. Verified end-to-end against the real
agent: uv run python -m evaluations.run format_validation reports all
three cases passing both structural checks.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Documentation updates

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`

**Interfaces:** none — this task changes only prose/markdown, no code.

- [ ] **Step 1: Fix pre-existing drift in CLAUDE.md's Architecture section**

`CLAUDE.md`'s Architecture section currently describes `app/agent.py` as
exporting `build_agent(model=None)` and `app/runner.py`'s `run_agent` as
taking `(agent, question, deps)` — neither matches the actual code (a
module-level `agent` object with model resolved separately, and `run_agent`
taking an explicit `model` parameter). This predates this plan's changes;
fix it while touching this section anyway so the doc matches reality.

Find this bullet:

```
- `app/agent.py` — `build_agent(model=None)`: constructs the `Agent`,
  registering `search_wikipedia` and resolving the real Anthropic model from
  `Settings` when no model is given. No CLI/argparse/printing logic.
- `app/runner.py` — `run_agent(agent, question, deps)`: runs a question
  through the agent and returns an auditable `RunTranscript` built from
  Pydantic AI's own message history (see Auditability above). Shared by the
  CLI and (later) the eval suite — neither depends on the other.
```

Replace with:

```
- `app/agent.py` — the module-level `agent` (registers `search_wikipedia`,
  no model bound) plus `resolve_real_model(settings=None)`: resolves the
  real Anthropic model from `Settings` when no settings are given. No
  CLI/argparse/printing logic.
- `app/runner.py` — `run_agent(agent, question, deps, model)`: runs a
  question through the agent and returns an auditable `RunTranscript` built
  from Pydantic AI's own message history (see Auditability above). Shared
  by the CLI and the eval suite (`evaluations/task.py`) — neither depends
  on the other.
```

- [ ] **Step 2: Add the `evaluations/` bullets to CLAUDE.md's Architecture section**

Immediately after the `app/query_agent.py` bullet (and before the
`tests/unit/test_app_imports.py` bullet), insert:

```
- `evaluations/` — the eval suite (assignment deliverable #3).
  `models.py` (`HotpotQAMetadata`: cross-cutting HotpotQA provenance —
  `level`/`type`/`hotpotqa_id`; purpose-specific grading data, e.g. a future
  correctness dataset's expected answer, lives next to the evaluator that
  reads it, not here — keeps this file's reason to change singular).
  `evaluators.py` (`Evaluator` subclasses + `CUSTOM_EVALUATOR_TYPES`; grows
  by addition as new eval purposes are added — split into multiple files
  only if it gets large enough to violate "one clear responsibility", not
  preemptively). `task.py` (`production_task()`: the one production
  entrypoint every dataset's cases run through — wraps
  `app.agent.resolve_real_model()` + `app.tools.build_wikipedia_client()` +
  `app.runner.run_agent()`; reused unchanged across every dataset). `run.py`
  (generic: `uv run python -m evaluations.run <dataset_name>` — never
  touched when adding a new dataset, since the dataset name is just an
  argument). `datasets/*.yaml` — one file per eval purpose; cases *and*
  their evaluator(s) are serialized together via
  `Dataset.to_file(custom_evaluator_types=...)`, so the YAML is
  self-describing, with an auto-generated `*_schema.json` sibling for IDE
  autocomplete. Depends only on `app/*`, never `app/query_agent.py` — same
  rule as `query_agent.py` itself.
- Evals hit the real Anthropic API and live Wikipedia — they are run
  manually (`uv run python -m evaluations.run <dataset_name>`), never by
  pytest/pre-commit/CI. Code quality on `evaluations/*.py` is *not*
  excluded: ruff/ty run repo-wide with no path exclusions, and
  `TranscriptWellFormed`'s pure logic has a normal pytest unit test — only
  the live agent execution itself stays manual.
- HotpotQA-sourced datasets: no build script is committed — sourcing is
  one-off curation work (see `docs/superpowers/specs/2026-08-09-pydantic-evals-hotpotqa-design.md`
  for why), and only its output (the YAML + schema) lands in the repo.
  `datasets` (Hugging Face) is a dev-only dependency for that curation work;
  nothing in the committed code imports it. HotpotQA (Yang et al. 2018,
  arXiv:1809.09600, CC-BY-SA-4.0) is extracted to
  `docs/hotpotqa_1809.09600v1.md` for reference.
```

- [ ] **Step 3: Add the eval command to CLAUDE.md's Commands section**

Find this line in the ` ```bash ` block under `## Commands`:

```
uv run python -m app.query_agent "your question"  # ask a question
```

Add immediately after it:

```
uv run python -m evaluations.run format_validation  # run an eval dataset (hits real API + Wikipedia)
```

- [ ] **Step 4: Replace README.md's Evals stub**

Find:

```markdown
## Evals

The eval suite that measures answer quality (assignment deliverable #3) is
not yet built.
```

Replace with:

```markdown
## Evals

The eval suite (assignment deliverable #3) grades the agent against a
small, hand-picked set of Wikipedia-grounded questions from
[HotpotQA](https://huggingface.co/datasets/hotpotqa/hotpot_qa) (Yang et
al., 2018 — see `docs/hotpotqa_1809.09600v1.md`), spanning easy/medium/hard
difficulty.

```bash
uv run python -m evaluations.run format_validation
```

This first dataset checks the agent's output is well-formed (a real
answer, well-formed tool-call records) — correctness and faithfulness
grading come next.
```

No new setup beyond the Quickstart above: running an already-built dataset
needs the same API key and network access as the CLI, nothing more.

- [ ] **Step 5: Add a case-sourcing note to CONTRIBUTING.md**

Find the `## Notes` section's bullet list (starts with "This is a
standalone `uv` project..." — already updated separately, during planning,
to fix a lockfile-drift bug caused by an earlier accidental parent-workspace
nesting; not part of this task). Add a new bullet at the end:

```markdown
- To add more HotpotQA-sourced cases to an eval dataset: use the
  `datasets` dev dependency interactively (e.g. `datasets.load_dataset("hotpotqa/hotpot_qa",
  "distractor", split="train", streaming=True)`), build `Case`/`Dataset`
  objects per `evaluations/models.py`/`evaluations/evaluators.py`, and call
  `Dataset.to_file(...)`. See `evaluations/datasets/format_validation.yaml`'s
  header comment for the exact methodology used last time — no build script
  is kept in the repo, only the resulting YAML (see the design doc under
  `docs/superpowers/specs/` for why).
```

- [ ] **Step 6: Verify the docs render sensibly and commit**

Run: `uv run pre-commit run --all-files`
Expected: PASS (no Python files changed, so ruff/ty/pytest report "no files
to check" or pass trivially; this just confirms nothing else broke).

```bash
git add CLAUDE.md README.md CONTRIBUTING.md
git commit -m "$(cat <<'EOF'
Document the eval suite in CLAUDE.md, README.md, and CONTRIBUTING.md

Also fixes pre-existing drift in CLAUDE.md's Architecture section
(app/agent.py and app/runner.py's documented signatures no longer
matched the actual code, predating this change).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Full quality gate sweep

A final whole-repo sanity check after six tasks of incremental commits —
each task already ran its own gates, but this confirms the full picture
together (whole-file ty context, full pytest collection, etc.).

**Files:** none (verification only).

- [ ] **Step 1: Run the complete gate**

```bash
uv run pre-commit run --all-files --show-diff-on-failure
```

Expected: every hook (`ruff-check`, `ruff-format`, `ty check`, `pytest`)
PASSES.

- [ ] **Step 2: Confirm the live eval still runs**

Run: `uv run python -m evaluations.run format_validation`
Expected: same 100%-passing report as Task 5's Step 3 (confirms later
refactors in Tasks 6-7 didn't break anything).

- [ ] **Step 3: Review the branch's full diff against `main`**

Run: `git log --oneline main..HEAD` and `git diff main...HEAD --stat`
Expected: seven feature commits (Tasks 1-6, in order — Task 7 has no code
changes to commit) plus the earlier spec-doc commits, touching exactly the
files this plan described — no stray or unexpected changes.

No commit for this task unless Step 1 or 2 surfaces something to fix — if
they do, fix it, re-run both steps, then commit the fix with a message
describing what was wrong.
