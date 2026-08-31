#!/usr/bin/env python3
"""Build Arm E failure-class subsets from the enriched baseline summary.

Arm E routes candidates to the attempts where their mechanism can plausibly act.
This script does not run agents or botmap; it only reads the existing baseline
summary and writes deterministic subset artifacts for review or later runs.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUMMARY = ROOT / "experiments" / "runs" / "agenteval-measurement-3009509" / "agenteval-summary-with-retries.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "failure-subsets.json"
DEFAULT_MARKDOWN = Path(__file__).resolve().parent / "failure-subsets.md"

TARGETS = {
    "c-truncated": {
        "priority": 1,
        "candidate": "cand/categories-truncation-hint @ 00bff1a",
        "principle": "Make completeness explicit; never silently truncate discovery output.",
        "acceptance_metric": "Target subtype decreases on matched attempts without new broad Class C or timeout regression.",
    },
    "c-wrong-column": {
        "priority": 2,
        "candidate": "cand/count-wrong-column-hint @ 7c794ff",
        "principle": "If a value exists under another field, name the field and retry command.",
        "acceptance_metric": "Target subtype reaches zero on matched attempts or converts to guided Class B used by the agent.",
    },
    "c-wrong-type": {
        "priority": 3,
        "candidate": "arm-d/wrong-type-hint-tool @ 9ba1187",
        "principle": "If the same filter works under another feature type, name the type and retry command.",
        "acceptance_metric": "Target subtype reaches zero on matched attempts, with bounded added wall-clock.",
    },
    "c-unknown": {
        "priority": 4,
        "candidate": "not yet accepted; requires probe split before paid run",
        "principle": "A zero result should carry a falsifiable explanation or safe next probe.",
        "acceptance_metric": "Do not run a product experiment until probes split vocabulary, wrong entity, unsupported field, and true zero.",
    },
    "A": {
        "priority": 5,
        "candidate": "not yet accepted; A-to-B recovery candidate needed",
        "principle": "Hard errors should become guided retry paths.",
        "acceptance_metric": "Class A falls and Class B/self-recovery rises on matched usage-error attempts.",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def failure_key(failure: dict[str, Any]) -> str:
    subtype = failure.get("subtype")
    if subtype:
        return str(subtype)
    klass = failure.get("class")
    return str(klass) if klass else "unknown"


def simplify_failure(failure: dict[str, Any]) -> dict[str, Any]:
    return {
        "class": failure.get("class"),
        "subtype": failure.get("subtype"),
        "scope": failure.get("scope"),
        "index": failure.get("index"),
        "argv": failure.get("argv", []),
        "evidence": failure.get("evidence", ""),
    }


def attempt_failure_counts(detail: dict[str, Any]) -> Counter[str]:
    return Counter(failure_key(failure) for failure in detail.get("failures", []))


def build_subsets(summary: dict[str, Any], max_attempts_per_subset: int | None) -> dict[str, Any]:
    attempts_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_target_attempts: dict[str, dict[str, Any]] = {}

    for detail in summary.get("details", []):
        counts = attempt_failure_counts(detail)
        if not counts:
            continue

        attempt = {
            "attempt": detail["attempt"],
            "question_id": detail["question_id"],
            "repeat": detail["repeat"],
            "botmap_calls": detail.get("botmap_calls", 0),
            "failure_counts": dict(sorted(counts.items())),
            "failures": [simplify_failure(failure) for failure in detail.get("failures", [])],
        }

        for key in counts:
            attempts_by_key[key].append(attempt)
            if key in {"c-truncated", "c-wrong-column", "c-wrong-type"}:
                all_target_attempts[attempt["attempt"]] = attempt

    subsets = {}
    for key, target in TARGETS.items():
        attempts = attempts_by_key.get(key, [])
        attempts = sorted(
            attempts,
            key=lambda item: (-item["failure_counts"].get(key, 0), item["question_id"], item["repeat"]),
        )
        selected = attempts if max_attempts_per_subset is None else attempts[:max_attempts_per_subset]
        subsets[key] = {
            **target,
            "baseline_attempts_with_failure": len(attempts),
            "baseline_failure_count": sum(item["failure_counts"].get(key, 0) for item in attempts),
            "selected_attempts": selected,
            "selected_question_ids": sorted({item["question_id"] for item in selected}),
        }

    combined = sorted(
        all_target_attempts.values(),
        key=lambda item: (
            -sum(item["failure_counts"].get(key, 0) for key in ("c-truncated", "c-wrong-column", "c-wrong-type")),
            item["question_id"],
            item["repeat"],
        ),
    )
    subsets["combined-accepted-patches-priority"] = {
        "priority": 0,
        "candidate": "combined tool-side hints: 00bff1a + 7c794ff + 9ba1187",
        "principle": "Validate the accepted/provisional tool-side principles together before a full-bank run.",
        "acceptance_metric": "Class C target subtypes fall together without material token/wall-clock regression.",
        "baseline_attempts_with_failure": len(combined),
        "baseline_failure_count": sum(
            sum(item["failure_counts"].get(key, 0) for key in ("c-truncated", "c-wrong-column", "c-wrong-type"))
            for item in combined
        ),
        "selected_attempts": combined,
        "selected_question_ids": sorted({item["question_id"] for item in combined}),
    }

    return {
        "source": str(DEFAULT_SUMMARY),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_records": summary.get("records"),
        "baseline_attempts_with_failures": summary.get("attempts_with_failures"),
        "baseline_class_counts": summary.get("class_counts", {}),
        "baseline_subtype_counts": summary.get("subtype_counts", {}),
        "subsets": subsets,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Arm E failure-class subsets",
        "",
        f"Source: `{payload['source']}`",
        "",
        "The subsets route each candidate only to attempts where its mechanism can plausibly affect the measured failure.",
        "",
        "| Subset | Priority | Baseline attempts | Baseline failures | Selected questions | Candidate / status |",
        "|---|---:|---:|---:|---|---|",
    ]
    for key, subset in sorted(payload["subsets"].items(), key=lambda item: item[1]["priority"]):
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{key}`",
                    str(subset["priority"]),
                    str(subset["baseline_attempts_with_failure"]),
                    str(subset["baseline_failure_count"]),
                    ", ".join(f"`{qid}`" for qid in subset["selected_question_ids"]),
                    subset["candidate"],
                ]
            )
            + " |"
        )

    lines.extend(["", "## Attempt lists", ""])
    for key, subset in sorted(payload["subsets"].items(), key=lambda item: item[1]["priority"]):
        lines.extend([f"### `{key}`", ""])
        lines.append(f"Principle: {subset['principle']}")
        lines.append("")
        for item in subset["selected_attempts"]:
            counts = ", ".join(f"{name}={count}" for name, count in item["failure_counts"].items())
            lines.append(f"- `{item['attempt']}` ({counts})")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--max-attempts-per-subset", type=int, default=None)
    args = parser.parse_args()

    summary = load_json(args.summary)
    payload = build_subsets(summary, args.max_attempts_per_subset)
    payload["source"] = str(args.summary)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.markdown, payload)
    print(f"wrote {args.output}")
    print(f"wrote {args.markdown}")


if __name__ == "__main__":
    main()
