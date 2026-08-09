"""Shared pytest fixtures for app/ tests."""

import httpx
import pytest


def _fake_wikipedia_transport(request: httpx.Request) -> httpx.Response:
    if "list=search" in str(request.url):
        return httpx.Response(200, json={"query": {"search": [{"title": "Ada Lovelace"}]}})
    return httpx.Response(
        200, json={"query": {"pages": {"1": {"extract": "Ada Lovelace was a mathematician."}}}}
    )


@pytest.fixture
def wikipedia_mock_transport() -> httpx.MockTransport:
    """A fake MediaWiki transport: any query resolves to the Ada Lovelace article."""
    return httpx.MockTransport(_fake_wikipedia_transport)
