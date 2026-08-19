"""The eval runner's report formatting and its dataset-name error path.

`_format_transcript` is pure (RunTranscript in, str out) and its output is only
ever seen through Rich, so the Rich round-trip is asserted rather than the
escaping mechanism — the bug this guards was invisible at the string level.
"""

import io

import pytest
from rich.console import Console
from rich.table import Table

from app.runner import RunTranscript, ToolCallRecord
from evaluations.run import _format_transcript
from evaluations.run import main as run_main


def _render(value: str) -> str:
    """Exactly how report.print() puts a formatted transcript on screen."""
    table = Table()
    table.add_column("Output")
    table.add_row(value)
    buffer = io.StringIO()
    Console(file=buffer, width=200).print(table)
    return buffer.getvalue()


def _transcript(tool_calls: list[ToolCallRecord] | None = None, answer: str = "a") -> RunTranscript:
    return RunTranscript(question="q", tool_calls=tool_calls or [], answer=answer)


def test_answer_only_transcript_has_no_tool_calls_section():
    rendered = _format_transcript(_transcript(answer="4"))

    assert rendered.startswith("Answer:")
    assert "4" in rendered
    assert "Tool Calls:" not in rendered


def test_tool_calls_are_reported_with_their_query_and_full_result():
    long_result = "Ada Lovelace was a mathematician. " + "x" * 500
    transcript = _transcript(
        tool_calls=[
            ToolCallRecord(
                tool_name="search_wikipedia", args={"query": "Ada Lovelace"}, result=long_result
            )
        ]
    )

    rendered = _format_transcript(transcript)

    assert "Tool Calls:" in rendered
    assert "search_wikipedia → 'Ada Lovelace'" in rendered
    assert long_result in rendered


@pytest.mark.parametrize(
    "result",
    [
        "[retry] No Wikipedia article found for query: 'zzz'.",
        "Ada Lovelace [1] worked on the [Analytical Engine].",
    ],
)
def test_bracketed_text_survives_rich_rendering(result):
    """Rich parses "[...]" as a style tag and silently drops what it doesn't
    recognise. That ate every "[retry]" marker app/runner.py writes out of the
    committed results files — the only live evidence a reviewer ever sees."""
    rendered = _render(
        _format_transcript(
            _transcript(
                tool_calls=[
                    ToolCallRecord(
                        tool_name="search_wikipedia", args={"query": "zzz"}, result=result
                    )
                ]
            )
        )
    )

    assert result in rendered


def test_unknown_dataset_name_exits_with_the_available_names(capsys):
    with pytest.raises(SystemExit) as exc_info:
        run_main(["no-such-dataset"])

    assert exc_info.value.code == 1
    stderr = capsys.readouterr().err
    assert "no-such-dataset" in stderr
    assert "refusal" in stderr and "answer_quality" in stderr
