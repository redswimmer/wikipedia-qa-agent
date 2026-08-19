"""Fixtures. The fakes themselves live in `fakes.py`."""

import httpx
import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from tests.unit.fakes import wikipedia_handler


@pytest.fixture
def wikipedia_mock_transport() -> httpx.MockTransport:
    """The happy path: any query resolves to the Ada Lovelace article."""
    return httpx.MockTransport(wikipedia_handler())


@pytest.fixture
def tool_context():
    """Builds a minimal RunContext, so `search_wikipedia` can be called directly
    and each `ModelRetry` asserted on its own rather than through a bespoke
    `FunctionModel` per case."""

    def build(client: httpx.Client) -> RunContext[httpx.Client]:
        return RunContext(deps=client, model=TestModel(), usage=RunUsage())

    return build
