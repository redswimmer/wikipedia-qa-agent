"""`search_wikipedia` driven against a fake MediaWiki transport.

The retrieval integration is hand-built, so the request parameters and the
search->extract chaining are its contract: nothing else in the system notices
if a parameter is renamed or the wrong title is looked up.
"""

import httpx
import pytest
from pydantic_ai import ModelRetry

from app.tools import (
    MEDIAWIKI_API_URL,
    WIKIPEDIA_USER_AGENT,
    build_wikipedia_client,
    parse_extract,
    search_wikipedia,
)
from tests.unit.fakes import EXTRACT, TITLE, Handler, wikipedia_handler


def _client(handler: Handler, recorder: list[httpx.Request] | None = None) -> httpx.Client:
    """Built through the production factory, so these tests exercise the real
    header/timeout configuration rather than a client the test invented."""

    def recording(request: httpx.Request) -> httpx.Response:
        if recorder is not None:
            recorder.append(request)
        return handler(request)

    return build_wikipedia_client(transport=httpx.MockTransport(recording))


def _requests_for(query: str, tool_context) -> list[httpx.Request]:
    recorded: list[httpx.Request] = []
    with _client(wikipedia_handler(), recorded) as client:
        search_wikipedia(tool_context(client), query)
    return recorded


# --- the wire contract -------------------------------------------------------


def test_search_request_sends_the_documented_mediawiki_parameters(tool_context):
    search, _ = _requests_for("ada lovelace", tool_context)

    assert str(search.url).startswith(MEDIAWIKI_API_URL)
    assert dict(search.url.params) == {
        "action": "query",
        "list": "search",
        "srsearch": "ada lovelace",
        "format": "json",
    }


def test_extract_request_asks_for_the_plaintext_intro_of_the_matched_title(tool_context):
    """`explaintext` keeps HTML out of the model's context and `exintro` keeps
    the whole article from flooding it — dropping either degrades every answer."""
    _, extract = _requests_for("ada lovelace", tool_context)

    assert dict(extract.url.params) == {
        "action": "query",
        "prop": "extracts",
        "explaintext": "true",
        "exintro": "true",
        "titles": TITLE,
        "format": "json",
    }


def test_extract_is_fetched_for_the_title_search_returned_not_the_raw_query(tool_context):
    """Passing the query straight through would silently fetch the wrong article
    for every query that isn't already an exact page title."""
    _, extract = _requests_for("who wrote the first program", tool_context)

    assert extract.url.params["titles"] == TITLE


def test_requests_carry_a_policy_compliant_user_agent(tool_context):
    """Wikipedia 403s generic agents and requires contact info:
    https://meta.wikimedia.org/wiki/User-Agent_policy"""
    agents = {r.headers["User-Agent"] for r in _requests_for("ada lovelace", tool_context)}

    assert agents == {WIKIPEDIA_USER_AGENT}
    agent = agents.pop()
    assert not agent.startswith("python-httpx")
    assert "https://" in agent or "@" in agent


def test_returns_the_extract_text(tool_context):
    with _client(wikipedia_handler()) as client:
        assert search_wikipedia(tool_context(client), "ada lovelace") == EXTRACT


# --- retry / error boundaries ------------------------------------------------
# These messages are prompt engineering: they are what the model reads to decide
# what to do next, so they're asserted rather than just the exception type.


def test_no_search_results_asks_the_model_for_a_different_query(tool_context):
    with (
        _client(wikipedia_handler(no_results_for=("asdfqwer",))) as client,
        pytest.raises(ModelRetry, match="No Wikipedia article found"),
    ):
        search_wikipedia(tool_context(client), "asdfqwer")


def test_empty_extract_asks_the_model_for_a_different_query(tool_context):
    with (
        _client(wikipedia_handler(extract="")) as client,
        pytest.raises(ModelRetry, match="no text extract"),
    ):
        search_wikipedia(tool_context(client), "ada lovelace")


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transient_failures_become_a_retry_the_model_can_act_on(tool_context, status):
    with (
        _client(lambda _: httpx.Response(status, json={})) as client,
        pytest.raises(ModelRetry, match=f"Wikipedia returned {status}"),
    ):
        search_wikipedia(tool_context(client), "ada lovelace")


@pytest.mark.parametrize("status", [400, 404])
def test_permanent_failures_raise_instead_of_burning_the_retry_budget(tool_context, status):
    """The other side of the transient boundary: retrying a 404 just loops until
    the agent's retry budget is exhausted."""
    with (
        _client(lambda _: httpx.Response(status, json={})) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        search_wikipedia(tool_context(client), "ada lovelace")


# --- pure parser -------------------------------------------------------------
# Only the branch the tests above genuinely cannot reach. Every other parser
# branch is observable through search_wikipedia and is asserted there instead.


def test_parse_extract_skips_blank_extracts_and_returns_the_first_real_one():
    """MediaWiki keys `pages` by opaque page id and returns a -1 sentinel page
    with a blank extract on a miss, so the skip-blank loop is the fiddly bit."""
    response_json = {"query": {"pages": {"-1": {"extract": "  "}, "12345": {"extract": EXTRACT}}}}

    assert parse_extract(response_json) == EXTRACT
