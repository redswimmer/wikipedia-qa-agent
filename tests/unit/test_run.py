from app.runner import RunTranscript, ToolCallRecord
from evaluations.run import _format_transcript


def test_format_transcript_has_answer_header_and_no_tool_calls_header_when_no_tool_calls():
    transcript = RunTranscript(question="What is 2 + 2?", tool_calls=[], answer="4")

    rendered = _format_transcript(transcript)

    assert rendered == "Answer:\n4"
    assert "Tool Calls:" not in rendered


def test_format_transcript_includes_query_and_result_for_each_tool_call():
    transcript = RunTranscript(
        question="Who was Ada Lovelace?",
        tool_calls=[
            ToolCallRecord(
                tool_name="search_wikipedia",
                args={"query": "Ada Lovelace"},
                result="Ada Lovelace was a mathematician.",
            )
        ],
        answer="Ada Lovelace was a mathematician.",
    )

    rendered = _format_transcript(transcript)

    assert rendered.startswith("Answer:\nAda Lovelace was a mathematician.")
    assert "Tool Calls:" in rendered
    assert "search_wikipedia → 'Ada Lovelace'" in rendered
    assert "[" not in rendered  # Rich Table treats "[...]" as markup and drops it


def test_format_transcript_includes_full_untruncated_result():
    long_result = "x" * 500
    transcript = RunTranscript(
        question="q",
        tool_calls=[
            ToolCallRecord(tool_name="search_wikipedia", args={"query": "q"}, result=long_result)
        ],
        answer="a",
    )

    rendered = _format_transcript(transcript)

    assert long_result in rendered
