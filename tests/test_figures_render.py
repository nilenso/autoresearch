"""render.py's agent-trace card -- particularly the tool_use escaping bug
caught while testing this against the live prompt-arm run: a dict input
was being escape()'d once inline and again by the outer escape() call,
producing double-escaped HTML entities.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "figures"))

import render  # noqa: E402


class FakeRecord:
    def __init__(self, **kw):
        self.question_id = kw.get("question_id", "q1")
        self.question = kw.get("question", "How many hospitals?")
        self.completed = kw.get("completed", True)
        self.score = kw.get("score", 0.85)
        self.duration_ms = kw.get("duration_ms", 4200)
        self.cost_usd = kw.get("cost_usd", 0.12)
        self.calls = kw.get("calls", [])
        self.route_judge = kw.get("route_judge")
        self.reasoning_trace = kw.get("reasoning_trace", [])


def test_tool_use_input_is_escaped_exactly_once():
    record = FakeRecord(reasoning_trace=[
        {"type": "tool_use", "name": "Bash", "input": {"command": "botmap where 'Rhode Island'"}},
    ])

    html = render.attempt_trace_card(record)

    assert "&amp;#x27;" not in html  # double-escaped single quote would look like this
    assert "&amp;quot;" not in html
    assert "&quot;command&quot;" in html  # single, correct escaping of the JSON output


def test_a_completed_attempt_gets_the_pass_color():
    html = render.attempt_trace_card(FakeRecord(completed=True))
    assert render._PASS_COLOR in html
    assert "completed" in html


def test_an_incomplete_attempt_gets_the_fail_color():
    html = render.attempt_trace_card(FakeRecord(completed=False))
    assert render._FAIL_COLOR in html
    assert "did not complete" in html


def test_a_failed_call_shows_its_stderr():
    html = render.attempt_trace_card(FakeRecord(calls=[
        {"argv": ["count", "-t", "place"], "exit_code": 1, "class": "A",
         "stderr_head": "no such option: --category"},
    ]))
    assert "no such option" in html
    assert render._FAIL_COLOR in html


def test_judge_verdict_gets_its_own_colored_verdict_and_rationale():
    html = render.attempt_trace_card(FakeRecord(route_judge={
        "adherence": 0.4, "verdict": "partial", "rationale": "used the wrong flag",
    }))
    assert render._VERDICT_COLOR["partial"] in html
    assert "used the wrong flag" in html


def test_no_judge_verdict_renders_nothing_extra():
    html = render.attempt_trace_card(FakeRecord(route_judge=None))
    assert "trace-judge" not in html


def test_attempt_traces_section_reports_when_empty():
    assert "No candidate attempts kept yet" in render.attempt_traces_section([], title="candidate attempts")
