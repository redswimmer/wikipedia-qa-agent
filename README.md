# Wikipedia Q&A Agent

A question-answering system powered by Claude with a `search_wikipedia` tool. Ask
it a question; it decides whether Wikipedia search is needed, looks things up if
so, and answers — telling you whether search was used.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) (Python 3.13 is pinned via `uv`, no
separate install needed) and an
[Anthropic API key](https://console.anthropic.com/settings/keys).

```bash
uv sync
cp .env.example .env   # then edit .env and set ANTHROPIC_API_KEY
uv run python -m app.query_agent "In what year was the Eiffel Tower completed?"
```

That's it — that one command asks the agent a question and prints its answer.
Here's real output from that exact command:

```
Question: In what year was the Eiffel Tower completed?

Tool calls:
  1. search_wikipedia(query='Eiffel Tower')
     → The Eiffel Tower (  EYE-fəl; French: Tour Eiffel [tuʁ ɛfɛl] ) is a lattice
       tower on the Champ de Mars in Paris, France. It is named after the
       engineer Gustave Eiffel, whose company designed and built the tower from
       1887 to 1889. Locally nicknamed "La dame de fer" (French for "Iron
       Lady")...
       [...]

Answer:
The Eiffel Tower was completed in 1889.
```

The output always shows three things: the question, every Wikipedia search the
agent ran (its query and what it found), and the final answer — so you can see
exactly what the agent looked up before answering, not just the answer itself.
Ask it anything else the same way:

```bash
uv run python -m app.query_agent "Who wrote the Declaration of Independence?"
```

## Evals

The eval suite that measures answer quality (assignment deliverable #3) is
not yet built.
