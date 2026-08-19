# Prompts and judge rubrics

Every prompt in this system, indexed on one page: the agent's system
prompt, and every LLM-as-judge rubric used by the eval suite.

Each judge rubric lives in its own file under [`rubrics/`](rubrics/), and
those files **are** the prompts — [`judges.py`](judges.py) reads each one
verbatim at load time and hands it straight to the judge, so what you read
below is byte-for-byte what the judge is sent. (That's also why the files
carry no headings, fences, or frontmatter of their own. GitHub's rendered
view swallows the `<example>` tags; use the raw view to see the exact
text.) The agent's own system prompt is the one exception — it lives in
[`app/prompts.py`](../app/prompts.py).

Shared judging design, applied to every rubric:

- **Binary Pass/Fail, never a 1-5 scale** — scale scores look precise but
  aren't reproducible; annotators (and judges) rarely agree on the line
  between a 3 and a 4.
- **Few-shot examples with worked critiques** — each rubric ships labeled
  Pass/Fail examples explaining *why*, distinct from the actual eval cases
  so the judge isn't calibrated on the questions it grades.
- **A stronger, separate judge model** — judging is done by Claude Opus
  (`anthropic:claude-opus-5`) while the agent under test runs Claude
  Sonnet, to reduce self-grading bias. Judges see the case input
  (`include_input`) and must report their reasoning alongside the verdict
  (`include_reason`), so grading decisions are auditable.

## Agent system prompt

[`app/prompts.py`](../app/prompts.py) — steers the agent itself: decide
answerability first, always search before answering, ground the answer in
what was retrieved.

## Judge rubrics — `refusal` dataset

| Rubric | Question it answers |
| --- | --- |
| [`refusal_quality.md`](rubrics/refusal_quality.md) | Was the refusal itself clear, specific, and appropriately delivered — not just present? |
| [`safety.md`](rubrics/safety.md) | Did the response avoid providing or facilitating anything unsafe? |

## Judge rubrics — `answer_quality` dataset

| Rubric | Question it answers |
| --- | --- |
| [`correctness.md`](rubrics/correctness.md) | Does the answer match the known HotpotQA gold answer, judged semantically rather than by string match? |
| [`faithfulness.md`](rubrics/faithfulness.md) | Is every factual claim grounded in what `search_wikipedia` actually retrieved, rather than fabricated or drawn from parametric memory? |
| [`relevance.md`](rubrics/relevance.md) | Does the answer address the specific question asked? |
| [`safety.md`](rubrics/safety.md) | The same file the `refusal` dataset uses — one shared rubric, not a copy. An unsafe response is a failure whether the agent answered or declined. |
