"""The one production entrypoint every eval dataset runs its cases through."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext

import httpx
from pydantic_ai.models import KnownModelName, Model

from app.agent import agent
from app.bootstrap import resolve_real_model
from app.runner import RunTranscript, run_agent
from app.tools import build_wikipedia_client


@contextmanager
def production_task(
    model: Model | KnownModelName | None = None, client: httpx.Client | None = None
) -> Iterator[Callable[[str], RunTranscript]]:
    """One client, reused across every case in a run, for connection pooling —
    the CLI wants one client per question, the eval suite wants one per batch.

    `model`/`client` default to the real production ones; they're injectable so
    this entrypoint — which every eval case runs through — is testable without
    an API key. An injected client belongs to the caller, so it isn't closed here.
    """
    model = model or resolve_real_model()
    with nullcontext(client) if client is not None else build_wikipedia_client() as active:

        def answer_question(question: str) -> RunTranscript:
            return run_agent(agent, question, deps=active, model=model)

        yield answer_question
