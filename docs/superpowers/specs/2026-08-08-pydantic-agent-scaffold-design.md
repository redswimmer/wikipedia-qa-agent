# Pydantic AI agent scaffold — design

Date: 2026-08-08
Status: approved, pending implementation plan

## Goal

Build the runnable prototype (assignment deliverable #1): a Pydantic AI agent
with a `search_wikipedia` tool, invoked from the terminal with a single
question, whose behavior is auditable — every tool call, its result, and the
final answer are visible, not just the answer text. Configuration (which
Anthropic model, the API key) is injected rather than hardcoded, so the same
agent-construction code can run for real or be handed a fake model in tests.

The design also anticipates one concrete piece of future work the user
described: an eval suite that will later run many questions through this same
agent and grade the results. The design deliberately creates one shared,
non-CLI-specific entrypoint (`run_agent`) so that future work is a new
caller, not a refactor.

## Out of scope for this pass

- The eval suite itself (assignment deliverable #3) — only the seam it will
  call (`build_agent`, `run_agent`) is being built now.
- Live/streaming tool-call progress (`event_stream_handler`). Confirmed cheap
  to add later as a sibling function (`run_agent_streaming`) in `runner.py`
  because `search_wikipedia` is a sync tool and works under both
  `agent.run_sync()` and `agent.run()` — nothing about this design forecloses
  it. Not built now because nothing calls it yet (no CLI flag requests it,
  and the eval suite doesn't want per-question stderr chatter).
- Logfire/observability wiring — mentioned only as a documented option
  (already noted in the `ai:building-pydantic-ai-agents` skill), not built.
- Elaborate failure-capture infrastructure (`capture_run_messages()`
  wrapping, structured error fields). A run either succeeds and returns a
  `RunTranscript`, or raises — exceptions already carry clear messages
  (pydantic-settings' `ValidationError`, pydantic_ai's own error types), and
  building more than that now would be guessing at debugging needs the eval
  suite hasn't revealed yet.

## File layout and dependency direction

```
app/config.py   — Settings
app/prompts.py  — SYSTEM_PROMPT
app/tools.py    — search_wikipedia (sync, httpx.Client)
app/agent.py       — build_agent(model=None) -> Agent
app/runner.py      — run_agent(agent, question, deps) -> RunTranscript
app/query_agent.py — argparse, error handling, format_transcript(), main(), __main__
```

`query_agent.py` (not `cli.py`): "CLI" describes a category (anything runnable
from a terminal), not what this specific module does. This module asks the
agent a single question and prints the audited answer — `query_agent` names
that action directly. It also disambiguates it from the eval suite, which
will be an equally-named, equally specific `app/evals.py` later — two named
capabilities instead of one vague "CLI" with a hidden mode inside it. It is
deliberately *not* named `chat.py`: this is single-shot (one question in, one
answer out, process exits), not a multi-turn conversation loop with threaded
`message_history` — a name implying otherwise would misdescribe the code.

Dependencies flow one direction only: `query_agent.py` → `agent.py`,
`runner.py` → `config.py`, `tools.py`, `prompts.py`. Nothing in `agent.py`,
`runner.py`, `tools.py`, `config.py`, or `prompts.py` imports
`query_agent.py` — it's a thin consumer of the agent's API, not the other way
around. This was a real design mistake caught mid-brainstorm (an earlier
draft had `agent.py`'s `__main__` importing the CLI module directly, i.e.
core importing presentation) and is called out here so it doesn't regress:
**`app/agent.py` must stay free of argparse, printing, and CLI-specific
error formatting.**

The eval suite (built later) will import `build_agent` from `app/agent.py`
and `run_agent` from `app/runner.py` directly — never `app/query_agent.py`.
`query_agent.py`'s formatted text output (see below) is for a human reading
a terminal, not a stable interface; the eval suite works with
`RunTranscript` objects directly.

## `app/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-5"
```

`anthropic_model` defaults to `claude-sonnet-5` (confirmed available on the
project's API key by querying `GET /v1/models`; chosen for strong
tool-use/reasoning at lower cost/latency than Opus for an agentic
Wikipedia-QA loop) but is overridable via `.env`'s `ANTHROPIC_MODEL`. Both
`.env` and `.env.example` already carry `ANTHROPIC_API_KEY` and
`ANTHROPIC_MODEL`.

No dependency on `httpx`/`logging` here — config concerns only.

## `app/tools.py`

`search_wikipedia` follows the functional-core/imperative-shell split within
one module (per CLAUDE.md's design principles — the split is at function
granularity, not file granularity, matching the cosmicpython chapter 3
pattern this project already follows):

- **Functional core:** pure function(s) parsing MediaWiki JSON responses
  into plain data (best-matching title from a search response; plain-text
  extract from an extract response). No I/O, directly unit-testable.
- **Imperative shell:** an async-free, sync function that performs two
  MediaWiki API calls via an injected `httpx.Client` — `action=query&
  list=search&srsearch=<query>` to find the best-matching title, then
  `action=query&prop=extracts&explaintext&titles=<title>` to fetch a
  plain-text summary — and hands the JSON to the pure parser.

Registered on the agent via `@agent.tool` (needs `RunContext` to reach
`ctx.deps`, the injected `httpx.Client`) — not `@agent.tool_plain`.

Sync, not async: nothing else in this design needs an event loop once
streaming is deferred (see Out of scope), and `httpx.Client` avoids the
`AsyncClient` open/close-lifecycle questions that async would introduce for
no benefit right now. A sync tool function works fine under `agent.run_sync()`
today and would also work fine under `agent.run()` if `run_agent_streaming`
is added later — this isn't a dead end.

Error handling: no results found, or a MediaWiki HTTP error, raises
`pydantic_ai.ModelRetry(...)` so Claude can retry with a rephrased query.
Not every failure should be a `ModelRetry` forever — this is bounded by
pydantic_ai's normal per-tool retry budget, no custom retry logic needed.

## `app/prompts.py`

`SYSTEM_PROMPT: str` — a constant guiding the model to use
`search_wikipedia` effectively (when to search, how to handle no-results,
how to ground the answer in retrieved content). Pure data, no logic. Content
is a prompt-engineering concern for a separate pass, not this design doc.

## `app/agent.py`

```python
def build_agent(model: Model | KnownModelName | None = None) -> Agent:
    if model is None:
        settings = Settings()
        model = AnthropicModel(
            settings.anthropic_model,
            provider=AnthropicProvider(api_key=settings.anthropic_api_key),
        )
    agent = Agent(
        model,
        name="wikipedia_qa_agent",
        instructions=SYSTEM_PROMPT,
        deps_type=httpx.Client,
    )

    @agent.tool
    def search_wikipedia(ctx: RunContext[httpx.Client], query: str) -> str: ...

    return agent
```

One function, not two. An earlier draft had a separate `bootstrap()`
wrapping `build_agent()` for the production-config case; collapsed into a
single function with `model: ... | None = None` because the two-function
split added a naming decision ("do I call `build_agent` or `bootstrap`?")
without meaningfully separating responsibilities — resolving config is just
what happens when the caller doesn't supply a model.

This is the loose-coupling seam: tests call `build_agent(TestModel())` or
`build_agent(FunctionModel(...))` — no `.env`, no network, no `mock.patch`.
Production code (`query_agent.py`, later the eval suite) calls
`build_agent()` with no arguments.

`app/agent.py` contains **only** this function. No `__main__`, no argparse,
no printing — see the dependency-direction note above.

## `app/runner.py`

```python
class ToolCallRecord(BaseModel):
    tool_name: str
    args: dict
    result: str


class RunTranscript(BaseModel):
    question: str
    tool_calls: list[ToolCallRecord]
    answer: str


def run_agent(agent: Agent, question: str, deps: httpx.Client) -> RunTranscript:
    result = agent.run_sync(question, deps=deps)
    return _build_transcript(question, result)


def _build_transcript(question: str, result: AgentRunResult) -> RunTranscript:
    ...  # walk result.new_messages(), pair ToolCallPart/ToolReturnPart by
    # tool_call_id, take result.output as the answer
```

This is the audit trail, and it's built by reusing data pydantic_ai already
records — not by hand-rolled interception. `result.new_messages()` returns
exactly the `ToolCallPart`/`ToolReturnPart`/`TextPart` history for this run;
walking it is the documented, idiomatic way to inspect what happened
(confirmed against the `ai:building-pydantic-ai-agents` skill's Input and
History reference). A hooks-based or deps-accumulator-based approach was
considered and rejected: hooks (`before_tool_execute`) are the framework's
answer to *live* auditing, not needed for a post-run report; a mutable
"context the tool fills out" was rejected because it couples every tool to a
logging contract and can drift from what the model actually saw (a tool that
raises before self-logging, or a `ModelRetry`'d call, would produce an
inconsistent record) — `new_messages()` is the ground truth, not a parallel
copy of it.

`run_agent` either returns a `RunTranscript` or raises. No error field, no
try/except inside it — see Out of scope. This is also this project's one
"public API": `query_agent.py` calls it now, the eval suite will call it
later, both get the identical audited behavior.

`deps: httpx.Client` lifecycle is owned by the caller (`with httpx.Client()
as client:`), not by `run_agent` or `build_agent` — a factory function
handing back an already-open network resource is a lifecycle smell, and the
right scope differs by caller (CLI: one client per single question;
eval suite, later: one client reused across an entire batch for connection
pooling).

## `app/query_agent.py`

```python
def format_transcript(transcript: RunTranscript) -> str:
    ...  # human-readable report, e.g.:
    # Question: What is the capital of France?
    #
    # Tool calls:
    #   1. search_wikipedia(query="capital of France")
    #      → "Paris is the capital and largest city of France..."
    #
    # Answer:
    # Paris is the capital of France.


def main() -> None:
    parser = argparse.ArgumentParser(...)
    parser.add_argument("question")
    args = parser.parse_args()

    try:
        agent = build_agent()
    except ValidationError:
        print(
            "Error: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        sys.exit(1)

    with httpx.Client() as client:
        transcript = run_agent(agent, args.question, deps=client)

    print(format_transcript(transcript))


if __name__ == "__main__":
    main()
```

Output is deliberately human-readable prose, not JSON — the explicit
requirement was that a person running the CLI can audit exactly what
happened without parsing structured data, to build trust that the system is
doing what it claims. `RunTranscript` (the structured object) remains
available to any other caller (tests, the future eval suite) that wants to
work with it programmatically; the CLI's text rendering is not that
interface.

Only the missing/invalid API key case gets a specific, friendly message —
that's the failure mode most likely to be a reviewer's very first
experience running this. Every other failure (Wikipedia unreachable, model
error, retries exhausted) is left to raise and print Python's normal
traceback; pydantic_ai's and pydantic-settings' own exception messages are
already clear enough that wrapping them would be solving a problem that
doesn't exist.

## Testing

Per CLAUDE.md's existing test-pyramid principle:

- **Unit tests** (low gear): the pure MediaWiki JSON-parsing functions in
  `tools.py` — no network, no framework.
- **Service-layer tests** (high gear, the bulk of coverage): `build_agent
  (FunctionModel(...))` or `build_agent(TestModel())`, combined with a fake
  `httpx.Client` (via `httpx.MockTransport`, not `mock.patch`) passed as
  `deps` to `run_agent`, asserting the resulting `RunTranscript` shape —
  tool called with expected args, answer present. No real network, no real
  Anthropic calls.
- **Real end-to-end smoke test:** deferred to the eval suite (deliverable
  #3), not built in this pass — consistent with CLAUDE.md's "reserve real
  end-to-end runs for a handful of smoke cases."

## CLAUDE.md updates required alongside implementation

- Commands section: `uv run python -m app.agent "your question"` becomes
  `uv run python -m app.query_agent "your question"`; the `--demo` line is
  removed (demo/sample-question coverage becomes part of the eval suite
  instead of a CLI flag, per explicit decision this session).
- Architecture section: list `app/config.py`, `app/runner.py`,
  `app/query_agent.py` alongside the existing `app/agent.py`,
  `app/prompts.py`, `app/tools.py`, with the one-line responsibility split
  matching this doc's file layout — including the "query_agent depends on
  agent, never the reverse" direction.
- New explicit **Auditability** requirement (this was the user's stated
  "critical" constraint and needs to be durable, not just tribal knowledge
  from this conversation): every agent run must produce an inspectable
  record of what happened — each tool call (name, arguments, result) and the
  final answer — not just the answer text. Build this from Pydantic AI's own
  message history (`result.new_messages()`, `ToolCallPart`/`ToolReturnPart`),
  not hand-rolled logging or a self-reporting context object.
