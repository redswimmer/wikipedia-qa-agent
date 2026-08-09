# Wikipedia Q&A Agent

[![CI](https://github.com/redswimmer/anthropic-take-home-assignment/actions/workflows/ci.yml/badge.svg)](https://github.com/redswimmer/anthropic-take-home-assignment/actions/workflows/ci.yml)

A question-answering system powered by Claude with a `search_wikipedia` tool. Ask
it a question; it decides whether Wikipedia search is needed, looks things up if
so, and answers — telling you whether search was used.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and an [Anthropic API key](https://console.anthropic.com/settings/keys).

```bash
# Install Dependencies
uv sync
# Copy environment example and set your Anthropic API key
cp .env.example .env
# Query the agent
uv run python -m app.query_agent "In what year was the Eiffel Tower completed?"
```

Example Response (streams live — tool calls to stderr, answer to stdout):

```
Tool calls:
  → search_wikipedia(query='Eiffel Tower')
  ← The Eiffel Tower (  EYE-fəl; French: Tour Eiffel [tuʁ ɛfɛl] ) is a lattice
    tower on the Champ de Mars in Paris, France. It is named after the
    engineer Gustave Eiffel, whose company designed and built the tower
    from 1887 to 1889...
    [truncated for length]

Answer:
The Eiffel Tower was completed in 1889, having been built by Gustave
Eiffel's company from 1887 to 1889 as the centerpiece of the 1889 World's
Fair in Paris.
```

`2>/dev/null` gets you just the answer.

## Evals

The eval suite (assignment deliverable #3) grades the agent along two
dimensions so far:

```bash
uv run python -m evaluations.run format_validation
uv run python -m evaluations.run refusal
```

- **Format validation** — does the agent produce a real answer with a real
  audit trail? The baseline sanity check, before grading answer quality at
  all.
- **Refusal** — does the agent correctly decline questions Wikipedia search
  can't help with (unsafe requests, gibberish, or things unanswerable in
  principle), instead of guessing or searching for nonsense?

Correctness and faithfulness grading come next. See
`docs/design_rationale.md` for what each eval measures and why, and what
we've learned so far.

No new setup beyond the Quickstart above: running an already-built dataset
needs the same API key and network access as the CLI, nothing more.
