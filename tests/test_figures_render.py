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


def test_accepted_proposal_shows_the_pass_color_and_both_scores():
    html = render.proposal_card({
        "iteration": 3, "component": "botmap/data/skill.md", "accepted": True,
        "score_before": 0.42, "score_after": 0.71,
        "prompt": "p", "raw_lm_output": "r", "diff": "",
    })
    assert render._PASS_COLOR in html
    assert "accepted" in html
    assert "0.420" in html and "0.710" in html


def test_rejected_proposal_shows_the_fail_color():
    html = render.proposal_card({
        "iteration": 4, "component": "cli.py", "accepted": False,
        "score_before": 0.5, "score_after": 0.4,
        "prompt": "p", "raw_lm_output": "r", "diff": "",
    })
    assert render._FAIL_COLOR in html
    assert "rejected" in html


def test_diff_lines_are_colored_by_prefix_and_escaped_exactly_once():
    diff = "\n".join([
        "--- a (parent)", "+++ b (proposed)", "@@ -1 +1 @@",
        "-old line with 'quotes'", "+new line", " unchanged",
    ])
    html = render._diff_html(diff)

    assert "diff-hdr" in html and "diff-hunk" in html
    assert '<span class="diff-del">-old line' in html
    assert '<span class="diff-add">+new line' in html
    assert "&amp;#x27;" not in html  # would indicate double-escaping


def test_an_empty_diff_says_so_rather_than_showing_nothing():
    assert "no textual change" in render._diff_html("")


def test_proposals_section_reports_when_empty():
    assert "No proposals logged yet" in render.proposals_section([])
