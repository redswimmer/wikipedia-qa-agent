# Contributing

## Setup

1. Install [uv](https://docs.astral.sh/uv/) if you don't have it.
2. Install dependencies:

   ```bash
   uv sync
   ```

3. Install the git hooks:

   ```bash
   uv run pre-commit install
   ```

   Every commit runs Ruff (lint + format), `ty` (type
   checking), and the test suite. If it isn't installed, you're just hoping
   your code would have passed — install the hook.

## Quality gates

Every commit is checked by:

- **`ruff check --fix`** — lint, with autofix
- **`ruff format`** — formatting
- **`ty check`** — static type checking
- **`pytest`** — test suite

These run automatically via pre-commit. If a hook fails, fix the issue and
commit again — don't bypass it.

You can also run them by hand at any time:

```bash
uv run ruff check .
uv run ruff format .
uv run ty check
uv run pytest
```

Or run every hook against the whole repo without committing:

```bash
uv run pre-commit run --all-files
```

## Notes

- This is a standalone `uv` project — `uv sync` creates its own `.venv` here
  and resolves against this repo's own `uv.lock`. Don't nest it inside a
  parent `uv` workspace: this repo is submitted/cloned standalone (and CI
  checks out only this repo), so a shared workspace lockfile above it can
  silently drift from what's actually committed here — `uv add` would
  update the *workspace's* lockfile instead of this repo's, leaving
  `uv sync --locked` broken for anyone who clones just this repo.
- Requires Python >= 3.13 (see `pyproject.toml`).
- To add more HotpotQA-sourced cases to an eval dataset: use the
  `datasets` dev dependency interactively (e.g. `datasets.load_dataset("hotpotqa/hotpot_qa",
  "distractor", split="validation", streaming=True)`), build `Case`/`Dataset`
  objects per `evaluations/models.py`, and call
  `Dataset.to_file(...)`. See `evaluations/datasets/wikipedia_answer_quality.yaml`'s
  header comment for the exact methodology used last time — no build script
  is kept in the repo, only the resulting YAML (see the design doc under
  `docs/superpowers/specs/` for why).
- Hand-authored datasets (no external source, e.g. `refusal`) follow the
  same no-build-script rule — build `Case`/`Dataset` objects directly with
  the literal question text and run `Dataset.to_file(...)` once. See
  `evaluations/datasets/refusal.yaml`'s header comment for that dataset's
  methodology (category/phrasing dimensions).
- When adding an `LLMJudge`-based evaluator: always pass `model=` explicitly
  (it defaults to `'openai:gpt-5.2'`, and this project has no OpenAI key).
  Also note `LLMJudge`'s `model` field always round-trips through a
  committed YAML as a plain model string — `pydantic_evals` serializes any
  `Model` instance back to its `model_id` on save — so at evaluate-time it
  always resolves via `ANTHROPIC_API_KEY` in the process environment, not
  through this project's `Settings`/`.env` mechanism. `evaluations/run.py`
  already exports the key from `Settings` before evaluating, so this works
  automatically for any dataset — but it's why `LLMJudge` can't carry an
  explicit provider/key the way `app.bootstrap.resolve_real_model()` does
  for the agent under test.
