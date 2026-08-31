#!/usr/bin/env python3
"""Run an Arm E subset against the combined tool-side hint candidate.

This script is intentionally opt-in for paid agent calls. Without
`--confirm-paid`, it prints the selected attempts and exits.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any

from autoresearch import config, runner
from autoresearch.agenteval.analyze import write_summary
from autoresearch.agenteval.enrich import enrich_run
from autoresearch.questions import Question, load

ARM_DIR = Path(__file__).resolve().parent
DEFAULT_SUBSETS = ARM_DIR / "failure-subsets.json"
DEFAULT_BOTMAP_REPO = Path("/Users/priyangapkini/workspace/ar-e/botmap")
DEFAULT_CANDIDATE_SHA = "6a3015d"
DEFAULT_SUBSET = "combined-accepted-patches-priority"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def append_progress(run_dir: Path, event: dict[str, Any]) -> None:
    with (run_dir / "progress.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def selected_attempts(subsets_path: Path, subset_name: str) -> list[dict[str, Any]]:
    subsets = read_json(subsets_path)["subsets"]
    if subset_name not in subsets:
        available = ", ".join(sorted(subsets))
        raise SystemExit(f"unknown subset {subset_name!r}; available: {available}")
    return subsets[subset_name]["selected_attempts"]


def question_map() -> dict[str, Question]:
    return {question.id: question for question in load()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subsets", type=Path, default=DEFAULT_SUBSETS)
    parser.add_argument("--subset", default=DEFAULT_SUBSET)
    parser.add_argument("--botmap-repo", type=Path, default=DEFAULT_BOTMAP_REPO)
    parser.add_argument("--candidate-sha", default=DEFAULT_CANDIDATE_SHA)
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--confirm-paid", action="store_true", help="actually run paid Claude attempts")
    args = parser.parse_args()

    attempts = selected_attempts(args.subsets, args.subset)
    questions = question_map()
    run_dir = args.run_dir or config.ROOT / "experiments" / "runs" / f"arm-e-combined-{args.subset}-{args.candidate_sha}"

    print(f"subset={args.subset}")
    print(f"attempts={len(attempts)}")
    print(f"botmap_repo={args.botmap_repo}")
    print(f"run_dir={run_dir}")
    for attempt in attempts:
        print(f"- {attempt['attempt']}")

    if not args.confirm_paid:
        print("Refusing to run paid agent calls without --confirm-paid.")
        return

    config.load_env()
    started = monotonic()
    attempts_done = 0
    completed = 0
    ok = 0
    botmap_calls = 0
    cost_usd = 0.0

    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "metadata.json", {
        "arm": "E",
        "subset": args.subset,
        "candidate_sha": args.candidate_sha,
        "botmap_repo": str(args.botmap_repo),
        "subsets_source": str(args.subsets),
        "baseline_source": "experiments/runs/agenteval-measurement-3009509/agenteval-summary-with-retries.json",
        "attempts": [attempt["attempt"] for attempt in attempts],
        "started": datetime.now(timezone.utc).isoformat(),
    })

    def summary(finished: bool = False) -> dict[str, Any]:
        return {
            "attempts_done": attempts_done,
            "total": len(attempts),
            "completed": completed,
            "ok": ok,
            "botmap_calls": botmap_calls,
            "cost_usd": cost_usd,
            "minutes": round((monotonic() - started) / 60, 1),
            "finished": datetime.now(timezone.utc).isoformat() if finished else None,
        }

    write_json(run_dir / "summary.json", summary())
    for item in attempts:
        question = questions[item["question_id"]]
        repeat = int(item["repeat"])
        print(f"[arm-e] {attempts_done + 1}/{len(attempts)} {item['attempt']}", flush=True)
        attempt = runner.ask(question, args.botmap_repo, repeat, keep_dir=run_dir / "attempts")
        attempts_done += 1
        completed += int(attempt.completed)
        ok += int(attempt.ok)
        botmap_calls += len(attempt.calls)
        cost_usd += attempt.transcript.usage.cost_usd
        append_progress(run_dir, {
            "attempt": item["attempt"],
            "completed": attempt.completed,
            "ok": attempt.ok,
            "botmap_calls": len(attempt.calls),
            "cost_usd": attempt.transcript.usage.cost_usd,
            "time": datetime.now(timezone.utc).isoformat(),
        })
        write_json(run_dir / "summary.json", summary())

    enrichment = enrich_run(run_dir, args.botmap_repo)
    write_json(run_dir / "enrichment-summary.json", enrichment)
    write_summary(run_dir)
    write_json(run_dir / "summary.json", summary(finished=True))
    print(f"[arm-e] done: {run_dir}")


if __name__ == "__main__":
    main()
