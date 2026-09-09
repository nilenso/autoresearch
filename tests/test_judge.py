"""agenteval/judge.py -- real litellm calls are never made here.

tests/conftest.py's block_real_litellm_calls fixture already refuses any
unmocked litellm.completion() call; every test below mocks it explicitly
with a controlled response instead.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from autoresearch.agenteval import judge
from autoresearch.agenteval.contract import Record2
from autoresearch.questions import Question


def _fake_response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def _record(**calls_kwargs) -> Record2:
    call = {
        "argv": ["count", "-t", "place", "--where", "categories.primary=hospital"],
        "exit_code": 0,
        "stdout_head": "12",
        "stderr_head": "",
        "class": None,
        **calls_kwargs,
    }
    return Record2(
        schema="agenteval/2",
        question_id="hospitals-rhode-island",
        repeat=1,
        calls=(call,),
        agent_side=(),
        tools_used={},
        botmap_calls=1,
        answer={"text": "12", "verified": None},
    )


QUESTION = Question(
    id="hospitals-rhode-island",
    question="How many hospitals are there in Rhode Island?",
    notes="Ideal: count -t place --in 'Rhode Island, US' --where categories.primary=hospital.",
)


def test_a_clean_strict_json_response_parses(monkeypatch):
    monkeypatch.setattr(
        judge.litellm, "completion",
        lambda **kw: _fake_response(json.dumps(
            {"adherence": 0.9, "verdict": "matched", "rationale": "used the ideal command"}
        )),
    )

    verdict = judge.judge_route_quality(QUESTION, _record())

    assert verdict.adherence == 0.9
    assert verdict.verdict == "matched"
    assert verdict.rationale == "used the ideal command"


def test_json_wrapped_in_a_code_fence_still_parses(monkeypatch):
    monkeypatch.setattr(
        judge.litellm, "completion",
        lambda **kw: _fake_response(
            "```json\n" + json.dumps({"adherence": 0.4, "verdict": "partial", "rationale": "close enough"})
            + "\n```"
        ),
    )

    verdict = judge.judge_route_quality(QUESTION, _record())

    assert verdict.adherence == 0.4
    assert verdict.verdict == "partial"


def test_adherence_is_clamped_to_0_1():
    assert judge._parse(json.dumps({"adherence": 1.7, "verdict": "matched", "rationale": "x"})).adherence == 1.0
    assert judge._parse(json.dumps({"adherence": -0.3, "verdict": "matched", "rationale": "x"})).adherence == 0.0


def test_malformed_json_returns_none(monkeypatch):
    monkeypatch.setattr(judge.litellm, "completion", lambda **kw: _fake_response("not json at all"))

    assert judge.judge_route_quality(QUESTION, _record()) is None


def test_an_invalid_verdict_value_returns_none():
    raw = json.dumps({"adherence": 0.5, "verdict": "sort-of", "rationale": "x"})
    assert judge._parse(raw) is None


def test_a_missing_field_returns_none():
    raw = json.dumps({"adherence": 0.5, "verdict": "matched"})
    assert judge._parse(raw) is None


def test_an_api_error_returns_none_not_a_raised_exception(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("upstream timed out")

    monkeypatch.setattr(judge.litellm, "completion", boom)

    assert judge.judge_route_quality(QUESTION, _record()) is None


def test_the_prompt_includes_the_question_notes_and_actual_calls():
    prompt = judge._prompt(QUESTION, _record())

    assert "How many hospitals are there in Rhode Island?" in prompt
    assert "count -t place --in 'Rhode Island, US'" in prompt
    assert "botmap count -t place --where categories.primary=hospital" in prompt


def test_the_prompt_includes_subtasks_when_present():
    compound = Question(
        id="pharmacy-near-address",
        question="What's the nearest pharmacy?",
        notes="Geocode first, then search from that point.",
        extra={"subtasks": ["addresses --street Massachusetts", "at LAT,LON --category pharmacy"]},
    )

    prompt = judge._prompt(compound, _record())

    assert "Expected decomposition" in prompt
    assert "addresses --street Massachusetts" in prompt


def test_judge_model_defaults_to_the_reflection_lm():
    from autoresearch import config

    assert config.JUDGE_MODEL == config.REFLECTION_LM
