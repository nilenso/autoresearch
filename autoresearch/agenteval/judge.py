"""Judges whether an attempt followed a question's intended path.

route_quality (one of five components inside the 60% correctness score --
see ROUTE_POINTS in agenteval/score.py) used to be a crude proxy,
1 / (1 + failed-call count), with no idea what the question's own `notes`
field said the ideal path actually was. This asks an LLM instead: given the
notes (and subtasks, for compound questions) plus the attempt's actual
calls, how closely did it follow the intended route?

Deliberately not `autoresearch/proposer.py::claude_cli()` -- that shells out
to `claude -p` specifically to bill the Claude Code subscription, which is
exactly what this project has moved off of (see config.agent_path()).
This calls litellm directly instead, the same mechanism GEPA's own
reflection_lm already uses internally -- billed through OPENROUTER_API_KEY,
no subprocess, no Claude Code CLI involved.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import litellm

from .. import config
from ..questions import Question
from .contract import Record2

_VERDICTS = frozenset({"matched", "partial", "deviated"})

_PROMPT_TEMPLATE = """\
You are grading whether an AI agent solved a map-data question the way a domain expert intended.

Question asked of the agent: "{question}"

Intended approach (ground truth — the agent never saw this):
{notes}
{decomposition}
What the agent actually ran, in order:
{calls}

Judge how closely the agent's actual commands followed the intended approach above — not whether the final answer happens to be right, but whether it took a good route to get there.

Respond with strict JSON only, nothing else:
{{"adherence": <float 0.0-1.0>, "verdict": "matched"|"partial"|"deviated", "rationale": "<1-2 sentences>"}}
"""


@dataclass(frozen=True)
class RouteVerdict:
    adherence: float
    verdict: str
    rationale: str


def judge_route_quality(question: Question, record: Record2) -> RouteVerdict | None:
    """Ask the judge model; return None (never a guess) on any failure.

    This is a real extra call per attempt, so it can and will occasionally
    fail -- a silent wrong number would be worse than the caller falling
    back to score_record()'s existing call-count proxy for exactly this
    case (see agenteval/score.py::_breakdown).
    """
    prompt = _prompt(question, record)
    try:
        response = litellm.completion(
            model=config.JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=config.openrouter_agent_key(),
            timeout=config.JUDGE_TIMEOUT_S,
        )
        text = response.choices[0].message.content or ""
    except Exception:
        return None
    return _parse(text)


def _prompt(question: Question, record: Record2) -> str:
    decomposition = ""
    subtasks = question.extra.get("subtasks")
    if subtasks:
        lines = "\n".join(f"- {step}" for step in subtasks)
        decomposition = f"\nExpected decomposition:\n{lines}\n"

    call_lines = []
    for call in record.calls:
        mark = "ok" if call.get("class") is None else "BAD"
        argv = " ".join(call.get("argv") or [])
        call_lines.append(f"[{mark}] botmap {argv} -> exit {call.get('exit_code')}")
        stdout = (call.get("stdout_head") or "").strip()
        if stdout:
            call_lines.append(f"  stdout: {stdout[:400]}")
        stderr = (call.get("stderr_head") or "").strip()
        if stderr:
            call_lines.append(f"  stderr: {stderr[:400]}")
    calls_text = "\n".join(call_lines) if call_lines else "(no calls at all)"

    return _PROMPT_TEMPLATE.format(
        question=question.question,
        notes=question.notes.strip() or "(none recorded)",
        decomposition=decomposition,
        calls=calls_text,
    )


def _parse(text: str) -> RouteVerdict | None:
    """Pull the JSON object out of the response and validate its shape.

    A search rather than a strict parse of the whole string, because a
    model asked for "JSON only" occasionally wraps it in a code fence or
    a stray sentence anyway.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    adherence = data.get("adherence")
    verdict = data.get("verdict")
    rationale = data.get("rationale")
    if not isinstance(adherence, (int, float)) or isinstance(adherence, bool):
        return None
    if verdict not in _VERDICTS:
        return None
    if not isinstance(rationale, str):
        return None

    return RouteVerdict(
        adherence=max(0.0, min(1.0, float(adherence))),
        verdict=verdict,
        rationale=rationale,
    )
