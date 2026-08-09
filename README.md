# Wikipedia Q&A Agent

[![CI](https://github.com/redswimmer/wikipedia-qa-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/redswimmer/wikipedia-qa-agent/actions/workflows/ci.yml)

A question-answering agent powered by Claude with a `search_wikipedia` tool. Ask
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

Example Response:

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

## Evals

The eval suite grades the two halves of correct behavior — answering well,
and knowing when not to answer at all:

```bash
uv run python -m evaluations.run refusal
uv run python -m evaluations.run wikipedia_answer_quality
```

- **Refusal** (`refusal`) — does the agent correctly decline questions Wikipedia search can't
  help with (unsafe requests, gibberish, or things unanswerable in principle), instead of
  guessing or searching for nonsense? 50 hand-authored cases.
  - `MaxToolCalls(max_calls=0)` — a hard ban on calling `search_wikipedia` at all for these
    cases.
  - `LLMJudge` (refusal quality) — was the refusal itself clear and appropriately delivered?
  - `LLMJudge` (safety) — did it avoid leaking anything unsafe while declining?
- **Wikipedia answer quality** (`wikipedia_answer_quality`) — is the answer actually *good*?
  50 hard, multi-hop HotpotQA questions.
  - `MaxToolCalls(max_calls=2)` / `ToolCorrectness` — a tool-call budget confirming
    `search_wikipedia` was actually used (not answered from memory), and not overused.
  - `LLMJudge` (correctness) — does the answer match the known gold answer?
  - `LLMJudge` (faithfulness) — is every claim grounded in what `search_wikipedia` actually
    retrieved, not fabricated?
  - `LLMJudge` (relevance) — does the answer address the specific question asked?
  - `LLMJudge` (safety) — reused verbatim from `refusal`'s rubric, as a defense-in-depth check
    on ordinary QA output.

Together these two datasets cover the system's full decision space: answer
correctly when Wikipedia can help, decline cleanly when it can't.
