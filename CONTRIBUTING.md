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

- This project is a member of a `uv` workspace rooted two directories up.
  `uv run`/`uv sync` from this directory resolve against that shared
  workspace environment and lockfile — you don't need a separate virtualenv
  here.
- Requires Python >= 3.13 (see `pyproject.toml`).
