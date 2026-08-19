# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

An Anthropic take-home assignment: build a question-answering system that uses
Claude plus a `search_wikipedia(query: str)` tool, and an eval suite that
measures how well it works. Full spec: `docs/assignment_instructions.md`. Key
constraint from that spec — no built-in hosted search/RAG tools (e.g.
Anthropic's `web_search` tool type); the retrieval integration must be
hand-built.

**Deliverable #3 (design rationale) lives in `README.md`'s "Design
rationale" section** — that's what a reviewer reads: prompt approach, eval
dimensions, successes/failures, iterations, extensions, time spent.
**`docs/eval_notes.md`** is supplementary, not the deliverable — the
working detail behind it (specific run numbers, concrete failure
examples, incident narratives) kept out of the README so that section
stays readable. Update it whenever a new eval dataset, finding, or
prompt/agent iteration lands, not only at the end; pull anything
reviewer-worthy up into the README yourself rather than leaving it
stranded here.

## Commands

```bash
uv sync                          # install deps
uv run pre-commit install        # one-time: wire up git hooks

uv run ruff check .              # lint
uv run ruff format .             # format
uv run ty check                  # type check
uv run pytest                    # full test suite
uv run pytest tests/unit/test_tools.py  # one file
uv run pre-commit run --all-files  # run every quality gate without committing

uv run python -m app.query_agent "your question"  # ask a question
uv run python -m evaluations.run answer_quality  # run an eval dataset (hits real API + Wikipedia)

# capturing a run's report to a file for the record (e.g. evaluations/results/)?
# widen the terminal width first — Rich defaults to 80 cols off-tty, which
# truncates the Case ID column and wraps everything else one word per line:
COLUMNS=250 uv run python -m evaluations.run answer_quality > evaluations/results/<name>.txt
```

Every commit runs ruff (lint + format), `ty`, and pytest via pre-commit; the
same checks run in CI (`.github/workflows/ci.yml`). A hook failure blocks the
commit — fix and re-commit rather than bypassing it.

This is a standalone `uv` project — `uv sync`/`uv run` resolve against this
repo's own `.venv` and `uv.lock`, nothing outside it. (It briefly lived as
a member of a single-purpose parent workspace; that caused `uv add` to
silently update the wrong lockfile — a real bug this history exists to
prevent regressing. Keep it standalone.)

## Design principles

Guiding constraints for how code in this repo should be shaped — apply
judgment about what they mean concretely once the actual design takes shape;
don't treat any specific class/module name below as prescribed.

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

### Background: cosmicpython abstractions and test pyramid

Paraphrased (not excerpted) notes on the two cosmicpython chapters behind the
principles above, kept here so the reasoning can be referenced without
re-fetching the source:

- Chapter 3, "A Brief Interlude: On Coupling and Abstractions":
  https://www.cosmicpython.com/book/chapter_03_abstractions.html
- Chapter 5, "TDD in High Gear and Low Gear":
  https://www.cosmicpython.com/book/chapter_05_high_gear_low_gear.html

