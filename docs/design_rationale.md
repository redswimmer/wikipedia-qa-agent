# Design rationale (deliverable #3 — living draft)

> **Status: working draft**, updated incrementally as the eval suite grows.
> Structured to match `docs/assignment_instructions.md`'s deliverable #3
> requirements, one section per required bullet. Kept concept-focused —
> what's being measured and why, and what we're learning — not
> implementation detail. For how something is built, read the code or
> `CLAUDE.md`. Sections marked **TODO** need input only the human author
> has.

## 1. Prompt engineering approach and why

The system prompt (written in an earlier session — this reflects a read of
its current structure; add first-hand rationale if you have more):

- **Search before answering, don't rely on memory** — the main defense
  against the model quietly answering from its own training data instead
  of grounding the answer in something retrieved.
- **Keep search queries short and specific**, not a restatement of the
  whole question — matches how search actually works better than a long
  paraphrase.
- **Try a different query before giving up** on a bad search.
- **Ground the answer in what was retrieved; say what's missing rather
  than guess** — the core anti-hallucination instruction.
- **Don't narrate the search process in the answer** — the audit trail is
  surfaced separately, so the answer itself stays a clean, direct response.

One gap the `refusal` eval exposed (Section 3): the prompt tells the model
*when* to search, but gives no guidance for recognizing input that isn't a
coherent question in the first place.

## 2. Eval suite design: dimensions measured, and why

Two dimensions so far, each its own dataset, deliberately narrow rather
than one combined "is this a good answer" rubric:

**Format validity** — before grading whether an answer is *good*, confirm
the system produces one at all: a real answer, a real record of what was
searched. The cheapest possible signal that the system works end-to-end.

**Refusal correctness** — the system has a genuine scope boundary: not
every question is Wikipedia's to answer. A system that always searches and
never declines will hallucinate on unsafe, gibberish, or fundamentally
unanswerable input. This measures the other half of good judgment —
knowing when *not* to search — along three checks: did it avoid searching
at all, was the refusal itself clear and appropriately delivered, and did
it avoid leaking anything unsafe while declining. Cases vary along two
axes: *why* the question shouldn't be answered (unsafe / gibberish /
unanswerable in principle) and *how* it's phrased (a direct question reads
very differently from a colloquial or implicit one) — testing whether
refusal holds up beyond the cleanest, most obvious phrasing.

A few choices worth naming: judging is done by a different, more capable
model than the one being tested, to reduce self-grading bias. Refusal
quality and safety are graded separately, so a report can distinguish
"refused, but rudely" from "refused politely, but leaked something unsafe"
— different problems needing different fixes.

## 3. Where the system succeeds and fails — what we learned from evals

**Format validation**: 100% pass on the one live run so far (easy/medium/
hard difficulty), confirming the basic pipeline works end-to-end.

**Refusal** (30 cases): 97.5% average pass rate. Three distinct findings,
none fixed yet (see Section 4):

1. **Gibberish handling is the system's clearest weakness.** 3 of 10
   gibberish-phrased cases had the agent attempt a search for a made-up
   term instead of recognizing it as nonsense and declining outright — one
   exhausted its retry budget and crashed rather than producing any
   answer. This is a genuine behavior gap, not a flaky eval: the prompt
   guides the model on when *to* search, but not on recognizing when the
   input isn't answerable in the first place.
2. **Grading refusals to the most sensitive prompts has a real ceiling.**
   For 2 of 10 unsafe-category cases, the judge itself declined to grade
   the response — its own safety filtering triggered on the sensitive
   request text embedded in the grading prompt. The system's own refusal
   behavior was unaffected; this is a limitation of using an LLM judge on
   the most sensitive content, worth knowing rather than hiding.
3. **Everything else was handled cleanly** — all unanswerable cases and
   most unsafe cases scored full marks, including one response that
   proactively offered safe alternative framings and surfaced a crisis
   hotline for a self-harm-adjacent prompt, unprompted.

## 4. Key iterations made based on eval results

**None yet, by design.** This pass's scope was building the eval suite and
letting it expose failure modes, not yet closing the loop. The findings
above are the backlog for the next iteration:

- Add explicit prompt guidance for recognizing unanswerable/gibberish
  input before attempting a search.
- Reconsider what should happen when a search retry budget is exhausted —
  a hard crash vs. a graceful decline.
- Decide how to handle prompts sensitive enough to trip the judge's own
  safety filtering — a different grading approach for that subset, or
  documenting it as an accepted limitation.

## 5. How I'd extend this with more time

- More eval dimensions: does the answer actually match the expected one
  (correctness), is it actually grounded in what was retrieved rather than
  just plausible-sounding (faithfulness), and did the agent search with a
  query that matches the question's intent (relevancy).
- Close the loop on the refusal findings above, then re-run to confirm the
  fix actually moves the numbers.
- Scale up case counts once correctness grading exists to pair with them.
- Wire eval pass-rate thresholds into CI so a regression is visible
  without someone remembering to run the suite by hand.

## 6. Approximately how long I spent

**TODO (needs your input).**
