#!/usr/bin/env python3
"""Builds a report for one current GEPA run: loss, pass rate, duration, cost.

    python3 tools/figures/run_report.py --run tool-abc1234-1787654321
    python3 tools/figures/run_report.py --run tool-abc1234-1787654321 --watch 30

Distinct from build_figures.py, which rebuilds the historical
gepa-trajectories.html report for the published arm-a..e study. This works
against any run this codebase produces, reading only structured JSON
artifacts (candidate_scores.json, record-v2.json, summary.json) -- nothing
here parses a text log.

--watch SECONDS reruns the build on an interval while a run is still in
progress, overwriting the output in place -- the same page, refreshed
instead of built once at the end. candidate_scores.json only exists once
the run's optimize_anything() call returns, so early in a run this shows
whatever pass-rate/duration/cost data already exists (baseline, and any
--keep-runs attempts so far) with a note that the loss plot isn't ready yet,
rather than failing outright.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import extract  # noqa: E402
import render  # noqa: E402
from build_figures import SCRIPT, STYLE  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "experiments" / "runs"
BASELINES_DIR = ROOT / "experiments" / "baselines"
OUT_DIR = ROOT / "docs" / "figures"


def _baseline_correctness(sha: str) -> tuple[float | None, Path | None]:
    """Mean correctness across a baseline's questions, and its attempts dir.

    None/None when there's no baseline yet, or it was saved with gaps and
    load()-refused (see autoresearch/baseline.py) -- a missing baseline
    reference just means the loss chart draws without one, not an error.
    """
    from autoresearch import baseline as baseline_mod

    readings = baseline_mod.load(sha)
    if not readings:
        return None, None
    import statistics
    mean_correctness = statistics.mean(r.correctness for r in readings.values())
    return mean_correctness, baseline_mod.attempts_dir(sha)


def build(run_name: str) -> str:
    run_dir = RUNS_DIR / run_name
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise SystemExit(f"no summary.json under {run_dir} -- is {run_name!r} a real run directory?")
    summary = json.loads(summary_path.read_text())
    sha = summary["sha"]

    baseline_correctness, baseline_attempts = _baseline_correctness(sha)

    loss_section = ""
    scores_path = run_dir / "candidate_scores.json"
    if scores_path.exists():
        loss = extract.candidate_loss_series(run_dir, baseline_correctness)
        panel = render.candidate_loss_panel(
            loss["points"], baseline_loss=loss["baseline_loss"], best_idx=loss["best_idx"],
            title="Every candidate GEPA proposed",
            subtitle=f'{len(loss["points"])} candidates, {summary.get("evaluations_run", "?")} evaluations',
        )
        loss_section = f'<div class="grid">{panel}</div>'
    else:
        loss_section = (
            '<p class="note">candidate_scores.json not written yet -- this run is still '
            "in progress (it's saved once optimize_anything() returns).</p>"
        )

    before = extract.pass_rate_and_duration(baseline_attempts) if baseline_attempts else None
    candidate_attempts = run_dir / "attempts"
    after = extract.pass_rate_and_duration(candidate_attempts)
    bars_section = (
        render.pass_rate_duration_bars(before, after)
        if before is not None
        else '<p class="note">No baseline attempts found for this commit yet.</p>'
    )

    before_cost = extract.cost_rollup(baseline_attempts) if baseline_attempts else 0.0
    after_cost = extract.cost_rollup(candidate_attempts)
    cost_rows = "".join(f"""<tr><td class="key">{escape(label)}</td><td>${cost:,.2f}</td></tr>"""
                        for label, cost in (("Baseline (before)", before_cost),
                                            ("This run's kept attempts (after)", after_cost)))

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lever = summary.get("lever", "?")
    iterations = summary.get("iterations_requested", "?")

    return f"""<div class="viz-root"><div id="tip"></div><div class="wrap">
<h1>Run report: {escape(run_name)}</h1>
<p class="lede">Lever <code>{escape(str(lever))}</code> &middot; commit {escape(sha)}
&middot; up to {escape(str(iterations))} iterations &middot; generated {generated}</p>

<h2>Every-candidate loss</h2>
{loss_section}

<h2>Pass rate &amp; duration, before vs. after</h2>
{bars_section}

<h2>Cost</h2>
<table><tbody>{cost_rows}</tbody></table>

<p class="prov">Source: <code>experiments/runs/{escape(run_name)}/</code> and
<code>experiments/baselines/{escape(sha)}*</code>. Rebuild anytime with
<code>python3 tools/figures/run_report.py --run {escape(run_name)}</code>.</p>
</div></div>"""


def _page(body: str) -> str:
    return f"<!DOCTYPE html>\n<html><head><meta charset='utf-8'>" \
           f"<title>Run report</title><style>{STYLE}</style></head>" \
           f"<body>{body}<script>{SCRIPT}</script></body></html>\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, metavar="NAME",
                    help="run directory name under experiments/runs/")
    ap.add_argument("--watch", type=int, metavar="SECONDS",
                    help="rebuild on this interval instead of once, overwriting the "
                         "output in place -- for watching a run that's still in progress")
    args = ap.parse_args()

    out_path = OUT_DIR / f"run-report-{args.run}.html"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    def once() -> None:
        out_path.write_text(_page(build(args.run)))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] wrote {out_path}")

    once()
    if args.watch:
        try:
            while True:
                time.sleep(args.watch)
                once()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
