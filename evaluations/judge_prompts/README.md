# Judge prompts

One file per LLM-as-judge rubric. Each file's **entire content is the
prompt string** the judge receives — [`../judges.py`](../judges.py) reads
it verbatim at load time and hands it straight to the judge. That's why
these files carry no headings, fences, or frontmatter of their own:
anything added here is added to the prompt. (This README is the one
exception — it's never loaded, since `judges.py` names the prompt files it
wants explicitly.)

**Read them in GitHub's raw view.** The rendered view swallows the
`<example>` tags the few-shot blocks are built from. That's cosmetic, not
a bug to fix: escaping or fencing them would change the prompt text.

| Prompt | Question it answers | Used by |
| --- | --- | --- |
| [`refusal_quality.md`](refusal_quality.md) | Was the refusal itself clear, specific, and appropriately delivered — not just present? | `refusal` |
| [`correctness.md`](correctness.md) | Does the answer match the known HotpotQA gold answer, judged semantically rather than by string match? | `answer_quality` |
| [`faithfulness.md`](faithfulness.md) | Is every factual claim grounded in what `search_wikipedia` actually retrieved, rather than fabricated or drawn from parametric memory? | `answer_quality` |
| [`relevance.md`](relevance.md) | Does the answer address the specific question asked? | `answer_quality` |
| [`safety.md`](safety.md) | Did the response avoid providing or facilitating anything unsafe? | both — one shared file, not a copy: an unsafe response is a failure whether the agent answered or declined |

Design shared by every rubric above: binary Pass/Fail rather than a 1–5
scale (scale scores look precise but aren't reproducible); few-shot
examples with worked critiques, drawn from outside the eval cases so the
judge isn't calibrated on the questions it grades; and a stronger,
separate judge model (Claude Opus) than the agent under test (Claude
Sonnet), to reduce self-grading bias. Judges see the case input
(`include_input`) and must report their reasoning with the verdict
(`include_reason`), so grading decisions are auditable.

The agent's own system prompt — the other prompt in this system — lives in
[`app/prompts.py`](../../app/prompts.py).
