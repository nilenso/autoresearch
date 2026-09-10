"""tools/figures/extract.py's new, current-run extraction functions.

tools/ isn't part of the autoresearch package, so it's imported the same way
tools/figures/build_figures.py itself does: a sys.path insert, not a normal
package import.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "figures"))

import extract  # noqa: E402


def _write_record(path: Path, *, completed: bool, duration_ms: int, cost_usd: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "agenteval/2",
        "question_id": path.parent.name.split("__r")[0],
        "repeat": 1,
        "calls": [],
        "agent_side": [],
        "tools_used": {},
        "botmap_calls": 0,
        "answer": {"text": "x", "verified": None},
        "completed": completed,
        "duration_ms": duration_ms,
        "cost_usd": cost_usd,
    }))


def test_pass_rate_and_duration_over_a_set_of_kept_attempts(tmp_path):
    _write_record(tmp_path / "q1__r1" / "record-v2.json", completed=True, duration_ms=1000, cost_usd=0.1)
    _write_record(tmp_path / "q1__r2" / "record-v2.json", completed=True, duration_ms=3000, cost_usd=0.2)
    _write_record(tmp_path / "q2__r1" / "record-v2.json", completed=False, duration_ms=2000, cost_usd=0.15)

    result = extract.pass_rate_and_duration(tmp_path)

    assert result["attempts"] == 3
    assert result["passed"] == 2
    assert result["pass_rate"] == 2 / 3
    assert result["mean_duration_s"] == 2.0


def test_pass_rate_and_duration_is_none_for_an_empty_or_missing_directory(tmp_path):
    assert extract.pass_rate_and_duration(tmp_path / "does-not-exist") is None
    empty = tmp_path / "empty"
    empty.mkdir()
    assert extract.pass_rate_and_duration(empty) is None


def test_a_corrupt_mid_write_record_is_skipped_not_fatal(tmp_path):
    _write_record(tmp_path / "q1__r1" / "record-v2.json", completed=True, duration_ms=1000, cost_usd=0.1)
    corrupt = tmp_path / "q2__r1" / "record-v2.json"
    corrupt.parent.mkdir(parents=True)
    corrupt.write_text('{"schema": "agenteval/2", "question_id": "q2"')  # truncated mid-write

    result = extract.pass_rate_and_duration(tmp_path)

    assert result["attempts"] == 1


def test_cost_rollup_sums_every_readable_record(tmp_path):
    _write_record(tmp_path / "q1__r1" / "record-v2.json", completed=True, duration_ms=1000, cost_usd=0.10)
    _write_record(tmp_path / "q1__r2" / "record-v2.json", completed=True, duration_ms=1000, cost_usd=0.25)

    assert extract.cost_rollup(tmp_path) == 0.35


def test_cost_rollup_is_zero_for_a_missing_directory(tmp_path):
    assert extract.cost_rollup(tmp_path / "nope") == 0.0


def test_candidate_loss_series_tracks_best_so_far_and_the_baseline(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "candidate_scores.json").write_text(json.dumps({
        "val_aggregate_scores": [0.58, 0.50, 0.70],
        "discovery_eval_counts": [0, 12, 24],
        "parents": [[], [0], [0]],
        "best_idx": 2,
    }))

    series = extract.candidate_loss_series(run_dir, baseline_correctness=0.60)

    assert series["baseline_loss"] == pytest.approx(0.40)
    assert [round(p["loss"], 2) for p in series["points"]] == [0.42, 0.50, 0.30]
    # Candidate 1 scored worse than candidate 0, so best-so-far holds at
    # candidate 0's loss instead of getting worse.
    assert [round(p["best_so_far"], 2) for p in series["points"]] == [0.42, 0.42, 0.30]
    assert series["best_idx"] == 2


def test_recent_proposals_reads_newest_first(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "gepa").mkdir(parents=True)
    path = run_dir / "gepa" / "proposals.jsonl"
    path.write_text("\n".join([
        json.dumps({"iteration": 1, "component": "cli.py", "accepted": True}),
        json.dumps({"iteration": 2, "component": "cli.py", "accepted": False}),
    ]) + "\n")

    rows = extract.recent_proposals(run_dir)

    assert [r["iteration"] for r in rows] == [2, 1]


def test_recent_proposals_skips_a_mid_write_line(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "gepa").mkdir(parents=True)
    path = run_dir / "gepa" / "proposals.jsonl"
    path.write_text(
        json.dumps({"iteration": 1, "component": "cli.py", "accepted": True}) + "\n"
        + '{"iteration": 2, "component": "cli.py"'  # truncated mid-write
    )

    rows = extract.recent_proposals(run_dir)

    assert len(rows) == 1
    assert rows[0]["iteration"] == 1


def test_recent_proposals_is_empty_when_the_file_does_not_exist_yet(tmp_path):
    assert extract.recent_proposals(tmp_path / "run") == []
