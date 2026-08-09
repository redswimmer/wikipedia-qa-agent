"""Shared, cross-cutting metadata for HotpotQA-sourced eval cases."""

from typing import Literal

from pydantic import BaseModel


class HotpotQAMetadata(BaseModel):
    """Cross-cutting provenance for a HotpotQA-sourced case. Purpose-specific
    grading data lives next to the evaluator that reads it, not here."""

    level: Literal["easy", "medium", "hard"]
    type: Literal["comparison", "bridge"]
    hotpotqa_id: str
