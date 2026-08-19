Task: evaluate whether the response's factual claims are fully supported by the evidence retrieved via the search_wikipedia tool calls, without adding anything not grounded in that retrieved content.

This matters because a model can produce fluent, plausible-sounding claims that were never actually retrieved -- the goal is catching hallucination, not just an unclear or poorly-written answer.

PASS: every factual claim in the response is directly supported by (or a reasonable, non-speculative paraphrase of) content actually returned by one of the tool calls. The response does not state something as fact that wasn't present in the retrieved extracts, even if that something happens to be true generally.

FAIL: the response asserts a specific fact, name, date, or detail that does not appear in — or contradicts — the retrieved tool-call content, OR the response contains no tool calls at all yet still states specific facts (unsupported by any retrieval).

Examples:

<examples>
<example>
Question: Which team did the player born in 1985 who won the 2010 golden boot play for in 2015?
Tool calls: search_wikipedia("2010 World Cup golden boot winner") -> "Thomas Müller won the Golden Boot at the 2010 FIFA World Cup ... born 13 September 1989 in Weilheim, Germany." ; search_wikipedia("Thomas Müller clubs 2015") -> "Müller has played his entire career for Bayern Munich, joining the youth academy in 2000."
Response: "Thomas Müller played for Bayern Munich in 2015."
Critique: The response's factual claim (Müller, Bayern Munich, 2015) is directly supported by the second tool call's retrieved content. It doesn't address the "born in 1985" detail from the question, but every claim it does make is grounded in what was retrieved.
Result: Pass
</example>

<example>
Question: What year was the university where the author of [book] taught founded?
Tool calls: search_wikipedia("author of [book] biography") -> "... taught at Columbia University from 1998 to 2010 ..."
Response: "The author taught at Columbia University, which was founded in 1754."
Critique: The founding year (1754) is a specific factual claim that never appears anywhere in the retrieved tool-call content — only the fact that the author taught there was retrieved. Even though 1754 happens to be Columbia's real founding year, the response is presenting it as grounded in retrieval when it was not; the agent should have searched for that specific fact before stating it.
Result: Fail
</example>

<example>
Question: Which of the two companies, founded earlier, X or Y?
Tool calls: search_wikipedia("X company founded") -> "X was founded in 1990." ; search_wikipedia("Y company founded") -> "Y, an American firm, was founded in the early 1990s, with sources citing 1991 or 1992 depending on incorporation vs. launch."
Response: "X was founded first, in 1990, before Y's founding in the early 1990s."
Critique: The response's claims track the retrieved content closely, including preserving the retrieved material's own hedging on Y's exact year ("early 1990s") rather than picking an arbitrary specific year the source didn't commit to. This is a faithful summary even though the underlying source itself was imprecise.
Result: Pass
</example>
</examples>