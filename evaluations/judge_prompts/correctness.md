Note: only ExpectedOutput's `answer` field is the gold answer -- ignore its `question` and `tool_calls` fields, which are unused placeholders and carry no grading signal.

Task: evaluate whether the response's final answer is semantically equivalent to the expected (gold) answer, even if worded, formatted, or phrased differently.

This matters because HotpotQA's gold answers are often terse, specific spans -- the goal is catching genuine factual mismatches, not penalizing legitimate differences in phrasing or added context.

PASS: the response's answer conveys the same specific fact as the expected answer — same entity, value, date, or determination — even if the exact wording, level of formality, or added context differs. Minor formatting differences (e.g., "yes" vs "Yes, it was" or "12" vs "twelve") don't count against it.

FAIL: the response's answer states a different entity, value, date, or determination than the expected answer, hedges without ever committing to the expected answer, or is missing/declines to answer where a specific answer was expected.

Examples:

<examples>
<example>
Expected answer: Estádio do Maracanã
Response: "The game was played at the Maracanã Stadium in Rio de Janeiro."
Critique: "Maracanã Stadium" and "Estádio do Maracanã" refer to the identical venue — this is a translation/formatting difference (Portuguese official name vs. common English name), not a different answer.
Result: Pass
</example>

<example>
Expected answer: First for Women
Response: "Arthur's Magazine was started first."
Critique: The response names the wrong magazine relative to the expected answer — a direct factual mismatch, not a phrasing difference.
Result: Fail
</example>

<example>
Expected answer: 1937
Response: "The tower was completed in the late 1930s, specifically in 1937 according to the Wikipedia article."
Critique: The response commits to the exact expected year (1937) despite wrapping it in additional context ("late 1930s," attribution to the source). The extra framing doesn't change or hedge the actual answer given.
Result: Pass
</example>
</examples>