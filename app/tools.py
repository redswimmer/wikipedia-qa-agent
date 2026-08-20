"""Wikipedia retrieval: search + extract via the MediaWiki API, exposed as an agent tool."""

import httpx
from pydantic_ai import ModelRetry, RunContext

MEDIAWIKI_API_URL = "https://en.wikipedia.org/w/api.php"

# Wikipedia rejects requests with a generic/default User-Agent — see
# https://meta.wikimedia.org/wiki/User-Agent_policy. Every httpx.Client used to
# call search_wikipedia must set this header.
WIKIPEDIA_USER_AGENT = (
    "wikipedia-qa-agent/0.1 "
    "(https://github.com/redswimmer/wikipedia-qa-agent; andrew@redswimmer.com)"
)


def build_wikipedia_client(
    timeout: float = 30.0, transport: httpx.BaseTransport | None = None
) -> httpx.Client:
    """A correctly-configured but unopened client for calling search_wikipedia.
    Lifecycle (open/close) stays with the caller. `transport` exists so tests
    exercise this real factory against a fake transport, rather than building
    their own client and never checking what production actually configures."""
    return httpx.Client(
        headers={"User-Agent": WIKIPEDIA_USER_AGENT}, timeout=timeout, transport=transport
    )


# How many search results the tool returns extracts for. Replaying real agent
# queries against HotpotQA's gold supporting articles showed the needed article
# ranked #2-3 in 5/50 cases — returned by the search API, then discarded when
# only the top hit was kept.
TOP_N_RESULTS = 3


def parse_search_titles(response_json: dict) -> list[str]:
    """Pure: pull the top matching page titles out of a MediaWiki search response."""
    results = response_json.get("query", {}).get("search", [])
    return [title for r in results if (title := r.get("title"))]


def parse_extracts(response_json: dict) -> dict[str, str]:
    """Pure: map page title -> plain-text extract from a MediaWiki extracts
    response, skipping pages with blank extracts (e.g. the -1 miss sentinel)."""
    pages = response_json.get("query", {}).get("pages", {})
    return {
        title: extract
        for page in pages.values()
        if (title := page.get("title")) and (extract := page.get("extract", "").strip())
    }


def format_extracts(titles: list[str], extracts_by_title: dict[str, str]) -> str:
    """Pure: label each extract with its article title, in search-rank order."""
    sections = [
        f"[{rank}] {title}:\n{extracts_by_title[title]}"
        for rank, title in enumerate(titles, start=1)
        if title in extracts_by_title
    ]
    return "\n\n".join(sections)


def _raise_for_transient_status(response: httpx.Response) -> None:
    """Convert transient HTTP failures (429/5xx) into a ModelRetry instead of
    letting them crash the run; anything else still raises normally."""
    if response.status_code == 429 or response.status_code >= 500:
        raise ModelRetry(f"Wikipedia returned {response.status_code}; try again in a moment.")
    response.raise_for_status()


def search_wikipedia(ctx: RunContext[httpx.Client], query: str) -> str:
    """Search Wikipedia and return plain-text intro extracts of the top matching
    articles, each labeled with its title."""
    client = ctx.deps

    search_response = client.get(
        MEDIAWIKI_API_URL,
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": TOP_N_RESULTS,
            "format": "json",
        },
    )
    _raise_for_transient_status(search_response)
    titles = parse_search_titles(search_response.json())
    if not titles:
        raise ModelRetry(f"No Wikipedia article found for query: {query!r}. Try a different query.")

    extract_response = client.get(
        MEDIAWIKI_API_URL,
        params={
            "action": "query",
            "prop": "extracts",
            "explaintext": True,
            "exintro": True,
            "titles": "|".join(titles),
            "format": "json",
        },
    )
    _raise_for_transient_status(extract_response)
    formatted = format_extracts(titles, parse_extracts(extract_response.json()))
    if not formatted:
        raise ModelRetry(
            f"Found articles for {query!r} but none had a text extract. Try a different query."
        )

    return formatted
