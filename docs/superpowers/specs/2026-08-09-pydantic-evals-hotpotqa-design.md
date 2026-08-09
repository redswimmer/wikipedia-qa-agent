# Pydantic Evals bootstrap: first eval dataset — design

Date: 2026-08-09
Status: approved, pending implementation plan

## Goal

Build the eval suite's scaffolding (assignment deliverable #3) and get one
real dataset running end-to-end: `pydantic_evals.Dataset` → the production
agent → a graded report — before scaling to more datasets or more cases.
Source questions from HotpotQA (Yang et al., 2018), a public multi-hop
Wikipedia QA dataset with a built-in easy/medium/hard difficulty label,
matching this project's Wikipedia-search-tool agent almost exactly.

This first dataset checks **format only**: does the agent's output look like
a real, populated `RunTranscript` (non-empty answer, well-formed tool-call
records)? Not correctness, not faithfulness, not whether search was used —
those are separate future datasets, deliberately out of scope here (see
below). The point of this pass is proving the pydantic-evals wiring works,
not grading answer quality yet.

## Out of scope for this pass

- Correctness, faithfulness, and relevancy datasets/evaluators. Each is a
  new YAML file + new `Evaluator` class once this scaffolding is proven; see
  "Scaling to more datasets" below for the exact shape that takes.
- A generic/parametrized case-count expansion (e.g. "10 per difficulty") —
  this pass ships 3 cases (one per difficulty level), enough to prove the
  wiring works across the full difficulty range without over-investing
  before the pattern is validated.
- Any committed dataset-building script. Sourcing HotpotQA cases is one-time
  curation work, not part of the running system — see "Why no build
  scripts" below.
- CI/pytest integration for the evals themselves (they hit the real
  Anthropic API and live Wikipedia — see "Not wired into pytest/CI" below).
