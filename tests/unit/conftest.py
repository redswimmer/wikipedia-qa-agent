"""Shared fakes for the MediaWiki API.

The wire format lives in one place (`mediawiki`) so a shape change is a
one-line edit, not four near-identical handlers drifting apart.
"""

import httpx
import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

TITLE = "Ada Lovelace"
EXTRACT = "Ada Lovelace was a mathematician."


class MediaWiki:
    """Builds MediaWiki-shaped responses. `search(*titles)` with no titles is a
    no-results hit; `extract("")` is the empty-extract case Wikipedia returns
    for a page-id -1 sentinel."""

    @staticmethod
    def search(*titles: str) -> httpx.Response:
        return httpx.Response(200, json={"query": {"search": [{"title": t} for t in titles]}})

    @staticmethod
    def extract(text: str) -> httpx.Response:
        return httpx.Response(200, json={"query": {"pages": {"1": {"extract": text}}}})

    @staticmethod
    def is_search(request: httpx.Request) -> bool:
        return "list=search" in str(request.url)


@pytest.fixture
def mediawiki() -> type[MediaWiki]:
    return MediaWiki


@pytest.fixture
def wikipedia_mock_transport() -> httpx.MockTransport:
    """The happy path: any query resolves to the Ada Lovelace article."""

    def handler(request: httpx.Request) -> httpx.Response:
        if MediaWiki.is_search(request):
            # More than one hit, best match first: a fake with a single result
            # can't tell "the first result" from "any result".
            return MediaWiki.search(TITLE, "Ada (disambiguation)")
        return MediaWiki.extract(EXTRACT)

    return httpx.MockTransport(handler)


@pytest.fixture
def tool_context():
    """A minimal RunContext so `search_wikipedia` can be called directly — the
    agent loop swallows ModelRetry, so its messages aren't assertable through it."""

    def build(client: httpx.Client) -> RunContext[httpx.Client]:
        return RunContext(deps=client, model=TestModel(), usage=RunUsage())

    return build


# --- fake models -------------------------------------------------------------
# Shared so the CLI and runner tests drive the agent through identical
# behaviour instead of each redefining it.


def search_then_answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    if len(messages) == 1:
        return ModelResponse(
            parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": TITLE})]
        )
    return ModelResponse(parts=[TextPart(content=EXTRACT)])


async def search_then_answer_stream(messages: list[ModelMessage], info: AgentInfo):
    if len(messages) == 1:
        yield {0: DeltaToolCall(name="search_wikipedia", json_args=f'{{"query": "{TITLE}"}}')}
    else:
        yield EXTRACT


def streaming_model() -> FunctionModel:
    return FunctionModel(search_then_answer, stream_function=search_then_answer_stream)
