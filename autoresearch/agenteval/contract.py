"""Record-v2 contract for the shared agent evaluator.

This module owns the stable JSON shape used by all evaluator components.  The
failure class is derived from the three axes; stored records may carry a
``class`` field for auditability, but validation never trusts it over the axes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

SCHEMA = "agenteval/2"

OUTCOMES = frozenset({"ok", "empty", "error", "degenerate"})
BLAMES = frozenset({"tool", "agent", "environment"})
RECOVERIES = frozenset({"guided", "unguided", "n/a"})
CLASSES = frozenset({"A", "B", "C", "D", "E", "F"})
C_SUBTYPES = frozenset(
    {
        "c-vocabulary",
        "c-wrong-column",
        "c-wrong-type",
        "c-dropped-input",
        "c-truncated",
        "c-wrong-entity",
        "c-unknown",
    }
)


@dataclass(frozen=True)
class Probe:
    kind: str
    ran: str
    result: str
    conclusive: bool


@dataclass(frozen=True)
class CallVerdict:
    outcome: str
    blame: str
    recovery: str
    cls: str | None
    subtype: str | None
    evidence: str
    probes: tuple[Probe, ...] = ()


@dataclass(frozen=True)
class AttemptVerdict:
    """Attempt-level verdict for failures that may have no botmap call."""

    outcome: str
    blame: str
    recovery: str
    cls: str | None
    subtype: str | None
    evidence: str


@dataclass(frozen=True)
class Record2:
    schema: str
    question_id: str
    repeat: int
    calls: tuple[dict[str, Any], ...]
    agent_side: tuple[dict[str, Any], ...]
    tools_used: dict[str, int]
    botmap_calls: int
    answer: dict[str, Any]
    attempt: AttemptVerdict | None = None
    # Denormalized task description, so a record is self-describing without a
    # join against experiments/questions.yaml.
    question: str = ""
    place: str | None = None
    # The score and its two efficiency terms, computed by the outer evaluator
    # (autoresearch/score.py) and persisted here instead of discarded once
    # folded into the aggregate.
    score: float | None = None
    token_efficiency: float | None = None
    wallclock_efficiency: float | None = None
    total_tokens: int = 0
    duration_ms: int = 0
    cost_usd: float = 0.0
    # Whether the attempt produced an answer at all (Attempt.completed) --
    # not the same as scoring well. Stored explicitly because "did this pass"
    # (a report's pass-rate figure) shouldn't have to be re-derived from
    # score.value, which can be low for a completed-but-wrong attempt too.
    completed: bool = True
    # Assistant text/thinking blocks, tool_use, and tool_result events, in
    # order, extracted from the retained transcript.jsonl -- an extraction
    # gap this closes, not a new capture mechanism.
    reasoning_trace: tuple[dict[str, Any], ...] = ()
    # The LLM judge's verdict on whether the attempt followed the question's
    # intended path (adherence, verdict, rationale) -- see agenteval/judge.py.
    route_judge: dict[str, Any] | None = None


def derive_class(outcome: str, blame: str, recovery: str) -> str | None:
    """Derive the A-F class from the three axes.

    Clean calls use ``None``.  Environment and agent blame win over the outcome
    because they decide whether the tool is charged at all.
    """
    if blame == "environment":
        return "E"
    if blame == "agent":
        return "F"
    if outcome == "ok":
        return None
    if outcome == "degenerate":
        return "D"
    if outcome == "empty" and recovery == "unguided":
        return "C"
    if outcome == "error" and recovery == "guided":
        return "B"
    if outcome == "error" and recovery == "unguided":
        return "A"
    return None


def write(path: str | Path, record: Record2) -> None:
    """Write a record as stable, indented JSON."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_record_to_json(record), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load(path: str | Path) -> Record2:
    """Load a record from JSON.

    Schema problems are reported by ``validate``; this function only parses the
    file into the dataclass shape.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return _record_from_json(raw)


def validate(raw: dict[str, Any]) -> list[str]:
    """Return schema problems. Never raise for malformed record content."""
    problems: list[str] = []

    if raw.get("schema") != SCHEMA:
        problems.append(f"schema must be {SCHEMA!r}")
    _require_str(raw, "question_id", problems)
    if not isinstance(raw.get("repeat"), int):
        problems.append("repeat must be an integer")
    if not isinstance(raw.get("calls"), list):
        problems.append("calls must be a list")
    if not isinstance(raw.get("agent_side"), list):
        problems.append("agent_side must be a list")
    if not isinstance(raw.get("tools_used"), dict):
        problems.append("tools_used must be an object")
    if not isinstance(raw.get("botmap_calls"), int):
        problems.append("botmap_calls must be an integer")
    if not isinstance(raw.get("answer"), dict):
        problems.append("answer must be an object")

    for index, call in enumerate(raw.get("calls") if isinstance(raw.get("calls"), list) else []):
        if not isinstance(call, dict):
            problems.append(f"calls[{index}] must be an object")
            continue
        _validate_verdict(call, f"calls[{index}]", problems, allow_missing=False)
        if "probes" in call:
            _validate_probes(call["probes"], f"calls[{index}].probes", problems)

    if raw.get("attempt") is not None:
        if not isinstance(raw.get("attempt"), dict):
            problems.append("attempt must be an object or null")
        else:
            _validate_verdict(raw["attempt"], "attempt", problems, allow_missing=False)

    # Optional metadata: type-checked only when present, never required, so
    # records written before these fields existed keep loading and validating
    # cleanly.
    _validate_optional_str(raw, "question", problems)
    _validate_optional_str(raw, "place", problems, nullable=True)
    _validate_optional_number(raw, "score", problems, nullable=True)
    _validate_optional_number(raw, "token_efficiency", problems, nullable=True)
    _validate_optional_number(raw, "wallclock_efficiency", problems, nullable=True)
    _validate_optional_int(raw, "total_tokens", problems)
    _validate_optional_int(raw, "duration_ms", problems)
    _validate_optional_number(raw, "cost_usd", problems)
    if "reasoning_trace" in raw and not isinstance(raw.get("reasoning_trace"), list):
        problems.append("reasoning_trace must be a list")
    if "route_judge" in raw:
        route_judge = raw.get("route_judge")
        if route_judge is not None and not isinstance(route_judge, dict):
            problems.append("route_judge must be an object or null")
    if "completed" in raw and not isinstance(raw.get("completed"), bool):
        problems.append("completed must be a boolean")

    return problems


def _validate_optional_str(raw: dict[str, Any], key: str, problems: list[str], *, nullable: bool = False) -> None:
    if key not in raw:
        return
    value = raw.get(key)
    if nullable and value is None:
        return
    if not isinstance(value, str):
        problems.append(f"{key} must be a string" + (" or null" if nullable else ""))


def _validate_optional_number(raw: dict[str, Any], key: str, problems: list[str], *, nullable: bool = False) -> None:
    if key not in raw:
        return
    value = raw.get(key)
    if nullable and value is None:
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        problems.append(f"{key} must be a number" + (" or null" if nullable else ""))


def _validate_optional_int(raw: dict[str, Any], key: str, problems: list[str]) -> None:
    if key not in raw:
        return
    value = raw.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        problems.append(f"{key} must be an integer")


def _validate_verdict(raw: dict[str, Any], prefix: str, problems: list[str], *, allow_missing: bool) -> None:
    missing = [key for key in ("outcome", "blame", "recovery") if key not in raw]
    if missing and not allow_missing:
        problems.append(f"{prefix} missing verdict axes: {', '.join(missing)}")
        return
    if missing:
        return

    outcome = raw.get("outcome")
    blame = raw.get("blame")
    recovery = raw.get("recovery")
    if outcome not in OUTCOMES:
        problems.append(f"{prefix}.outcome invalid: {outcome!r}")
    if blame not in BLAMES:
        problems.append(f"{prefix}.blame invalid: {blame!r}")
    if recovery not in RECOVERIES:
        problems.append(f"{prefix}.recovery invalid: {recovery!r}")
    if outcome not in OUTCOMES or blame not in BLAMES or recovery not in RECOVERIES:
        return

    expected = derive_class(outcome, blame, recovery)
    stored = raw.get("class", raw.get("cls"))
    if stored != expected:
        problems.append(f"{prefix}.class must be {expected!r} for its axes, got {stored!r}")
    subtype = raw.get("subtype")
    if expected == "C" and subtype is not None and subtype not in C_SUBTYPES:
        problems.append(f"{prefix}.subtype invalid for class C: {subtype!r}")
    if expected != "C" and subtype is not None:
        problems.append(f"{prefix}.subtype must be null unless class is C")


def _validate_probes(raw: Any, prefix: str, problems: list[str]) -> None:
    if not isinstance(raw, list):
        problems.append(f"{prefix} must be a list")
        return
    for index, probe in enumerate(raw):
        if not isinstance(probe, dict):
            problems.append(f"{prefix}[{index}] must be an object")
            continue
        for key in ("kind", "ran", "result"):
            if not isinstance(probe.get(key), str):
                problems.append(f"{prefix}[{index}].{key} must be a string")
        if not isinstance(probe.get("conclusive"), bool):
            problems.append(f"{prefix}[{index}].conclusive must be a boolean")


def _require_str(raw: dict[str, Any], key: str, problems: list[str]) -> None:
    if not isinstance(raw.get(key), str):
        problems.append(f"{key} must be a string")


def _record_to_json(record: Record2) -> dict[str, Any]:
    raw = asdict(record)
    raw["calls"] = [_call_to_json(call) for call in record.calls]
    if record.attempt is not None:
        raw["attempt"] = _verdict_to_json(record.attempt)
    return raw


def _call_to_json(call: dict[str, Any]) -> dict[str, Any]:
    raw = dict(call)
    if "cls" in raw:
        raw["class"] = raw.pop("cls")
    if "probes" in raw:
        raw["probes"] = [_probe_to_json(probe) for probe in raw["probes"]]
    return raw


def _probe_to_json(probe: Probe | dict[str, Any]) -> dict[str, Any]:
    return asdict(probe) if isinstance(probe, Probe) else dict(probe)


def _verdict_to_json(verdict: AttemptVerdict | CallVerdict) -> dict[str, Any]:
    raw = asdict(verdict)
    raw["class"] = raw.pop("cls")
    return raw


def _record_from_json(raw: dict[str, Any]) -> Record2:
    attempt = raw.get("attempt")
    return Record2(
        schema=raw.get("schema", ""),
        question_id=raw.get("question_id", ""),
        repeat=raw.get("repeat", 0),
        calls=tuple(raw.get("calls", ())),
        agent_side=tuple(raw.get("agent_side", ())),
        tools_used=dict(raw.get("tools_used", {})),
        botmap_calls=raw.get("botmap_calls", 0),
        answer=dict(raw.get("answer", {})),
        attempt=_attempt_from_json(attempt) if isinstance(attempt, dict) else None,
        question=raw.get("question", ""),
        place=raw.get("place"),
        score=raw.get("score"),
        token_efficiency=raw.get("token_efficiency"),
        wallclock_efficiency=raw.get("wallclock_efficiency"),
        total_tokens=raw.get("total_tokens", 0),
        duration_ms=raw.get("duration_ms", 0),
        cost_usd=raw.get("cost_usd", 0.0),
        reasoning_trace=tuple(raw.get("reasoning_trace", ())),
        route_judge=raw.get("route_judge"),
        completed=raw.get("completed", True),
    )


def _attempt_from_json(raw: dict[str, Any]) -> AttemptVerdict:
    return AttemptVerdict(
        outcome=raw.get("outcome", ""),
        blame=raw.get("blame", ""),
        recovery=raw.get("recovery", ""),
        cls=raw.get("class", raw.get("cls")),
        subtype=raw.get("subtype"),
        evidence=raw.get("evidence", ""),
    )
