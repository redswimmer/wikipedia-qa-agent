# Wikipedia Q&A Agent

A question-answering system powered by Claude with a `search_wikipedia` tool. Ask
it a question; it decides whether Wikipedia search is needed, looks things up if
so, and answers — telling you whether search was used.

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python 3.13 is pinned via `uv`, no separate
  install needed)
- An [Anthropic API key](https://console.anthropic.com/settings/keys)

## Setup

```bash
uv sync
cp .env.example .env
# then edit .env and set ANTHROPIC_API_KEY
```

## Usage

Ask a question:

```bash
uv run python -m app.agent "When was the Eiffel Tower built?"
```

Run the built-in demo (a handful of sample questions, no typing required):

```bash
uv run python -m app.agent --demo
```

Each answer is printed along with whether the Wikipedia search tool was used to
produce it.

## Evals

The eval suite that measures answer quality lives in [`tests/`](tests/). See
[`docs/`](docs/) for the design rationale behind the prompt and eval approach.