- `pydantic_evals.generation.generate_dataset()` (LLM-synthesized cases) and
  `span_tree`/`SpanQuery`-based evaluators (OTel-instrumentation-based
  tool-call checks) — both real, documented pydantic-evals capabilities
  (confirmed via the library's own examples repo), noted here as available
  options for later, not used now. `RunTranscript` already carries
  everything `SpanQuery` would check (tool name, args, result) without
  requiring OTel instrumentation to be wired up for evals specifically.

## Source: HotpotQA

- Dataset: `hotpotqa/hotpot_qa` on Hugging Face. License CC-BY-SA-4.0 —
  redistributing a hand-picked handful of questions in this public repo is
  fine with attribution (Yang et al. 2018, arXiv:1809.09600; see
  `docs/hotpotqa_1809.09600v1.md`, an extracted, readable copy of the paper
  kept in this repo for reference).
- Split: `train`. `validation` (HotpotQA's "dev set") is 100% `level="hard"`
  — no easy/medium examples exist outside `train`. `test` has null
  answers/level/type (hidden for the official leaderboard) — unusable.
- Config: `distractor` (arbitrary choice — `question`/`answer`/`level`/`type`
  are identical between `distractor` and `fullwiki`; only the unused
  `context` field differs, and this project doesn't use `context` at all
  since the agent does its own live retrieval).
- Selection for this pass: one case per `level` (`easy`, `medium`, `hard`),
  first reasonable match per level when streaming the `train` split
  (`streaming=True`, so this doesn't download/cache the full ~90k-row split
  locally just to pick 3 rows).
- Fields kept per case: `question` (→ `Case.inputs`), `level`, `type`,
  `id` (→ `HotpotQAMetadata`). No `expected_output` — this dataset doesn't
  grade correctness (see "Why format-only" below).

## Why no build scripts

Once a dataset's cases and evaluator(s) are serialized into a committed YAML
file (see "Evaluators live in the dataset file" below), nothing in the
eval-running path ever touches the code that produced it again — the YAML
*is* the artifact, version control *is* the durability mechanism. Keeping a
`build_format_validation_dataset.py` (or a shared `hotpotqa_source.py`)
permanently in the repo means carrying code whose only caller is "a human,
someday, maybe" — the premature-abstraction problem CLAUDE.md already warns
against, worse here because there's only one dataset so far, meaning there
isn't even a second caller yet to justify factoring anything out.

Concretely: the HotpotQA sourcing for `format_validation.yaml` happens once,
interactively, during implementation of this plan — not as a script left in
the repo. The sourcing methodology (dataset, config, split, selection
criteria, license attribution) is recorded as a comment header in the
generated YAML file itself, so it's traceable without needing runnable code.

`datasets` (the Hugging Face library) stays a dev-only dependency
(`[dependency-groups] dev` in `pyproject.toml`) per explicit instruction,
even though nothing in the committed code imports it — it's there so that
whoever next curates more HotpotQA cases (most likely: a future session
building the correctness dataset) has it available for that one-off work.
`CONTRIBUTING.md` gets a short note on this (see "Documentation updates").

If a second HotpotQA-sourced dataset's build step turns out to need
materially the same fetch/filter/mapping logic, *that's* the signal to
factor it into a real shared module — not before.

## Why format-only, and why metadata stays minimal

Two related scoping decisions, both aimed at keeping this pass's files
single-reason-to-change as the eval suite grows:

**Format-only, not format+correctness.** `RunTranscript` is a `pydantic.BaseModel`
already validated by construction (`run_agent` either returns a fully-typed
`RunTranscript` or raises — never a malformed one). So "format validation"
isn't really schema-checking (Python's type system already guarantees that);
it's a **structural smoke check** that the model's fields are actually
populated meaningfully, not just present — answer non-empty, tool-call
records non-empty. This is deliberately kept separate from correctness
(does the answer match HotpotQA's expected answer?), which is its own
dataset+evaluator next, per pydantic-evals' own recommended "separate
datasets by purpose" convention (confirmed in the docs: `smoke_tests.yaml`,
`comprehensive_tests.yaml`, `regression_tests.yaml` as the pattern).

**Metadata stays HotpotQA-provenance-only, not pre-loaded with
`expected_answer`.** An earlier version of this design put `expected_answer`
into a metadata model shared by every dataset "for later use." That's a
coupling smell: a metadata type shared across every dataset means *any*
dataset's new need forces a change to a type every *other* dataset also
depends on, even though most don't care about that field. The fix: the
shared metadata model (`evaluations/models.py`, `HotpotQAMetadata`) carries
only what's genuinely cross-cutting — `level`, `type`, `hotpotqa_id`
(provenance, useful for every HotpotQA-sourced dataset regardless of
purpose). Purpose-specific grading data (like a future correctness dataset's
expected answer) gets defined next to the evaluator that reads it, when that
dataset is actually built — not preemptively.

## File layout

```
evaluations/
  datasets/
    format_validation.yaml            # 3 cases + TranscriptWellFormed baked in
    format_validation_schema.json     # auto-generated by Dataset.to_file()
  models.py                           # HotpotQAMetadata (level, type, hotpotqa_id)
  evaluators.py                       # TranscriptWellFormed, CUSTOM_EVALUATOR_TYPES
  task.py                             # production_task() context manager
  run.py                              # generic: `python -m evaluations.run <dataset_name>`
```

No `__init__.py` — same convention as `app/`, relies on `pythonpath = ["."]`
already set in `pyproject.toml` and implicit namespace packages.

### `evaluations/models.py`

```python
from typing import Literal

from pydantic import BaseModel


class HotpotQAMetadata(BaseModel):
    """Cross-cutting provenance for a HotpotQA-sourced case. Purpose-specific
    grading data lives next to the evaluator that reads it, not here."""

    level: Literal["easy", "medium", "hard"]
    type: Literal["comparison", "bridge"]
    hotpotqa_id: str
```

### `evaluations/evaluators.py`

```python
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

### `evaluations/task.py`

The one production entrypoint every dataset's cases run through — CLI and
evals both end up calling `run_agent` with identically-constructed
arguments, so neither is special-cased and the agent has no notion of who's
calling it.

```python
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.agent import agent, resolve_real_model
from app.runner import RunTranscript, run_agent
from app.tools import build_wikipedia_client


@contextmanager
def production_task() -> Iterator[Callable[[str], RunTranscript]]:
    """One client, reused across every case in a run, for connection pooling —
    this is the "eval suite" lifecycle the original agent-scaffold design
    anticipated (CLI: one client per question; evals: one per batch)."""
    model = resolve_real_model()
    with build_wikipedia_client() as client:

        def answer_question(question: str) -> RunTranscript:
            return run_agent(agent, question, deps=client, model=model)

        yield answer_question
```

### `evaluations/run.py`

```python
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

Generic by design: adding a new dataset never touches this file, only its
own new YAML + whatever `evaluators.py`/`models.py` additions it needs (see
"Scaling to more datasets").

## Required refactor: shared production wiring

`query_agent.py`'s `_resolve_real_model()` and its inline
`httpx.Client(headers={"User-Agent": ...}, timeout=30.0)` construction are
exactly the wiring `evaluations/task.py` also needs. Duplicating them would
mean two copies of the same production configuration that could silently
drift (e.g. a timeout change applied to one and not the other) — the
opposite of "the agent doesn't know who's calling it." Fix: promote both to
the modules that already own the concepts they configure, not to a new
module:

- `app/tools.py`: add `build_wikipedia_client(timeout: float = 30.0) ->
  httpx.Client`, next to the `WIKIPEDIA_USER_AGENT` constant it wraps.
  Returns an unopened, correctly-configured client — lifecycle (open/close)
  stays with the caller, per the existing design doc's rationale (CLI wants
  one client per question; evals want one per batch).
