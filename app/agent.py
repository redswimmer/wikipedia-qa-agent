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
)
