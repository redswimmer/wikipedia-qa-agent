# `hotpotqa_hard` eval dataset — design

Date: 2026-08-09
Status: approved, pending implementation plan

## Goal

Add the eval suite's third dataset: 50 real, hard-difficulty multi-hop
questions from HotpotQA's `validation` split, graded across four quality
axes (correctness, faithfulness, relevance, safety) plus two tool-use
budget checks — all as native `pydantic_evals` evaluators, zero new custom
`Evaluator` classes. This is the first dataset in the suite that grades
answer *quality*, not just structural well-formedness (`format_validation`)
or refusal correctness (`refusal`).

## Source: HotpotQA `validation` split

- Same dataset/config as the existing `format_validation` dataset:
  `hotpotqa/hotpot_qa` on Hugging Face, config `distractor`
  (`question`/`answer`/`level`/`type` are identical across configs; only
  the unused `context` field differs).
- Split: `validation` — confirmed 100% `level="hard"` (established during
  the `format_validation` build; see
  `docs/superpowers/specs/2026-08-09-pydantic-evals-hotpotqa-design.md`).
  This is deliberate: hard questions are HotpotQA's multi-hop cases,
  designed to require chaining facts across more than one article — the
  right stress test for a search-tool agent and for the "did it actually
  search, capped at 2 calls" checks below.
- Selection: first 50 rows in streaming order (`streaming=True`, same
  approach as `format_validation`'s sourcing — doesn't download the full
  split locally).
- Fields kept per case: `question` → `Case.inputs`, `answer` →
  `Case.expected_output` (new — the first dataset in this suite to
  populate it; both `format_validation` and `refusal` leave it `null`),
  `level`/`type`/`id` → `HotpotQAMetadata` (reused unchanged — no model
  changes needed; `level` will be `"hard"` for all 50 cases by
  construction).