Both are from *Architecture Patterns with Python* by Harry Percival and Bob
Gregory (O'Reilly).

**Chapter 3: abstractions and coupling.** The chapter's core argument is that
tightly coupling business logic directly to I/O (filesystems, networks,
databases) makes code expensive to test and change, because every test of
the logic has to go through the slow, messy real thing. The fix isn't "add
more mocks" — it's finding the right abstraction to put between the logic
and the I/O.

Their running example is a file-sync tool. Instead of writing code that
walks the filesystem and issues copy/move/delete calls inline with the
comparison logic, they factor it into three separate concerns: (1) read the
real state of the world into a simple data structure (e.g. a dict mapping
content hashes to file paths), (2) run pure comparison logic against that
data structure to decide what *should* happen, expressed as plain data (e.g.
tuples like `("COPY", src, dest)`) rather than as direct filesystem calls,
and (3) interpret that plain data and apply the actual I/O. The key move is
representing both "the state of the world" and "the actions to take" as
ordinary data structures instead of objects that do things — that turns the
interesting logic into something you can unit test with plain Python values
and no I/O at all.

Rules of thumb they offer for finding this kind of seam: can messy,
real-world state be represented with a familiar data structure (dict, list,
tuple, dataclass)? Separate *what* should happen from *how* it gets
executed. Look for a natural boundary where a simplifying abstraction could
sit. What responsibilities are currently tangled together that could be
split into distinct, named components?

On testing: they explicitly argue against reaching for `mock.patch` as the
default way to isolate code from I/O. Patching lets you test code without
first designing a clean seam, which means the coupling problem never
actually gets fixed — it just gets hidden by the mock. Their preferred
alternative is dependency injection with a hand-written fake (e.g. an
in-memory fake filesystem) that implements the same interface as the real
thing. Because the fake is a real object with real (if simplified) behavior,
tests using it exercise the actual entrypoint logic edge-to-edge, not just
the parts convenient to patch.

**Chapter 5: the test pyramid, high gear and low gear.** The chapter uses a
bicycle-gears metaphor for two different testing modes, and argues most
projects should use both, at different times:

- **Low gear — domain-layer tests.** Tests written directly against core
  business-logic objects. High effort per unit of coverage, tightly coupled
  to implementation details (so they break when internals change even if
  behavior doesn't), but they give strong design feedback and read as
  precise documentation of the domain rules. Best suited to the early,
  exploratory phase of building something new or genuinely complex, where
  you're still discovering what the right domain model even is.
- **High gear — service-layer tests.** Tests written against a layer that
  sits above the domain model — the entry points application code actually
  calls. Looser coupling to internals (so refactors don't break them), wider
  coverage per test, and they still avoid real I/O by using fakes for
  anything external. Best suited to routine, ongoing feature work and bug
  fixes once the domain model has stabilized.

They recommend most of a project's test suite live at the service layer once
past the initial exploratory phase: a small number of domain-layer tests kept
for the trickiest business rules (or deleted once service-layer tests cover
the same ground), a larger set of service-layer tests doing the bulk of edge
case coverage, and a small number of true end-to-end tests — roughly one per
user-facing feature — that exercise the real entry point (e.g. an HTTP API)
to confirm the pieces are wired together correctly. Their reasoning: as the
proportion of slow, brittle tests grows, the whole suite gets slower and
harder to maintain, so the fast, loosely-coupled layer should carry most of
the weight.

A related piece of guidance: service-layer functions should take primitive
arguments (strings, ints, plain dicts) rather than requiring the caller to
construct domain objects by hand. If writing a service-layer test keeps
needing you to reach into domain internals to set up state, that's a signal
the service layer is missing an operation — add it, rather than working
around the gap in the test.

## Auditability

Every agent run must produce an inspectable record of what happened — each
tool call (name, arguments, result) and the final answer — not just the
answer text. Build this from Pydantic AI's own message history
(`result.new_messages()`, walking `ToolCallPart`/`ToolReturnPart`), as
`app/runner.py`'s `run_agent()` does — not hand-rolled logging, and not a
mutable context object tools write into themselves (that couples every tool
to a logging contract and can drift from what the model actually saw).

## Architecture

- `app/config.py` — env-driven settings (`Settings`: Anthropic API key + model,
  read from `.env`).
- `app/tools.py` — the `search_wikipedia` tool: MediaWiki search + extract
  retrieval (functional core / imperative shell split within the module).
  `build_wikipedia_client()` takes an optional `transport` so tests drive the
  *real* factory against an `httpx.MockTransport` — that's what makes the
  User-Agent and request parameters assertable on the wire instead of only
  on a client object the test built itself.
- `app/prompts.py` — the agent's system prompt.
- `app/agent.py` — the module-level `agent` (registers `search_wikipedia`,
  no model bound). Provider-agnostic: no `Settings`/`.env` dependency, no
  concrete model construction, no CLI/argparse/printing logic — this is the
  reusable core, tested with `TestModel`/`FunctionModel`, never a real
  provider.
- `app/bootstrap.py` — `resolve_real_model(settings=None)`: resolves the
  real Anthropic model from `Settings` when no settings are given. Kept
  separate from `agent.py` on purpose — this is the composition root for
  production wiring (imports `Settings`, `AnthropicModel`,
  `AnthropicProvider`), not part of the agent's core definition. Used by
  `query_agent.py` and `evaluations/task.py`, never by `agent.py` itself.
- `app/runner.py` — `run_agent(agent, question, deps, model)`: runs a
  question through the agent and returns an auditable `RunTranscript` built
  from Pydantic AI's own message history (see Auditability above). Shared
  by the CLI and the eval suite (`evaluations/task.py`) — neither depends
  on the other.
- `app/query_agent.py` — the CLI entrypoint (`python -m app.query_agent`).
  The only module with argparse/printing/CLI-specific error handling;
  depends on `agent.py` and `runner.py`, and nothing else depends on it.
  `main()` injects both `model_factory` and `client_factory` (defaulting to
  the real ones) so its whole path is testable offline. Keep both seams: with
  only `model_factory`, any path where the model calls a tool would hit live
  Wikipedia, so the CLI's tool-calling and retry output went untested and the
  tests sat on private display helpers instead.
- `evaluations/` — the eval suite (assignment deliverable #3).
  `models.py` (per-dataset metadata models — `HotpotQAMetadata`:
  `level`/`type`/`hotpotqa_id`; `RefusalMetadata`: `category`/`phrasing`;
  purpose-specific grading data, e.g. a future correctness dataset's
  expected answer, lives next to the evaluator that reads it, not here —
  keeps this file's reason to change singular). Both current datasets grade
  entirely with native `pydantic_evals` evaluators (`MaxToolCalls`,
  `ToolCorrectness`, `LLMJudge`) — no custom `Evaluator` subclass exists in
  the repo, by design: prefer a native evaluator over a hand-rolled one
  whenever one exists, and only add a custom class (in a new
  `evaluators.py`) when a dataset's check genuinely can't be expressed
  natively. `task.py` (`production_task(model=None, client=None)`: the one
  production entrypoint every dataset's cases run through — defaults to
  `app.bootstrap.resolve_real_model()` + `app.tools.build_wikipedia_client()`
  wrapped around `app.runner.run_agent()`; reused unchanged across every
  dataset. Both deps are injectable *only* so this entrypoint is testable
  without an API key; an injected client belongs to the caller and is not
  closed here). `run.py`
  (generic: `uv run python -m evaluations.run <dataset_name>` — never
  touched when adding a new dataset, since the dataset name is just an
  argument; loads datasets as `Dataset[str, RunTranscript, Any]` —
  deliberately loose on the metadata type, since each dataset defines its
  own metadata model and the runner never reads metadata fields itself —
  then attaches that dataset's `LLMJudge` evaluators via
  `judges.for_dataset(name)`). `judges.py` — maps a dataset name to its
  `LLMJudge` evaluators, each built by reading a `judge_prompts/*.md` file
  verbatim. `judge_prompts/*.md` — one file per judge rubric, whose
  *entire* content is the prompt string the judge receives: no headings, no
  fences, no frontmatter, and read with no strip/templating, so the file a
  reviewer opens is byte-for-byte what the judge is sent. Editing one edits
  the live prompt; don't add anything to these files that isn't meant to
  reach the judge. Named to pair with `app/prompts.py` — the two kinds of
  prompt in this system, both plain readable text. `safety.md` is shared by
  both datasets on purpose. (GitHub's rendered view swallows the
  `<example>` tags — that's expected; don't "fix" it by escaping or
  fencing, which would change the prompt text.) `judge_prompts/README.md`
  is the one file there that *isn't* a prompt — `judges.py` names the
  prompt files it loads explicitly, so a README is safe; GitHub renders it
  automatically when the directory is opened, which is where a reviewer
  browsing `evaluations/` lands. It carries the reader-facing framing (the
  files are the prompts, use the raw view, shared judging design) plus a
  table of each rubric and which dataset uses it. `datasets/*.yaml` — one file per eval purpose; cases and their
  *native* evaluators (`MaxToolCalls`/`ToolCorrectness`) are serialized
  together via `Dataset.to_file(...)`, with an auto-generated
  `*_schema.json` sibling for IDE autocomplete. `LLMJudge` evaluators are
  deliberately *not* serialized there — they attach at load time from
  `judge_prompts/` instead. When round-tripping a YAML through
  `from_file`/`to_file`, load it with its real metadata model
  (`RefusalMetadata`/`HotpotQAMetadata`, not `Any`) or the regenerated
  schema silently loses the metadata types, and re-add the hand-written
  `#` header comments, which `to_file` drops. Depends only on `app/*`,
  never `app/query_agent.py` — same rule as `query_agent.py` itself. `results/` — raw `report.print()`
  output from notable live runs, committed on purpose (not gitignored):
  reviewers don't have an API key to run evals themselves, so these are the
  only live evidence they see. Capture with the wide-`COLUMNS` invocation
  above; findings worth a reviewer's attention get distilled from these into
  `eval_notes.md`/README, not left as raw files for someone to dig through.
- OpenTelemetry/Logfire: `app/agent.py` sets `agent.instrument = True` on
  the shared `agent` object (harmless without a configured tracer — spans
  go to a no-op provider; only `evaluations/run.py` actually configures one,
  locally-only via `logfire.configure(send_to_logfire="if-token-present",
  ...)`, so plain `query_agent.py` CLI usage is unaffected). This exists so
  span-based native evaluators (e.g. `MaxToolCalls`, `ToolCorrectness`)
  work — both datasets rely on these for tool-call counts/identity,
  matching `pydantic_evals`' own documented pattern for that kind of check.
  Note: `LLMJudge`'s `model` field always round-trips through a committed YAML as
  a plain model string (pydantic_evals serializes any `Model` instance back
  to its `model_id`), so it resolves via `ANTHROPIC_API_KEY` in the process
  environment at evaluate-time, not through this project's `Settings`/`.env`
  mechanism — `evaluations/run.py` exports it from `Settings` once, before
  evaluating, specifically so `LLMJudge`-based evaluators work.
- Evals hit the real Anthropic API and live Wikipedia — they are run
  manually (`uv run python -m evaluations.run <dataset_name>`), never by
  pytest/pre-commit/CI. Code quality on `evaluations/*.py` is *not*
  excluded: ruff/ty run repo-wide with no path exclusions, and
  `tests/unit/test_datasets.py` loads every dataset YAML for real — only
  the live agent execution itself stays manual.
- HotpotQA-sourced datasets: no build script is committed — sourcing is
  one-off curation work (see `docs/superpowers/specs/2026-08-09-pydantic-evals-hotpotqa-design.md`
  for why), and only its output (the YAML + schema) lands in the repo.
  `datasets` (Hugging Face) is a dev-only dependency for that curation work;
  nothing in the committed code imports it. HotpotQA (Yang et al. 2018,
  arXiv:1809.09600, CC-BY-SA-4.0) is extracted to
  `docs/hotpotqa_1809.09600v1.md` for reference. The `refusal` dataset is
  hand-authored (not HotpotQA-sourced) — no external dataset, same
  no-build-script rule applies.
- Tests live in `tests/unit/`, with shared fakes in `conftest.py`: the
  `MediaWiki` response builders (one place knows the wire format, so a shape
  change is a one-line edit), `wikipedia_mock_transport`, `tool_context` (a
  minimal `RunContext` for calling `search_wikipedia` directly, so each
  `ModelRetry` message can be asserted on its own rather than via a bespoke
  `FunctionModel` per case; the transcript route is still used where the
  retry's *recording* is the point),
  and the shared `FunctionModel` behaviours. A test that pokes a pure helper or
  a private function has to earn it: the bar is that mutating what it guards
  must survive the rest of the suite (mutate the behaviour, deselect the test,
  re-run — if another test fails, the low-gear one is glue and goes). Prefer
  making a fake more realistic over keeping a helper test — the search fake
  returns a runner-up title precisely so "the first result" is observable from
  the entrypoint. Assert *behaviour*, not census:
  dataset tests check properties (every category present, roughly balanced,
  `MaxToolCalls` budget) rather than exact per-category counts, since pinning
  counts means adding a good case fails the suite. `tests/unit/test_datasets.py`
  loads each committed dataset YAML for real (via `Dataset.from_file`),
  resolving paths from `evaluations.run.DATASETS_DIR` so it passes from any
  cwd, so a renamed evaluator or YAML typo fails fast in pytest instead of
  only surfacing on a live run. The eval suite has two datasets,
  covering the two halves of correct behavior: `refusal` (50
  hand-authored questions the agent should decline — unsafe/gibberish/
  unanswerable — checked via native `MaxToolCalls(max_calls=0)` plus two
  `LLMJudge` evaluators for refusal quality and safety, judged by a
  different model than the agent under test to reduce self-grading bias),
  and `answer_quality` (50 hard-difficulty HotpotQA validation-split
  questions, graded on correctness, faithfulness, relevance, and safety via
  four `LLMJudge` evaluators — `safety` reused verbatim from `refusal` —
  plus a tool-call budget of 1-2 search calls via `MaxToolCalls`/
  `ToolCorrectness`; see
  `docs/superpowers/specs/2026-08-09-hotpotqa-hard-quality-design.md` for
  why these four axes are bundled onto one dataset rather than split like
  the other two).
- `pyproject.toml` sets `pythonpath = ["."]` under `[tool.pytest.ini_options]`.
  This is required: `app/` has no `__init__.py`/package install, so without it
  pytest's default import mode can't resolve `app.*` imports even though a
  plain `python -c "import app.agent"` from the repo root works fine.
- Anthropic API key is read from `.env` (see `.env.example` for the variable
  name); `.env` is gitignored.
- README.md is consumer-facing (setup + usage for someone running the
  prototype); CONTRIBUTING.md is contributor-facing (dev environment, quality
  gates). Keep that split when adding docs.
