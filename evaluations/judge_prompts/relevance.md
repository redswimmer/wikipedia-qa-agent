Task: evaluate whether the response directly and specifically answers the question that was actually asked, rather than a related-but-different question or a general summary of the retrieved topic.

This matters because a technically accurate response that never commits to the specific thing asked is just as unhelpful as a wrong one -- the goal is catching non-answers, not just factual errors.

PASS: the response identifies and states the specific answer the question asks for (e.g., a name, date, place, yes/no, comparison result) — matching what the question requested, not just related background about the topic.

FAIL: the response discusses the general topic or retrieved facts without ever committing to the specific answer the question asked for, answers a different but related question, or answers only part of a multi-part question while treating it as complete.

Examples:

<examples>
<example>
Question: Which of the two magazines, Arthur's Magazine or First for Women, was started first?
Response: "Arthur's Magazine was started first, in 1844; First for Women launched in 1989."
Critique: The question specifically asks for a comparison result (which came first). The response states the direct answer (Arthur's Magazine) and supports it with both dates, directly resolving what was asked.
Result: Pass
</example>

<example>
Question: Which of the two magazines, Arthur's Magazine or First for Women, was started first?
Response: "Arthur's Magazine was an American literary periodical published in Philadelphia in the 19th century, featuring fiction, poetry, and essays. First for Women is a woman's interest magazine published by Bauer Media Group, first launched in the late 20th century, focused on health, recipes, and relationships content for a female readership."
Critique: The response gives background on both magazines but never states which one launched first — the specific comparison the question asked for. A reader would have to infer the answer themselves (if the dates were even given, which they aren't here); the question was not actually answered.
Result: Fail
</example>

<example>
Question: What nationality was the director of [film], who also directed [other film] starring [actor]?
Response: "The director is British. [other film], which they also directed, starred [actor] in a critically acclaimed role."
Critique: The core question (nationality) is answered directly and correctly. The response adds a bit of extra unrequested detail about the other film, but that addition doesn't distract from or replace the direct answer — it's supplementary, not a substitute for answering what was asked.
Result: Pass
</example>
</examples>