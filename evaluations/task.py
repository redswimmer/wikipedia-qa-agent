"""The one production entrypoint every eval dataset runs its cases through."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.agent import agent, resolve_real_model
from app.runner import RunTranscript, run_agent
from app.tools import build_wikipedia_client


@contextmanager
def production_task() -> Iterator[Callable[[str], RunTranscript]]:
    """One client, reused across every case in a run, for connection pooling —
    the CLI wants one client per question, the eval suite wants one per batch."""
    model = resolve_real_model()
    with build_wikipedia_client() as client:

        def answer_question(question: str) -> RunTranscript:
            return run_agent(agent, question, deps=client, model=model)

        yield answer_question
