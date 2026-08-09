# HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering

Zhilin Yang\*, Peng Qi\*, Saizheng Zhang\*, Yoshua Bengio, William W. Cohen,
Ruslan Salakhutdinov, Christopher D. Manning
(Carnegie Mellon University, Stanford University, Mila/Université de Montréal, Google AI)

arXiv:1809.09600v1 [cs.CL], 25 Sep 2018 — https://HotpotQA.github.io

> Extracted from `docs/hotpotqa_1809.09600v1.pdf` via `pdftotext -layout` for
> easier reading; not a substitute for the original PDF's figures.

## Abstract

Existing QA datasets fail to train QA systems to perform complex reasoning
and provide explanations for answers. HotpotQA is a new dataset with 113k
Wikipedia-based question-answer pairs with four key features: (1) the
questions require finding and reasoning over multiple supporting documents
to answer; (2) the questions are diverse and not constrained to any
pre-existing knowledge bases or knowledge schemas; (3) sentence-level
supporting facts required for reasoning are provided, allowing QA systems to
reason with strong supervision and explain predictions; (4) a new type of
factoid comparison question tests QA systems' ability to extract relevant
facts and perform necessary comparison.

## Figure 1 example

> **Paragraph A, Return to Olympus:** [1] Return to Olympus is the only
> album by the alternative rock band Malfunkshun. [2] It was released after
> the band had broken up and after lead singer Andrew Wood (later of Mother
> Love Bone) had died of a drug overdose in 1990. [3] Stone Gossard, of
> Pearl Jam, had compiled the songs and released the album on his label,
> Loosegroove Records.
>
> **Paragraph B, Mother Love Bone:** [4] Mother Love Bone was an American
> rock band that formed in Seattle, Washington in 1987. [5] The band was
> active from 1987 to 1990. [6] Frontman Andrew Wood's personality and
> compositions helped to catapult the group to the top of the burgeoning
> late 1980s/early 1990s Seattle music scene. [7] Wood died only days before
> the scheduled release of the band's debut album, "Apple", thus ending the
> group's hopes of success. [8] The album was finally released a few months
> later.
>
> **Q:** What was the former band of the member of Mother Love Bone who
> died just before the release of "Apple"?
> **A:** Malfunkshun
> **Supporting facts:** 1, 2, 4, 6, 7

## 1. Introduction

Prior QA datasets fall short on multi-hop reasoning:

- **Single-hop datasets** (SQuAD): most questions answerable from a single
  paragraph/sentence.
- **Multi-document but still shallow** (TriviaQA, SearchQA): IR-collected
  multi-document context, but most questions still answerable from a few
  nearby sentences in one paragraph.
- **KB-constrained multi-hop datasets** (QAngaroo, ComplexWebQuestions):
  built from existing knowledge-base schemas, so question/answer diversity
  is limited by the KB's schema and entity-relation completeness.
- **Distant supervision only**: none of the above tell the system *which*
  text the answer was derived from, hurting explainability.

