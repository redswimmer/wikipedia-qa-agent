"""Wires the system prompt and tools into a Pydantic AI Agent."""

import httpx
from pydantic_ai import Agent

from app.prompts import SYSTEM_PROMPT
from app.tools import search_wikipedia

agent: Agent[httpx.Client, str] = Agent(
    name="wikipedia_qa_agent",
    instructions=SYSTEM_PROMPT,
    deps_type=httpx.Client,
    tools=[search_wikipedia],
    # Default of 1 was too tight for a lookup tool: a single bad query (wrong
    # title match, disambiguation page) shouldn't abort the whole run before
    # the model gets a couple of chances to refine its search.
    retries=3,
)
# Emits OpenTelemetry spans for agent runs and tool calls. Harmless without
# instrumentation configured (spans go to a no-op tracer) — the eval suite
# is what actually configures logfire and reads them, via span-based
# evaluators like MaxToolCalls (see evaluations/run.py).
agent.instrument = True
