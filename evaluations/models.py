"""Typed metadata for eval cases, grouped by dataset provenance."""

from typing import Literal

from pydantic import BaseModel


class HotpotQAMetadata(BaseModel):
    """Cross-cutting provenance for a HotpotQA-sourced case. Purpose-specific
    grading data lives next to the evaluator that reads it, not here."""

    level: Literal["easy", "medium", "hard"]
    type: Literal["comparison", "bridge"]
    hotpotqa_id: str


class RefusalMetadata(BaseModel):
    """Provenance for a hand-authored refusal-eval case: why it should be
    refused, and how the request is phrased."""

    category: Literal["unsafe", "gibberish", "unanswerable"]
    phrasing: Literal["imperative", "colloquial", "implicit", "question"]