- `app/agent.py`: add `resolve_real_model(settings: Settings | None = None)
  -> Model`, next to the `agent` object it configures.
- `query_agent.py`: drop its private `_resolve_real_model()` and inline
  client construction; import and use the two functions above instead.

## Not wired into pytest/CI

Evals hit the real Anthropic API and live Wikipedia — slow, costly, and
flaky to run on every commit. They stay a manual `uv run python -m
evaluations.run format_validation` command, never invoked by
pytest/pre-commit/CI. `TranscriptWellFormed.evaluate()`'s pure logic does
get a fast unit test (`tests/unit/test_evaluators.py`, constructed
`RunTranscript` fixtures, no live calls, no `EvaluatorContext` network
dependency) — consistent with CLAUDE.md's test-pyramid principle. Light unit
coverage is also added for the two new `app/` functions
(`resolve_real_model`, `build_wikipedia_client`) alongside existing
`test_agent.py`/`test_tools.py`.

## Scaling to more datasets (illustrative — not built this pass)

Adding a `correctness` dataset later costs exactly:

1. One new `evaluations/datasets/correctness.yaml` (fresh HotpotQA sample,
   this time with `expected_output` populated, cases assembled the same
   one-off way as `format_validation.yaml`).
2. One new `AnswerMatchesExpected` evaluator appended to `evaluators.py`
   (`CUSTOM_EVALUATOR_TYPES` grows to include it).
3. Nothing else. `models.py`, `task.py`, and `run.py` are untouched;
   `uv run python -m evaluations.run correctness` just works because
   `run.py` never knew or cared which dataset it was running.

Faithfulness follows the identical shape later: new YAML, new `Faithfulness`
evaluator (likely `pydantic_evals.evaluators.LLMJudge`-based, reading
`ctx.output.answer` against `ctx.output.tool_calls` as evidence — confirmed
`LLMJudge` is a real built-in via the library's docs), zero changes anywhere
else.

`evaluators.py` growing by addition, forever, is intentional and fine — its
one job *is* "grading logic for this eval suite," so accumulating evaluators
is consistent with a single reason to change, not a violation of it. Split
it into multiple files only if it gets large enough that CLAUDE.md's
existing "large file is a signal it's doing too much" guidance kicks in —
not preemptively.

## Documentation updates required alongside implementation

- **CLAUDE.md** — Architecture section: new bullets for
  `evaluations/{models,evaluators,task,run}.py` and `datasets/*.yaml`,
  matching the existing one-liner-per-file style, including the dependency
  direction (`evaluations/*` → `app/*` only, never `app/query_agent.py`,
  mirroring the existing rule for `query_agent.py` itself). Commands
  section: add `uv run python -m evaluations.run <dataset_name>`. New notes:
  evals are manual only (not pytest/pre-commit/CI, hit real API + network);
  `datasets` is a dev-only dependency for one-off HotpotQA curation, no
  committed script imports it; HotpotQA attribution (CC-BY-SA-4.0, Yang et
  al. 2018) and a pointer to `docs/hotpotqa_1809.09600v1.md`.
- **README.md** — replace the current "not yet built" Evals stub with a
  short, consumer-focused section: what the eval suite measures, a link to
  the HotpotQA paper extract, and the one command to run it. No
  implementation depth (that belongs in CLAUDE.md/this spec) — running the
  shipped dataset needs no new setup beyond what the CLI already requires
  (same API key, same network access; `datasets` is dev-only and not needed
  to *run* an already-built dataset). Keep it as tight as the existing
  Quickstart section.
- **CONTRIBUTING.md** — short note under "Notes": how to add more
  HotpotQA-sourced cases (use the `datasets` dev dependency interactively,
  build `Case`/`Dataset` objects per `evaluations/models.py`/`evaluators.py`,
  call `Dataset.to_file(...)`) — pointing at `format_validation.yaml`'s own
  header comment as the worked example, rather than re-explaining the
  methodology twice.

## Testing

- **Unit** (low gear): `TranscriptWellFormed.evaluate()` against constructed
  `RunTranscript` fixtures (empty answer, whitespace-only answer, empty
  tool-call result, all-well-formed case) — no I/O, no `pydantic_ai` run.
  `resolve_real_model()` and `build_wikipedia_client()` get light coverage
  alongside the existing `test_agent.py`/`test_tools.py`.
- **Real end-to-end**: running `uv run python -m evaluations.run
  format_validation` by hand during implementation, against the real API and
  live Wikipedia, confirming the report prints and all three cases pass — is
  the acceptance check for this pass, not an automated test (per "Not wired
  into pytest/CI" above).
