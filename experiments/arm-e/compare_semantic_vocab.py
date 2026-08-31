#!/usr/bin/env python3
"""Compare the semantic-vocabulary skill note against its control.

Control  = cand/categories-search @ 4a197c3 (search feature + basic note)
Treatment= cand/categories-search-semantic-skill @ f93a7d2 (adds semantic note)

Only the skill note differs, so any movement is attributable to it.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ATTEMPTS = [
    "basic-category-rollup__r1",
    "bus-stops-cambridge__r1",
    "bus-stops-with-coffee__r1",
    "bike-parking-coverage__r1",
    "asian-restaurants-rollup__r1",
]


def search_terms(attempt_dir: Path) -> list[str]:
    """Every value passed to `categories --search` in this attempt, in order."""
    path = attempt_dir / "commands.jsonl"
    if not path.exists():
        return []
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        argv = json.loads(line).get("argv", [])
        if "--search" in argv:
            terms.append(argv[argv.index("--search") + 1])
    return terms


def call_count(attempt_dir: Path) -> int:
    path = attempt_dir / "commands.jsonl"
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def agenteval_details(run_dir: Path) -> dict[str, dict]:
    """Per-attempt failure detail from the canonical agenteval summary.

    Falls back to summarizing the record-v2 files directly, which is what
    `write_summary` does anyway — useful when a run was interrupted before
    its summary was written.
    """
    path = run_dir / "agenteval-summary.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        from autoresearch.agenteval.analyze import summarize_run

        if not (run_dir / "attempts").exists():
            return {}
        data = summarize_run(run_dir)
    return {d["attempt"]: d for d in data.get("details", [])}


def failure_counts(detail: dict) -> Counter:
    """Failure subtypes for one attempt; falls back to class when untyped."""
    counts: Counter = Counter()
    for f in detail.get("failures", []):
        if f.get("scope") == "agent_side":
            counts[f"agent_side:{f.get('kind')}"] += 1
        else:
            counts[f.get("subtype") or f.get("class")] += 1
    return counts


def side(run_dir: Path, label: str) -> dict:
    details = agenteval_details(run_dir)
    out = {"label": label, "run_dir": str(run_dir), "attempts": {}}
    for attempt in ATTEMPTS:
        d = run_dir / "attempts" / attempt
        out["attempts"][attempt] = {
            "terms": search_terms(d),
            "calls": call_count(d),
            "failures": dict(failure_counts(details.get(attempt, {}))),
        }
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        out["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
    return out


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    control = side(root / "experiments/runs/arm-e-categories-search-c-truncated-4a197c3", "control 4a197c3")
    treatment = side(root / "experiments/runs/arm-e-semantic-vocab-f93a7d2", "treatment f93a7d2")

    print(f"{'attempt':<30} {'control terms':<40} {'treatment terms'}")
    for attempt in ATTEMPTS:
        c = control["attempts"][attempt]
        t = treatment["attempts"][attempt]
        print(f"{attempt:<30} {str(c['terms']):<40} {t['terms']}")

    print()
    print(f"{'attempt':<30} {'ctl calls':>9} {'trt calls':>9} {'ctl terms':>9} {'trt terms':>9}")
    for attempt in ATTEMPTS:
        c = control["attempts"][attempt]
        t = treatment["attempts"][attempt]
        print(f"{attempt:<30} {c['calls']:>9} {t['calls']:>9} {len(c['terms']):>9} {len(t['terms']):>9}")

    ctl_f, trt_f = Counter(), Counter()
    for attempt in ATTEMPTS:
        ctl_f.update(control["attempts"][attempt]["failures"])
        trt_f.update(treatment["attempts"][attempt]["failures"])
    print(f"\ncontrol failures:   {dict(ctl_f)}")
    print(f"treatment failures: {dict(trt_f)}")

    out = Path(__file__).resolve().parent / "semantic-vocab-comparison.json"
    out.write_text(json.dumps({"control": control, "treatment": treatment}, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
