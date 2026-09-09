import json

from autoresearch.agenteval.contract import validate
from autoresearch.agenteval.record import build_record, parse_reasoning_trace, parse_tools_used
from autoresearch.questions import Question
from autoresearch.score import Attempt
from autoresearch.trace import Call, Transcript, Usage


def test_build_record_from_attempt_contains_verdicts_and_agent_side():
    attempt = Attempt(
        question_id="q",
        repeat=1,
        calls=[
            Call(["count"], 0, "", "Did you mean: bus_station"),
            Call(["categories", "-t", "place"], 0, "[]", ""),
        ],
        transcript=Transcript(final_answer="done", completed=True, status="ok"),
    )

    record = build_record(attempt)
    raw = {
        "schema": record.schema,
        "question_id": record.question_id,
        "repeat": record.repeat,
        "calls": list(record.calls),
        "agent_side": list(record.agent_side),
        "tools_used": record.tools_used,
        "botmap_calls": record.botmap_calls,
        "answer": record.answer,
        "attempt": None,
    }

    assert record.calls[0]["class"] == "B"
    assert record.agent_side[0]["kind"] == "ignored_hint"
    assert validate(raw) == []


def test_parse_tools_used_counts_claude_stream_events(tmp_path):
    path = tmp_path / "transcript.jsonl"
    path.write_text(
        json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "Bash"},
                {"type": "tool_use", "name": "WebSearch"},
            ]},
        }) + "\n" + json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Bash"}]},
        }) + "\n",
        encoding="utf-8",
    )

    assert parse_tools_used(path) == {"Bash": 2, "WebSearch": 1}


def test_build_record_populates_task_metadata_and_usage_from_the_question_and_attempt():
    question = Question(id="q", question="how many hospitals in Rhode Island?",
                         place="Rhode Island, US", tier=1)
    attempt = Attempt(
        question_id="q",
        repeat=1,
        calls=[],
        transcript=Transcript(
            final_answer="12", completed=True, status="ok",
            usage=Usage(input_tokens=800, output_tokens=200, cost_usd=0.12, duration_ms=4500),
        ),
    )

    record = build_record(attempt, question=question)

    assert record.question == "how many hospitals in Rhode Island?"
    assert record.place == "Rhode Island, US"
    assert record.total_tokens == 1000
    assert record.duration_ms == 4500
    assert record.cost_usd == 0.12
    # score/token_efficiency/wallclock_efficiency/route_judge are attached
    # later by the caller (see evaluator.py/baseline.py), not built here --
    # scoring this record needs the record itself as input.
    assert record.score is None
    assert record.route_judge is None


def test_build_record_without_a_question_leaves_task_metadata_blank():
    attempt = Attempt(question_id="q", repeat=1, calls=[],
                       transcript=Transcript(final_answer="x", completed=True, status="ok"))

    record = build_record(attempt)

    assert record.question == ""
    assert record.place is None


def test_parse_reasoning_trace_keeps_text_tool_use_and_tool_result_in_order(tmp_path):
    path = tmp_path / "transcript.jsonl"
    path.write_text(
        "\n".join([
            json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "I'll count hospitals first."},
                {"type": "tool_use", "name": "Bash", "input": {"command": "botmap count -t place"}},
            ]}}),
            json.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "content": "12 rows"},
            ]}}),
        ]) + "\n",
        encoding="utf-8",
    )

    trace = parse_reasoning_trace(path)

    assert trace == [
        {"type": "text", "text": "I'll count hospitals first."},
        {"type": "tool_use", "name": "Bash", "input": {"command": "botmap count -t place"}},
        {"type": "tool_result", "content": "12 rows"},
    ]


def test_parse_reasoning_trace_truncates_like_call_output_does(tmp_path):
    path = tmp_path / "transcript.jsonl"
    long_text = "x" * 3000
    path.write_text(
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": long_text},
        ]}}) + "\n",
        encoding="utf-8",
    )

    trace = parse_reasoning_trace(path, limit=2000)

    assert len(trace[0]["text"]) == 2000


def test_parse_reasoning_trace_on_a_missing_file_is_empty(tmp_path):
    assert parse_reasoning_trace(tmp_path / "does-not-exist.jsonl") == []
    assert parse_reasoning_trace(None) == []