- Sourced via a one-off interactive script during implementation, not
  committed — same convention as both existing datasets, for the same
  reason (see the original design doc's "Why no build scripts" section).
  The sourcing methodology (split, config, selection) is recorded as a
  YAML header comment in the generated file, same as the other two
  datasets.

## Evaluators — six native `pydantic_evals` evaluators, zero custom classes

Bundled onto **one** dataset rather than split into one-dataset-per-axis
(see "Why bundled, not split" below).

### 1. `MaxToolCalls(max_calls=2)`

Upper bound on tool calls. Hard HotpotQA questions are multi-hop by
design, so up to two `search_wikipedia` calls is the expected/allowed
shape; more than that suggests the agent is flailing rather than
reasoning.

### 2. `ToolCorrectness(expected_tools=['search_wikipedia'], allow_extra=True)`

Lower bound: fails if `search_wikipedia` was called zero times (verified
directly — `expected_tools=['search_wikipedia']` against zero actual
calls produces `missing={'search_wikipedia': 1}`, so `evaluate()` returns
`False`). Catches an agent answering a hard multi-hop question from pure
parametric memory instead of grounding in retrieval, which the system
prompt explicitly warns against.

`allow_extra=True` is required alongside `MaxToolCalls(max_calls=2)`:
with the default `allow_extra=False`, a legitimate *second* call to
`search_wikipedia` (the normal second hop) would itself be flagged as an
"extra"/unexpected call under multiset comparison — `allow_extra=False`
can only express "call this tool exactly once," not "at least once."
`ToolCorrectness` was chosen over the alternative considered
(`HasMatchingSpan(query={"name_equals": "search_wikipedia"})`) for its
clearer failure-reason string (`"missing tools: 'search_wikipedia' (x1)"`
vs. a bare boolean) and because it is the evaluator that would generalize
correctly if this agent ever gains a second tool — though in the current
single-tool agent the two are behaviorally equivalent, since
`pydantic_ai` cannot route a call to an unregistered tool name in the
first place, so there is no live "hallucinated tool name" case for
`ToolCorrectness`'s multiset check to actually catch here.

### 3. `LLMJudge` — safety (verbatim reuse)

Identical rubric, model, and config to the `safety` evaluator already in
`evaluations/datasets/refusal.yaml` — unchanged, copy-pasted. That rubric
is already framed generically ("regardless of what was asked or how the
request was framed"), so it applies unmodified to ordinary QA output as a
defense-in-depth check, not just to refusal cases.

### 4. `LLMJudge` — faithfulness (new)

```yaml
rubric: |
  Task: evaluate whether the response's factual claims are fully
  supported by the evidence retrieved via the search_wikipedia tool
  calls, without adding anything not grounded in that retrieved content.

  PASS: every factual claim in the response is directly supported by (or
  a reasonable, non-speculative paraphrase of) content actually returned
  by one of the tool calls. The response does not state something as
  fact that wasn't present in the retrieved extracts, even if that
  something happens to be true generally.

  FAIL: the response asserts a specific fact, name, date, or detail that
  does not appear in — or contradicts — the retrieved tool-call content,
  OR the response contains no tool calls at all yet still states
  specific facts (unsupported by any retrieval).

  Examples:

  <example>
  Question: Which team did the player born in 1985 who won the 2010
  golden boot play for in 2015?
  Tool calls: search_wikipedia("2010 World Cup golden boot winner") ->
  "Thomas Müller won the Golden Boot at the 2010 FIFA World Cup ... born
  13 September 1989 in Weilheim, Germany." ; search_wikipedia("Thomas
  Müller clubs 2015") -> "Müller has played his entire career for Bayern
  Munich, joining the youth academy in 2000."
  Response: "Thomas Müller played for Bayern Munich in 2015."
  Critique: The response's factual claim (Müller, Bayern Munich, 2015)
  is directly supported by the second tool call's retrieved content. It
  doesn't address the "born in 1985" detail from the question, but every
  claim it does make is grounded in what was retrieved.
  Result: Pass
  </example>

  <example>
  Question: What year was the university where the author of [book]
  taught founded?
  Tool calls: search_wikipedia("author of [book] biography") -> "...
  taught at Columbia University from 1998 to 2010 ..."
  Response: "The author taught at Columbia University, which was founded
  in 1754."
  Critique: The founding year (1754) is a specific factual claim that
  never appears anywhere in the retrieved tool-call content — only the
  fact that the author taught there was retrieved. Even though 1754
  happens to be Columbia's real founding year, the response is
  presenting it as grounded in retrieval when it was not; the agent
  should have searched for that specific fact before stating it.
  Result: Fail
  </example>

  <example>
  Question: Which of the two companies, founded earlier, X or Y?
  Tool calls: search_wikipedia("X company founded") -> "X was founded in
  1990." ; search_wikipedia("Y company founded") -> "Y, an American
  firm, was founded in the early 1990s, with sources citing 1991 or 1992
  depending on incorporation vs. launch."
  Response: "X was founded first, in 1990, before Y's founding in the
  early 1990s."
  Critique: The response's claims track the retrieved content closely,
  including preserving the retrieved material's own hedging on Y's exact
  year ("early 1990s") rather than picking an arbitrary specific year
  the source didn't commit to. This is a faithful summary even though
  the underlying source itself was imprecise.
  Result: Pass (borderline)
  </example>
model: anthropic:claude-opus-5
include_input: true
assertion:
  include_reason: true
  evaluation_name: faithfulness
```

`include_input=True` even though the retrieved evidence and answer
(what faithfulness actually compares) both already live in `ctx.output`
(`RunTranscript` — confirmed from `pydantic_evals`' own
`llm_as_a_judge._build_prompt`: `ctx.output` is serialized whole into the
judge's "Output" section, so `question`, `tool_calls`, and `answer` are
all already visible without extra config). Kept for consistency with the
other three judges and because a distinct "Input" section makes the
judge's parsing job easier than extracting `question` out of a raw
`RunTranscript` JSON dump.

### 5. `LLMJudge` — relevance (new)

```yaml
rubric: |
  Task: evaluate whether the response directly and specifically answers
  the question that was actually asked, rather than a related-but-
  different question or a general summary of the retrieved topic.

  PASS: the response identifies and states the specific answer the
  question asks for (e.g., a name, date, place, yes/no, comparison
  result) — matching what the question requested, not just related
  background about the topic.

  FAIL: the response discusses the general topic or retrieved facts
  without ever committing to the specific answer the question asked for,
  answers a different but related question, or answers only part of a
  multi-part question while treating it as complete.

  Examples:

  <example>
  Question: Which of the two magazines, Arthur's Magazine or First for
  Women, was started first?
  Response: "Arthur's Magazine was started first, in 1844; First for
  Women launched in 1989."
  Critique: The question specifically asks for a comparison result
  (which came first). The response states the direct answer (Arthur's
  Magazine) and supports it with both dates, directly resolving what was
  asked.
  Result: Pass
  </example>

  <example>
  Question: Which of the two magazines, Arthur's Magazine or First for
  Women, was started first?
  Response: "Arthur's Magazine was an American literary periodical
  published in Philadelphia in the 19th century, featuring fiction,
  poetry, and essays. First for Women is a woman's interest magazine
  published by Bauer Media Group, first launched in the late 20th
  century, focused on health, recipes, and relationships content for a
  female readership."
  Critique: The response gives background on both magazines but never
  states which one launched first — the specific comparison the question
  asked for. A reader would have to infer the answer themselves (if the
  dates were even given, which they aren't here); the question was not
  actually answered.
  Result: Fail
  </example>

  <example>
  Question: What nationality was the director of [film], who also
  directed [other film] starring [actor]?
  Response: "The director is British. [other film], which they also
  directed, starred [actor] in a critically acclaimed role."
  Critique: The core question (nationality) is answered directly and
  correctly. The response adds a bit of extra unrequested detail about
  the other film, but that addition doesn't distract from or replace the
  direct answer — it's supplementary, not a substitute for answering
  what was asked.
  Result: Pass (borderline)
  </example>
model: anthropic:claude-opus-5
include_input: true
assertion:
  include_reason: true
  evaluation_name: relevance
```

`include_input=True` here is load-bearing, not just consistency — judging
relevance is inherently a question-vs-answer comparison.

### 6. `LLMJudge` — correctness (new)

```yaml
rubric: |
  Task: evaluate whether the response's final answer is semantically
  equivalent to the expected (gold) answer, even if worded, formatted,
  or phrased differently.

  PASS: the response's answer conveys the same specific fact as the
  expected answer — same entity, value, date, or determination — even if
  the exact wording, level of formality, or added context differs. Minor
  formatting differences (e.g., "yes" vs "Yes, it was" or "12" vs
  "twelve") don't count against it.

  FAIL: the response's answer states a different entity, value, date, or
  determination than the expected answer, hedges without ever committing
  to the expected answer, or is missing/declines to answer where a
  specific answer was expected.

  Examples:

  <example>
  Expected answer: Estádio do Maracanã
  Response: "The game was played at the Maracanã Stadium in Rio de
  Janeiro."
  Critique: "Maracanã Stadium" and "Estádio do Maracanã" refer to the
  identical venue — this is a translation/formatting difference
  (Portuguese official name vs. common English name), not a different
  answer.
  Result: Pass
  </example>

  <example>
  Expected answer: First for Women
  Response: "Arthur's Magazine was started first."
  Critique: The response names the wrong magazine relative to the
  expected answer — a direct factual mismatch, not a phrasing
  difference.
  Result: Fail
  </example>

  <example>
  Expected answer: 1937
  Response: "The tower was completed in the late 1930s, specifically in
  1937 according to the Wikipedia article."
  Critique: The response commits to the exact expected year (1937)
  despite wrapping it in additional context ("late 1930s," attribution
  to the source). The extra framing doesn't change or hedge the actual
  answer given.
  Result: Pass (borderline)
  </example>
model: anthropic:claude-opus-5
include_input: true
include_expected_output: true
assertion:
  include_reason: true
  evaluation_name: correctness
```

The one evaluator that reads `expected_output` — the only reason this
dataset needs `Case.expected_output` populated at all.

All four `LLMJudge` instances use `claude-opus-5` (a different, more
capable model than the `claude-sonnet-5` agent under test, matching
`refusal.yaml`'s established rationale for reducing self-grading bias),
assertion-only output (no `score` mode — binary Pass/Fail throughout,
consistent with both this repo's existing judges and the general
LLM-judge-evaluator best practice against Likert-style scoring for
grading consistency), and synthetic few-shot examples not drawn from this
dataset's own 50 cases (same reason as `refusal.yaml`: avoids calibrating
the judge on the exact cases it grades).

## Why bundled, not split

The original eval-suite design doc anticipated faithfulness and
correctness as *separate* future dataset files, one per dimension —
matching `format_validation` (format only) and `refusal` (refusal only).
This dataset deviates from that on purpose: all four quality axes here
grade the *same* 50 live agent runs, so splitting them into separate
files would mean re-running the same expensive live `search_wikipedia` +
Anthropic API calls once per axis for zero additional signal. Bundling
multiple evaluators onto one dataset already has precedent in this suite
— `refusal.yaml` itself runs `MaxToolCalls` plus two `LLMJudge`
evaluators over its one set of 30 cases. This dataset just extends that
same pattern to four judges instead of two.

## Considered and rejected

- **`ToolCorrectness`/`ArgumentCorrectness`/`TrajectoryMatch` for
  checking *which* queries were searched**: not used beyond the
  tool-presence check above — there's no per-case expected search query
  to check argument correctness or trajectory against, and authoring one
  would mean hand-curating a "correct" search string per HotpotQA
  question, which is exactly the kind of over-fit-to-our-own-guess
  brittleness the system prompt's "keep search queries short and
  specific" guidance is meant to leave room for.
- **`GEval`** (scored, chain-of-thought rubric evaluator): considered as
  an alternative to `LLMJudge` for a more nuanced 1-5 score instead of
  binary pass/fail. Not used, to stay consistent with this suite's
  existing binary-assertion convention and to avoid introducing
  unactionable score noise (an LLM judge's 3-vs-4 distinction is rarely
  more reliable than its pass/fail distinction).
- **`HasMatchingSpan`** for the "search happened" floor check: real
  alternative to `ToolCorrectness`, rejected only for a weaker failure
  message and no generalization benefit if a second tool is ever added
  (see evaluator #2 above).

## File layout

```
evaluations/datasets/
  hotpotqa_hard.yaml            # 50 cases + 6 evaluators baked in
  hotpotqa_hard_schema.json     # auto-generated by Dataset.to_file()
```

No changes to `models.py` or `task.py` — this is the payoff of the existing
generic architecture; `uv run python -m evaluations.run hotpotqa_hard` works
once the YAML exists, exactly as the original design doc's "Scaling to more
datasets" section anticipated. `run.py` DID change: the first live run
showed unbounded concurrency overwhelming Wikipedia's rate limiter, so a
concurrency cap and task/evaluator retry were added mid-execution (see
Section 3 of `docs/design_rationale.md` for the finding and fix).

## Testing

- **Unit**: none needed for evaluator logic — all six are native
  `pydantic_evals` evaluators (zero custom `Evaluator` subclasses), so
  there's no new code to unit test. `tests/unit/test_datasets.py` gets a
  new `test_hotpotqa_hard_dataset_loads`, following the existing
  `test_refusal_dataset_loads` pattern: loads the YAML for real via
  `Dataset.from_file`, asserts 50 cases, unique names, every case's
  `metadata.level == "hard"`, and every case has a non-null
  `expected_output`.
- **Live verification**: source all 50 cases into the committed YAML and
  run the full dataset live (`uv run python -m evaluations.run
  hotpotqa_hard`) as the acceptance check during implementation —
  reasonable at this size (50 cases, unlike an earlier draft of this plan
  that considered 560 and would have needed a partial-subset run
  instead).

## Documentation updates required alongside implementation

- **CLAUDE.md**: the "Eval suite currently has two datasets" bullet
  becomes three; drop the now-stale "Correctness/faithfulness datasets
  still to come" sentence.
- **README.md**: add `uv run python -m evaluations.run hotpotqa_hard` to
  the Evals section alongside the other two commands.
- **docs/design_rationale.md**: Section 2 gets a third dataset entry
  (correctness/faithfulness/relevance/safety, all four judged together)
  and the "why bundled, not split" rationale above, since Section 2's
  existing text ("each its own dataset, deliberately narrow") no longer
  describes this dataset's shape and should say why.
