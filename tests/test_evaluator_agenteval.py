from pathlib import Path

import gepa.optimize_anything as oa

from autoresearch.baseline import Reading, _summarise
from autoresearch.evaluator import Evaluator
from autoresearch.questions import Question
from autoresearch.score import Attempt
from autoresearch.trace import Call, Transcript, Usage


class FakePool:
    files = None

    def __init__(self):
        self.log = []

    def acquire(self):
        self.log.append("acquire")
        return Path("/tmp/fake-tree")

    def reset(self, tree):
        self.log.append("reset")

    def write_candidate(self, tree, lever, files):
        self.log.append(f"write:{sorted(files)}")


def transcript(answer="done", *, status="ok", tokens=1000, ms=1000):
    return Transcript(
        final_answer=answer,
        completed=status == "ok" and bool(answer),
        status=status,
        usage=Usage(input_tokens=tokens, duration_ms=ms),
    )


def attempt(calls, transcript_=None):
    return Attempt(
        question_id="q1",
        repeat=1,
        calls=calls,
        transcript=transcript_ or transcript(),
    )


def test_evaluator_scores_and_logs_record_v2_explanations(monkeypatch):
    logs = []
    monkeypatch.setattr(oa, "log", logs.append)
    monkeypatch.setattr(Evaluator, "_broken", lambda self, tree: None)
    monkeypatch.setattr(
        "autoresearch.runner.ask_repeatedly",
        lambda *args, **kwargs: [attempt([
            Call(
                ["count", "-t", "place", "--where", "categories.primary=bus_stop"],
                exit_code=0,
                stdout="",
                stderr="0 rows. Did you mean: bus_station?",
            )
        ])],
    )
    ev = Evaluator("tool", FakePool(), {"q1": Reading(tokens=1000, duration_ms=1000, correctness=1.0)})

    total, report = ev({"botmap/cli.py": "x"}, Question(id="q1", tier=1, question="how many?"))

    assert total > 0
    assert "agenteval" in report["Score"]
    assert report["ClassifiedFailures"] == 1
    assert any("CLASS B" in line for line in logs)
    assert any('Question: "how many?"' in line for line in logs)


def test_evaluator_excludes_attempt_level_quota_instead_of_scoring_candidate(monkeypatch):
    logs = []
    monkeypatch.setattr(oa, "log", logs.append)
    monkeypatch.setattr(Evaluator, "_broken", lambda self, tree: None)
    starved = attempt([], transcript("You've hit your session limit", status="error"))
    monkeypatch.setattr("autoresearch.runner.ask_repeatedly", lambda *args, **kwargs: [starved])
    ev = Evaluator("tool", FakePool(), {})

    total, report = ev({"botmap/cli.py": "x"}, Question(id="q1", tier=1, question="how many?"))

    assert total == 0.0
    assert report == {"Unmeasurable": "all attempts excluded by agenteval"}
    assert any("CLASS E" in line for line in logs)


def test_evaluator_attaches_the_judge_verdict_and_logs_it_as_feedback(monkeypatch):
    logs = []
    monkeypatch.setattr(oa, "log", logs.append)
    monkeypatch.setattr(Evaluator, "_broken", lambda self, tree: None)
    monkeypatch.setattr(
        "autoresearch.runner.ask_repeatedly",
        lambda *args, **kwargs: [attempt([Call(["count", "-t", "place"], exit_code=0, stdout="12", stderr="")])],
    )
    from autoresearch.agenteval.judge import RouteVerdict

    monkeypatch.setattr(
        "autoresearch.evaluator.agenteval_judge.judge_route_quality",
        lambda question, record: RouteVerdict(adherence=0.75, verdict="partial", rationale="close but not ideal"),
    )
    ev = Evaluator("tool", FakePool(), {"q1": Reading(tokens=1000, duration_ms=1000, correctness=1.0)})

    ev({"botmap/cli.py": "x"}, Question(id="q1", tier=1, question="how many?"))

    assert any("Route adherence: partial (0.75)" in line and "close but not ideal" in line for line in logs)


def test_baseline_summary_uses_agenteval_and_drops_environment_attempts(tmp_path):
    starved = attempt([], transcript("You've hit your session limit", status="error", tokens=9999, ms=9999))
    clean = attempt([Call(["count"], exit_code=0, stdout="12", stderr="")], transcript(tokens=100, ms=200))
    question = Question(id="q1", tier=1, question="how many?")

    reading = _summarise([starved, clean], question, tmp_path)

    assert reading == Reading(tokens=100, duration_ms=200, correctness=1.0)


def test_baseline_summary_persists_the_judge_verdict_onto_the_saved_record(tmp_path, monkeypatch):
    from autoresearch.agenteval.contract import load as load_record
    from autoresearch.agenteval.judge import RouteVerdict

    monkeypatch.setattr(
        "autoresearch.baseline.judge_route_quality",
        lambda question, record: RouteVerdict(adherence=1.0, verdict="matched", rationale="textbook"),
    )
    clean = attempt([Call(["count"], exit_code=0, stdout="12", stderr="")], transcript(tokens=100, ms=200))
    question = Question(id="q1", tier=1, question="how many?")

    _summarise([clean], question, tmp_path)

    saved = load_record(tmp_path / "q1__r1" / "record-v2.json")
    assert saved.route_judge == {"adherence": 1.0, "verdict": "matched", "rationale": "textbook"}
