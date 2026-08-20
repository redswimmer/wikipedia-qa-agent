"""Fakes for the MediaWiki API and the model, shared by the test modules.

Deliberately not in `conftest.py`: that file is for fixtures pytest discovers
on its own, and importing helpers out of it is a smell. The wire format and the
search/extract routing both live here, so a change to either is one edit.
"""

import json
from collections.abc import Callable

import httpx
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

TITLE = "Ada Lovelace"
RUNNER_UP = "Ada (disambiguation)"
EXTRACT = "Ada Lovelace was a mathematician."
# What the default handler yields through search_wikipedia: labeled extracts
# for both search hits (the fake serves the same text for every title).
TOOL_RESULT = f"[1] {TITLE}:\n{EXTRACT}\n\n[2] {RUNNER_UP}:\n{EXTRACT}"

Handler = Callable[[httpx.Request], httpx.Response]


class MediaWiki:
    """MediaWiki-shaped responses. `search()` with no titles is a no-results
    hit; `extract("")` is what a page-id -1 sentinel returns on a miss."""

    @staticmethod
    def search(*titles: str) -> httpx.Response:
        return httpx.Response(200, json={"query": {"search": [{"title": t} for t in titles]}})

    @staticmethod
    def extract(text: str, titles: tuple[str, ...] = (TITLE,)) -> httpx.Response:
        """Extracts for the requested titles — pages keyed by id, each carrying
        its title, matching the real batched-titles response shape."""
        pages = {str(i): {"title": t, "extract": text} for i, t in enumerate(titles, start=1)}
        return httpx.Response(200, json={"query": {"pages": pages}})

    @staticmethod
    def is_search(request: httpx.Request) -> bool:
        return "list=search" in str(request.url)

    @staticmethod
    def requested_titles(request: httpx.Request) -> tuple[str, ...]:
        return tuple(request.url.params.get("titles", "").split("|"))


def wikipedia_handler(
    *,
    titles: tuple[str, ...] = (TITLE, RUNNER_UP),
    extract: str = EXTRACT,
    no_results_for: tuple[str, ...] = (),
) -> Handler:
    """Routes a MediaWiki search/extract pair.

    Defaults to more than one hit, best match first: a fake with a single
    result can't tell "the first result" from "any result". `no_results_for`
    names the queries that come back empty, for exercising the retry path.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if not MediaWiki.is_search(request):
            return MediaWiki.extract(extract, MediaWiki.requested_titles(request))
        if request.url.params.get("srsearch", "") in no_results_for:
            return MediaWiki.search()
        return MediaWiki.search(*titles)

    return handler


def search_then_answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Searches once, then answers from the extract."""
    if len(messages) == 1:
        return ModelResponse(
            parts=[ToolCallPart(tool_name="search_wikipedia", args={"query": TITLE})]
        )
    return ModelResponse(parts=[TextPart(content=EXTRACT)])


async def search_then_answer_stream(messages: list[ModelMessage], info: AgentInfo):
    if len(messages) == 1:
        yield {0: DeltaToolCall(name="search_wikipedia", json_args=json.dumps({"query": TITLE}))}
    else:
        yield EXTRACT


def streaming_model() -> FunctionModel:
    return FunctionModel(search_then_answer, stream_function=search_then_answer_stream)
