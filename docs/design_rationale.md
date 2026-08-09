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

One gap the `refusal` eval exposed and Section 4 closed: the prompt told
the model *when* to search, but gave no guidance for recognizing input that
isn't a coherent, answerable question in the first place. The fix was
written as a general reasoning step ("decide whether this is genuinely a
real question before searching"), not a rule naming the specific failure
category the eval happened to catch — a prompt tuned to name our own test
categories would overfit to this eval rather than generalize to real,
unseen input shaped differently.

A second gap, found through manual live testing rather than an eval (see
Section 4's second iteration): "always use `search_wikipedia`... rather
than relying on your own knowledge alone" reads as unconditional, but the
model still skipped the tool on trivia it was confident about (e.g. "What
is the capital of France?"). The instruction's own framing — "decide
whether the request is *genuinely* a factual... question" — left room for
the model to read confidence as evidence a question didn't really need
looking up, and the closing guideline ("answer... as if you already knew
the information") reinforced that reading. Fixed by naming the loophole
directly: search even when confident, because confidence isn't a reason to
skip it.

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

**Format validation**: 100% pass across both live runs (before and after
the prompt change in Section 4), confirming the basic pipeline works
end-to-end and that the change didn't regress ordinary Q&A behavior.

**Refusal** (30 cases), first run: 97.5% average, with two findings — a
weak spot in one specific category (detailed in Section 4, since it's now
fixed and the "before/after" is more informative there than a static
snapshot), and a case where the judge itself declined to grade a response
because its own safety filtering triggered on the sensitive request text
embedded in the grading prompt. The system's own refusal behavior was
unaffected by that; it's a limitation of grading the most sensitive
prompts with an LLM judge, worth knowing rather than hiding. It didn't
recur on the second run, but a single run isn't enough to call it resolved
either way — LLM judges (and, per below, the underlying API's content
filtering) aren't perfectly deterministic.

**Everything else was handled cleanly from the start** — all unanswerable
cases and most unsafe cases scored full marks, including one response that
proactively offered safe alternative framings and surfaced a crisis
hotline for a self-harm-adjacent prompt, unprompted.

## 4. Key iterations made based on eval results

One iteration so far, directly from the `refusal` eval's first run:

**Before:** one category of refusal cases was the system's clearest
weakness — several had the agent attempt a search instead of recognizing
the input couldn't be resolved that way at all, and one exhausted its
retry budget and crashed rather than producing any answer. The system
prompt told the model *when* to search but gave no guidance for
recognizing when it shouldn't.

**Change:** added one general guideline — decide whether a request is
genuinely a real, answerable question before searching for it, and say so
plainly if it isn't, rather than searching or guessing. Deliberately
written as a general reasoning step rather than a rule naming the specific
failure category the eval caught, so it generalizes to input shaped
differently than our 30 test cases, not just those exact ones. The two
judge rubrics were also tightened — explicit pass/fail definitions plus a
few illustrative examples apiece, distinct from any of our actual 30 test
questions so the judge isn't calibrated on the same cases it grades.

**After:** re-ran both datasets. Format validation stayed 100% pass
(no regression to ordinary behavior). Every case in the previously-weak
category passed cleanly, and the run that previously crashed completed
normally — 30/30 cases finished this time, versus 29/30 before.

Still open: whether a search retry budget being exhausted should be a hard
crash at all, versus a graceful decline; and how to handle prompts
sensitive enough to trip the judge's own content filtering, if it recurs.

A second iteration, found through manual live testing while building CLI
streaming (not from a scored eval — no correctness dataset exists yet to
have caught it automatically):

**Before:** ran the unmodified `run_agent()` against three easy trivia
questions ("What is the capital of France?", "Who wrote Romeo and
Juliet?", "What year did World War II end?") and got zero tool calls on
all three — the model answered from its own knowledge despite the system
prompt's "always use `search_wikipedia`" instruction. Multi-hop
`format_validation` questions (e.g. comparing two magazines' founding
dates) reliably triggered the tool; only single-hop trivia the model was
confident about did not — consistent with the model reading "genuinely
factual" as "non-trivial enough to need lookup" rather than "any real-world
fact, always."

**Change:** added an explicit override right at the loophole — "always
call `search_wikipedia` first — even if you're confident you already know
the answer... confidence is not a reason to skip the search" — and
reworded the closing guideline from "answer... as if you already knew the
information" (which could be read as license to skip the tool) to "once
you've searched, answer directly and concisely, in your own words" (same
tone guidance, but only after the tool call, not instead of it).

**After:** re-ran the same three trivia questions through unmodified
`run_agent()` — all three now produce exactly one tool call. Full eval
suite (`format_validation`, `refusal`) not yet re-run against this change;
worth doing before trusting it broadly, since the reworded closing
guideline touches phrasing that could interact with refusal quality.

This gap only surfaced from manually trying questions outside the eval
suite's existing cases — the format_validation dataset's cases are all
multi-hop HotpotQA questions, which happened not to exercise this failure
mode, and no dataset yet targets answer correctness/tool-use-necessity
directly. Argues for the correctness dataset in Section 5 including
deliberately easy, single-hop trivia cases, not just harder multi-hop
ones.

## 5. How I'd extend this with more time

- More eval dimensions: does the answer actually match the expected one
  (correctness), is it actually grounded in what was retrieved rather than
  just plausible-sounding (faithfulness), and did the agent search with a
  query that matches the question's intent (relevancy).
- Validate the judge itself against human-labeled examples before trusting
  it further — right now its alignment with human judgment is assumed, not
  measured.
- Scale up case counts once correctness grading exists to pair with them.
- Wire eval pass-rate thresholds into CI so a regression is visible
  without someone remembering to run the suite by hand.

## 6. Approximately how long I spent

**TODO (needs your input).**