HotpotQA addresses all four: crowd workers see multiple supporting Wikipedia
documents and are explicitly asked to write questions that require reasoning
across all of them, are free-form (not KB-schema-constrained), come with
sentence-level supporting facts, and include a novel **comparison question**
type (compare two entities on a shared property, e.g. "Who has played for
more NBA teams, Michael Jordan or Kobe Bryant?").

## 2. Data Collection

**Building a Wikipedia hyperlink graph.** Corpus = full English Wikipedia
dump. Hyperlinks in each article's first paragraph build a directed graph
`G` where edge `(a, b)` = a hyperlink from article `a`'s first paragraph to
article `b`.

**Generating candidate paragraph pairs (bridge-entity questions).** Example:
"When was the singer and songwriter of Radiohead born?" requires first
resolving "singer and songwriter of Radiohead" → **Thom Yorke** (the
*bridge entity*), then finding his birthday. Given edge `(a, b)`, entity `b`
is usually the bridge entity connecting `a` and `b`. Not every article `b`
yields good multi-hop questions (e.g. countries have too many incoming
links; highly technical entities like "IPv4 protocol" don't work), so bridge
entities are constrained to a manually curated set of Wikipedia pages
(Appendix A: 591 categories from WikiProject "lists of popular pages").

**Comparison questions.** Comparing two entities from the same category
(e.g. two rock bands) tends to produce interesting multi-hop questions.
42 manually curated lists of similar entities (`L`, e.g. "Highest Mountains
on Earth", from Wikipedia's "list of lists of lists") are used to sample
paragraph pairs. A yes/no subset is also collected here (e.g. "Are Iron
Maiden and AC/DC from the same country?") — designed to require reasoning
over *both* paragraphs, unlike degenerate forms like "Is Iron Maiden or
AC/DC from the UK?" which can be answered from one article alone.

**Collecting supporting facts.** Crowd workers also mark the sentences that
justify the answer, so models can be evaluated on explainability
(sentence-level supporting-fact prediction), not just answer accuracy.

**Algorithm 1 (data collection procedure), informal summary:** with
probability `r1 = 0.75`, ask a bridge-entity question about paragraphs
`(a, b)`; otherwise sample two entities from a comparison list `L` and, with
probability `r2 = 0.5`, ask a yes/no comparison question, else a span-answer
comparison question. Workers always provide supporting facts.

## 3. Processing and Benchmark Settings

112,779 valid examples collected via Amazon Mechanical Turk (ParlAI
interface).

- **train-easy** (18,089 examples): split out first — questions from
  top-contributing Turkers where an overwhelming fraction only required
  reasoning over one paragraph (i.e. accidentally single-hop).
- **train-medium** (56,814 examples): from the remaining multi-hop pool, a
  baseline QA model answered these correctly with high confidence in 3-fold
  cross-validation (60% of multi-hop examples) — "easier" multi-hop.
- **train-hard / dev / test-distractor / test-fullwiki** (15,661 / 7,405 /
  7,405 / 7,405): the harder remainder, randomly split four ways.

### Table 1 — Data split

| Name | Desc. | Usage | # Examples |
|---|---|---|---|
| train-easy | single-hop | training | 18,089 |
| train-medium | multi-hop | training | 56,814 |
| train-hard | hard multi-hop | training | 15,661 |
| dev | hard multi-hop | dev | 7,405 |
| test-distractor | hard multi-hop | test | 7,405 |
| test-fullwiki | hard multi-hop | test | 7,405 |
| **Total** | | | **112,779** |

`train-easy`, `train-medium`, `train-hard` are combined for training in the
paper's experiments. `test-distractor` and `test-fullwiki` are **different
question sets** (not the same questions under two conditions) — kept
separate so gold paragraphs used in the distractor test set can't leak into
the full-wiki test set.

**Two benchmark settings** (apply to dev/test):

- **Distractor setting:** for each question, the 2 gold (actually-supporting)
  paragraphs are shuffled together with 8 distractor paragraphs retrieved by
  bigram tf-idf using the question as the query. Tests whether a model can
  find the true supporting facts amid noise, given the right documents are
  present.
- **Full wiki setting:** the model gets the first paragraphs of *all*
  Wikipedia articles, no gold paragraphs singled out — must do its own
  retrieval across 5,000,000+ paragraphs. This is the setting that
  "truly tests performance... in the wild" and is directly analogous to a
  live-search-tool QA agent: nothing hands the model pre-selected context.

**Important caveat for eval design:** official `test-distractor` /
`test-fullwiki` answers are **not public** (held out for the leaderboard).
Only `train-*` and `dev` have publicly visible gold answers. `dev` is the
right public source for hard, multi-hop, full-wiki-style questions with a
known answer.

## 4. Dataset Analysis

### Question types (Figure 2)
Diverse — centered on entities, locations, events, dates, numbers, and
yes/no comparison questions ("Are both A and B ...?").

### Table 2 — Answer types (sampled 100 examples)

| Answer Type | % | Example(s) |
|---|---|---|
| Person | 30 | King Edward II, Rihanna |
| Group / Org | 13 | Cartoonito, Apalachee |
| Location | 10 | Fort Richardson, California |
| Date | 9 | 10th or even 13th century |
| Number | 8 | 79.92 million, 17 |
| Artwork | 8 | Die schweigsame Frau |
| Yes/No | 6 | - |
| Adjective | 4 | conservative |
| Event | 1 | Prix Benois de la Danse |
| Other proper noun | 6 | Cold War, Laban Movement Analysis |
| Common noun | 5 | comedy, both men and women |

68% of questions are about entities; most answers are short spans, not
free-form prose — relevant for grading (exact-match / F1-style scoring is
natural, similar to SQuAD).

### Table 3 — Multi-hop reasoning types (sampled 100 examples from dev/test)

| Reasoning Type | % | Description |
|---|---|---|
| **Type I** — bridge entity chain reasoning | 42 | Must identify a bridge entity to complete the 2nd-hop question. E.g. "Which team does the player named 2015 Diamond Head Classic's MVP play for?" → resolve MVP name ("Buddy Hield") → look up his team. |
| **Comparison** | 27 | Compare two entities on a shared property. E.g. "Did LostAlone and Guster have the same number of members? (yes)" |
| **Type II** — multiple-property intersection | 15 | Locate the answer entity by satisfying multiple properties simultaneously (find the set satisfying each property, intersect). E.g. "Which former member of the Pittsburgh Pirates was nicknamed 'The Cobra'?" |
| **Type III** — inferring a property through a bridge entity | 6 | The entity in question shares a property with a bridge entity (e.g. co-location) inferred through it. E.g. "What city is the Marine Air Control Group 28 located in?" (via the airfield it's based at) |
| **Other** | 2 | Requires more than two supporting facts. |

Remaining 8% (by the authors' judgement): single-hop (6%), unanswerable (2%).
A second 100-example sample from `train-medium` + `train-hard` combined gave
similar proportions: Type I 38%, Type II 29%, Comparison 20%, Other 7%, Type
III 2%, single-hop 2%, unanswerable 2%.

**Relevance for picking eval questions:** these two axes — reasoning *type*
(bridge/Type I, comparison, Type II multi-property, Type III, other) and
*difficulty split* (easy/medium/hard) — are the two natural dimensions to
stratify a hand-picked eval sample across, matching what the user wants
(vary difficulty per eval case).

## 5. Experiments (brief — not directly relevant to eval design, kept for completeness)

Baseline model: reimplementation of Clark & Gardner (2017)'s architecture
(char-RNN + word embeddings, bi-attention, self-attention, RNN decoder),
extended with a 3-way yes/no/span classifier and a supporting-fact
prediction head trained jointly (multi-task) with the QA objective.

**Metrics used (Table 4):** exact match (EM) and F1, computed three ways —
on the answer span, on the set of predicted supporting-fact sentences vs.
gold, and a **joint** metric that multiplies precision/recall of both
components before computing F1 (so a system must get both the answer *and*
its justification right to score well on joint metrics). This is a strong
model for "auditable" QA evaluation, close in spirit to grading not just an
agent's final answer but whether it actually grounded the answer in the
retrieved Wikipedia text it cited.

**Headline results:** full-wiki setting is much harder than distractor
(EM 25.2 vs. 45.5 on test) — retrieval over the open corpus is the
bottleneck, not just reading comprehension. Human performance (Table 8) is
far higher (EM 83.6 / F1 91.4) than any model setting, confirming the
dataset is genuinely hard for machines circa 2018.

## 6. Related Work (brief)

Four categories of prior QA datasets: single-document (SQuAD), multi-document
(TriviaQA, SearchQA — IR-collected but still mostly single-paragraph
answerable), KB-based multi-hop (QAngaroo, ComplexWebQuestions — schema
-limited), free-form answer generation (MS MARCO — graded with ROUGE/BLEU,
which the authors note correlates poorly with human judgment).

## 7. Conclusion

HotpotQA facilitates explainable, multi-hop QA over diverse natural language,
plus a new comparison-question type.

## Appendix A — Data Collection Details (selected)

- Wikipedia dump: October 1, 2017, processed with WikiExtractor + Stanford
  CoreNLP 3.8.0 for tokenization/sentence boundaries.
- Bridge entities constrained to 591 manually curated categories from
  WikiProject's lists of popular pages.
- Comparison-question entity lists: 42 manually curated lists (e.g.
  "Highest Mountains on Earth") from Wikipedia's "list of lists of lists".

## Appendix C — Full Wiki Setting Details (selected)

Retrieval uses an inverted-index (unigram+bigram) filtering pass down to
≤5,000 candidate paragraphs, then bigram tf-idf ranks the top 10. Table 9
shows `train-medium`'s retrieval difficulty (MAP 41.89) is comparable to
`dev`/`test` (MAP 42.79 / 45.92) under the full-wiki setting — i.e.
`train-medium` isn't meaningfully "easier" to retrieve for, only easier for
the reading-comprehension step once retrieval succeeds.

## Practical takeaways for this project's eval suite

1. **Source split to sample from:** `dev` (publicly available answers, hard
   multi-hop, matches the full-wiki/live-search framing our agent uses — no
   gold paragraphs handed to the model). Do not use `test-distractor` /
   `test-fullwiki` — their gold answers aren't public.
2. **Stratify hand-picked cases along two axes:** reasoning type (bridge/
   Type I, comparison, Type II, Type III) and, if sourcing from multiple
   splits for a difficulty gradient, `train-easy` (single-hop, easiest) →
   `train-medium` (multi-hop, model-solvable) → `dev` (hard multi-hop).
3. **Answers are short spans/entities or yes/no**, not free-form prose —
   this shapes what an evaluator function should check (contains the
   correct entity/fact) rather than semantic-similarity-of-a-paragraph.
4. **Supporting facts are available per-question** — useful as optional
   metadata for a future evaluator that checks whether the agent's
   `search_wikipedia` calls actually touched the right source articles, not
   just whether the final answer string matches.
