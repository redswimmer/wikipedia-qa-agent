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
