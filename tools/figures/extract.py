"""Pulls the figure data out of the run artifacts.

Two different shapes come out of this module, because the arms really are two
different kinds of experiment and flattening them into one would be a lie:

  GEPA arms   an optimizer with an iteration axis. Each iteration proposes one
              candidate, scores it on a 3-question minibatch, and only pays for
              a full valset evaluation if the minibatch improved. So the score
              trajectory is a step function that moves on accepted iterations
              and holds flat everywhere else.

  Paired arms no iteration axis at all. One before state, one after state, and
              the measured quantity is a count of failure instances rather than
              a score. Plotted as a dumbbell, never as a line.

Every number is read from experiments/runs/. Nothing is hardcoded.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# The three GEPA runs that carry a parsable run_log.txt, with the arm labels the
# paper uses. tool-narrow is the 4-file tool lever; it is the only run whose
# optimizer ever beat its own base.
GEPA_RUNS = [
    ("Arm B", "prompt", "prompt-3009509-1787544952"),
    ("Arm C", "tool, 83 files", "tool-3009509-1787550419"),
    ("tool-narrow", "tool, 4 files", "tool-3009509-1787049966"),
]

# Each paired experiment: label, the run holding the AFTER state, the subtype it
# was built to move, and the arm that produced the candidate. BEFORE is recomputed
# from the baseline over exactly the attempts the after-run contains, so the
# subsets always match.
#
# The arm labels follow the paper's Section 5: Experiments 1 and 2 came from the
# paired-experiment programme that predates the lettered arms, Experiment 3 from
# Arm D, Experiment 4 from Arm E. The run directory names carry the same
# attribution independently -- wrong-type-hint-tool-9ba1187 is Arm D's candidate
# (paper Section 6.4) and arm-e-categories-search names its arm outright.
PAIRED = [
    ("Exp 1  truncation warning", "after-categories-truncation-hint-00bff1a", "c-truncated", "paired programme"),
    ("Exp 2  wrong-column hint", "after-count-wrong-column-hint-7c794ff", "c-wrong-column", "paired programme"),
    ("Exp 3  wrong-type hint", "after-wrong-type-hint-tool-9ba1187", "c-wrong-type", "Arm D"),
    ("Exp 4  categories --search", "arm-e-categories-search-c-truncated-4a197c3", "c-truncated", "Arm E"),
]

BASELINE = "agenteval-measurement-3009509"

_NUM = r"([0-9]*\.?[0-9]+)"
_BASE = re.compile(rf"Iteration 0: Base program full valset score: {_NUM}")
_SELECTED = re.compile(rf"Iteration (\d+): Selected program (\d+) score: {_NUM}")
_SKIP = re.compile(rf"Iteration (\d+): New subsample score {_NUM} is not better than old score {_NUM}, skipping")
_NOPROP = re.compile(r"Iteration (\d+): Reflective mutation did not propose a new candidate")
_ACCEPT = re.compile(rf"Iteration (\d+): Accepted candidate \(subsample score {_NUM} -> {_NUM}\)")
_VALSET = re.compile(rf"Iteration (\d+): Valset score for new program: {_NUM}")
_PARETO = re.compile(rf"Iteration (\d+): Valset pareto front aggregate score: {_NUM}")
_BEST = re.compile(rf"Iteration (\d+): Best valset aggregate score so far: {_NUM}")
_CANDIDX = re.compile(r"Iteration (\d+): New program candidate index: (\d+)")


def parse_gepa_log(path: Path) -> dict:
    """Reads one GEPA run_log.txt into a per-iteration record.

    The log interleaves full proposed file bodies with its status lines, so we
    match on the status lines only and key everything by iteration number.
    """
    text = path.read_text(encoding="utf-8", errors="replace")

    base = float(_BASE.search(text).group(1))
    selected = {int(m.group(1)): (int(m.group(2)), float(m.group(3))) for m in _SELECTED.finditer(text)}
    skipped = {int(m.group(1)): (float(m.group(2)), float(m.group(3))) for m in _SKIP.finditer(text)}
    noprop = {int(m.group(1)) for m in _NOPROP.finditer(text)}
    accepted = {int(m.group(1)): (float(m.group(2)), float(m.group(3))) for m in _ACCEPT.finditer(text)}
    valset = {int(m.group(1)): float(m.group(2)) for m in _VALSET.finditer(text)}
    pareto = {int(m.group(1)): float(m.group(2)) for m in _PARETO.finditer(text)}
    best = {int(m.group(1)): float(m.group(2)) for m in _BEST.finditer(text)}
    candidx = {int(m.group(1)): int(m.group(2)) for m in _CANDIDX.finditer(text)}

    last = max(selected) if selected else 0
    iterations = []
    # Iteration 0 is the base program: no proposal, best-so-far is the base.
    running_best, running_pareto = base, None
    iterations.append({
        "i": 0, "outcome": "base", "parent": None, "parent_score": None,
        "candidate_score": base, "candidate_index": 0,
        "best_so_far": base, "pareto": None,
        "minibatch_old": None, "minibatch_new": None,
    })
    for i in range(1, last + 1):
        if i in accepted:
            outcome = "accepted"
            mb_old, mb_new = accepted[i]
        elif i in skipped:
            outcome = "rejected"
            mb_new, mb_old = skipped[i]
        elif i in noprop:
            outcome = "no_proposal"
            mb_old = mb_new = None
        else:
            outcome = "unknown"
            mb_old = mb_new = None

        # best/pareto are only logged on accepted iterations; hold the last
        # known value across rejected ones rather than leaving a gap.
        running_best = best.get(i, running_best)
        running_pareto = pareto.get(i, running_pareto)
        par = selected.get(i)
        iterations.append({
            "i": i, "outcome": outcome,
            "parent": par[0] if par else None,
            "parent_score": par[1] if par else None,
            "candidate_score": valset.get(i),
            "candidate_index": candidx.get(i),
            "best_so_far": running_best,
            "pareto": running_pareto,
            "minibatch_old": mb_old, "minibatch_new": mb_new,
        })
    return {"base": base, "iterations": iterations}


def gepa_series(runs_dir: Path) -> list[dict]:
    out = []
    for arm, lever, run in GEPA_RUNS:
        rd = runs_dir / run
        parsed = parse_gepa_log(rd / "gepa" / "run_log.txt")
        summary = json.loads((rd / "summary.json").read_text())
        final = parsed["iterations"][-1]["best_so_far"]
        out.append({
            "arm": arm, "lever": lever, "run": run,
            "base": parsed["base"], "final_best": final,
            "delta": final - parsed["base"],
            "beat_base": final > parsed["base"] + 1e-9,
            "heldout": summary.get("heldout_questions") or [],
            "editable_files": len(summary.get("files") or []),
            "candidates": summary.get("candidates_tried"),
            "evaluations": summary.get("evaluations_run"),
            "budget": summary.get("budget"),
            "iterations": parsed["iterations"],
        })
    return out


def paired_series(runs_dir: Path) -> list[dict]:
    """Before/after failure instances on matched attempt subsets."""
    base = json.loads((runs_dir / BASELINE / "agenteval-summary-with-retries.json").read_text())
    by_attempt = {d["attempt"]: d for d in base["details"]}

    out = []
    for label, run, subtype, arm in PAIRED:
        after = json.loads((runs_dir / run / "agenteval-summary.json").read_text())
        ids = [d["attempt"] for d in after["details"]]
        missing = [i for i in ids if i not in by_attempt]
        if missing:
            raise SystemExit(f"{run}: attempts absent from baseline, subset is not matched: {missing}")
        before_n = sum(
            1
            for i in ids
            for f in by_attempt[i].get("failures", [])
            if f.get("subtype") == subtype
        )
        out.append({
            "label": label, "run": run, "subtype": subtype, "arm": arm,
            "attempts": len(ids),
            "before": before_n,
            "after": after["subtype_counts"].get(subtype, 0),
        })
    return out


def collect(root: Path) -> dict:
    runs_dir = root / "experiments" / "runs"
    gepa = gepa_series(runs_dir)
    # questions.split() is deterministic, so every run must hold out the same
    # questions. If that ever stops being true the runs stop being comparable
    # and the shared-valset claim on the page would be wrong.
    splits = {tuple(r["heldout"]) for r in gepa}
    if len(splits) != 1:
        raise SystemExit(f"runs do not share a validation split: {splits}")
    bases = [r["base"] for r in gepa]
    baseline = json.loads((runs_dir / BASELINE / "agenteval-summary-with-retries.json").read_text())
    return {
        "commit": "3009509",
        "heldout_questions": sorted(splits.pop()),
        "base_spread": max(bases) - min(bases),
        "gepa": gepa,
        "paired": paired_series(runs_dir),
        "baseline": {
            "records": baseline["records"],
            "class_counts": baseline["class_counts"],
            "subtype_counts": baseline["subtype_counts"],
        },
    }
