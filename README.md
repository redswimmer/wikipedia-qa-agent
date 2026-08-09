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
uv run python -m app.query_agent "When was the Eiffel Tower built?"
```

The output shows the question, every Wikipedia search the agent performed
(with its query and the result), and the final answer — so you can see
exactly what the agent looked up before answering, not just the answer
itself.

## Evals

The eval suite that measures answer quality (assignment deliverable #3) is
not yet built.
