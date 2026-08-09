"""Wikipedia retrieval: search + extract via the MediaWiki API, exposed as an agent tool."""

import httpx
from pydantic_ai import ModelRetry, RunContext

MEDIAWIKI_API_URL = "https://en.wikipedia.org/w/api.php"

# Wikipedia rejects requests with a generic/default User-Agent — see
# https://meta.wikimedia.org/wiki/User-Agent_policy. Every httpx.Client used to
# call search_wikipedia must set this header.
WIKIPEDIA_USER_AGENT = (
    "anthropic-take-home-wikipedia-agent/0.1 "
    "(https://github.com/redswimmer/anthropic-take-home-assignment; andrew@redswimmer.com)"
)


def parse_search_title(response_json: dict) -> str | None:
    """Pure: pull the best-matching page title out of a MediaWiki search response."""
    results = response_json.get("query", {}).get("search", [])
    if not results:
        return None
    return results[0].get("title")


def parse_extract(response_json: dict) -> str | None:
    """Pure: pull the plain-text extract out of a MediaWiki extracts response."""
    pages = response_json.get("query", {}).get("pages", {})
    for page in pages.values():
        extract = page.get("extract", "").strip()
        if extract:
            return extract
    return None


def _raise_for_transient_status(response: httpx.Response) -> None:
    """Convert transient HTTP failures (429/5xx) into a ModelRetry instead of
    letting them crash the run; anything else still raises normally."""
    if response.status_code == 429 or response.status_code >= 500:
        raise ModelRetry(f"Wikipedia returned {response.status_code}; try again in a moment.")
    response.raise_for_status()


def search_wikipedia(ctx: RunContext[httpx.Client], query: str) -> str:
    """Search Wikipedia and return a plain-text extract of the best-matching article."""
    client = ctx.deps

    search_response = client.get(
        MEDIAWIKI_API_URL,
        params={"action": "query", "list": "search", "srsearch": query, "format": "json"},
    )
    _raise_for_transient_status(search_response)
    title = parse_search_title(search_response.json())
    if title is None:
        raise ModelRetry(f"No Wikipedia article found for query: {query!r}. Try a different query.")

    extract_response = client.get(
        MEDIAWIKI_API_URL,
        params={
            "action": "query",
            "prop": "extracts",
            "explaintext": True,
            "exintro": True,
            "titles": title,
            "format": "json",
        },
    )
    _raise_for_transient_status(extract_response)
    extract = parse_extract(extract_response.json())
    if extract is None:
        raise ModelRetry(
            f"Found article {title!r} but it has no text extract. Try a different query."
        )

    return extract
