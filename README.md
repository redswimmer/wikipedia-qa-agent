# Wikipedia Q&A Agent

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

Example Response:

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

## Evals

The eval suite (assignment deliverable #3) grades the agent against two
datasets so far:

```bash
uv run python -m evaluations.run format_validation  # output is well-formed
uv run python -m evaluations.run refusal             # correctly declines what it should
```

- **`format_validation`** — a small, hand-picked set of Wikipedia-grounded
  questions from [HotpotQA](https://huggingface.co/datasets/hotpotqa/hotpot_qa)
  (Yang et al., 2018 — see `docs/hotpotqa_1809.09600v1.md`), spanning
  easy/medium/hard difficulty. Checks the agent's output is well-formed (a
  real answer, well-formed tool-call records).
- **`refusal`** — 30 hand-authored questions the agent should decline to
  answer because no Wikipedia search can resolve them: unsafe requests,
  gibberish, and questions unanswerable in principle (personal to the user,
  or unknowable). Checks the agent makes zero tool calls and that its
  refusal is polite, clear, and safe.

Correctness and faithfulness grading come next.

No new setup beyond the Quickstart above: running an already-built dataset
needs the same API key and network access as the CLI, nothing more.
