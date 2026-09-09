"""Build record-v2 attempts from retained runner artifacts."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Iterable

from autoresearch.questions import Question
from autoresearch.score import Attempt
from autoresearch.trace import Call, Transcript

from .agent_side import detect_ignored_hints
from .contract import Record2
from .taxonomy import classify, classify_attempt


def build_record(attempt: Attempt, *, question: Question | None = None,
                  transcript_path: Path | None = None) -> Record2:
    """Convert an existing runner attempt into the shared record-v2 shape.

    Only what's directly derivable from `attempt` (and `question`, when
    given) is populated here -- score, token/wallclock efficiency, and
    route_judge all depend on scoring this very record, so they're attached
    afterward by the caller via `dataclasses.replace`, not computed here.
    """
    calls = tuple(_call_record(call) for call in attempt.calls)
    agent_side = tuple(detect_ignored_hints(calls))
    usage = attempt.transcript.usage
    return Record2(
        schema="agenteval/2",
        question_id=attempt.question_id,
        repeat=attempt.repeat,
        calls=calls,
        agent_side=agent_side,
        tools_used=parse_tools_used(transcript_path) if transcript_path else {},
        botmap_calls=len(attempt.calls),
        answer={"text": attempt.transcript.final_answer, "verified": None},
        attempt=classify_attempt(attempt.transcript),
        question=question.question if question else "",
        place=question.place if question else None,
        total_tokens=usage.total_tokens,
        duration_ms=usage.duration_ms,
        cost_usd=usage.cost_usd,
        reasoning_trace=tuple(parse_reasoning_trace(transcript_path)) if transcript_path else (),
    )


def parse_tools_used(path: Path | None) -> dict[str, int]:
    """Count tool-use events in a Claude stream-json transcript."""
    if path is None or not path.exists():
        return {}
    counts: Counter[str] = Counter()
    for event in _events(path):
        message = event.get("message") or {}
        for part in message.get("content") or []:
            if isinstance(part, dict) and part.get("type") == "tool_use":
                name = part.get("name")
                if isinstance(name, str) and name:
                    counts[name] += 1
    return dict(counts)


def parse_reasoning_trace(path: Path | None, limit: int = 2000) -> list[dict[str, Any]]:
    """The assistant's reasoning and tool exchanges, in order.

    Walks the same events `parse_tools_used` does, but keeps the content
    instead of only counting it: text/thinking blocks, tool_use, and
    tool_result -- so a record shows not just which tools ran but what was
    said and returned around them. This data already exists in the retained
    transcript.jsonl; this is an extraction gap, not new capture.
    """
    if path is None or not path.exists():
        return []
    trace: list[dict[str, Any]] = []
    for event in _events(path):
        message = event.get("message") or {}
        for part in message.get("content") or []:
            if not isinstance(part, dict):
                continue
            kind = part.get("type")
            if kind == "text":
                trace.append({"type": "text", "text": _head(part.get("text") or "", limit)})
            elif kind == "thinking":
                trace.append({"type": "thinking", "text": _head(part.get("thinking") or "", limit)})
            elif kind == "tool_use":
                trace.append({"type": "tool_use", "name": part.get("name"), "input": part.get("input")})
            elif kind == "tool_result":
                content = part.get("content")
                text = content if isinstance(content, str) else json.dumps(content)
                trace.append({"type": "tool_result", "content": _head(text, limit)})
    return trace


def _events(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            yield event


def _call_record(call: Call) -> dict[str, Any]:
    verdict = classify(call)
    return {
        "argv": call.argv,
        "exit_code": call.exit_code,
        "stdout_head": _head(call.stdout),
        "stderr_head": _head(call.stderr),
        "duration_s": call.duration,
        "outcome": verdict.outcome,
        "blame": verdict.blame,
        "recovery": verdict.recovery,
        "class": verdict.cls,
        "subtype": verdict.subtype,
        "evidence": verdict.evidence,
        "probes": [
            {"kind": probe.kind, "ran": probe.ran, "result": probe.result, "conclusive": probe.conclusive}
            for probe in verdict.probes
        ],
    }


def _head(text: str, limit: int = 2000) -> str:
    return text[:limit]
