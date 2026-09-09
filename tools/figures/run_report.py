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


def _baseline_correctness(sha: str) -> tuple[float | None, Path]:
    """Mean correctness across a *complete* baseline, and its attempts dir.

    These are deliberately decoupled: the attempts dir is a plain path,
    known and readable the moment baseline.measure() starts writing to it,
    one record-v2.json at a time -- exactly what a progress UI needs while
    baseline measurement is still in flight, well before the full
    baseline.json (and the aggregate correctness the loss chart's reference
    line needs) exists. Correctness comes back None until load() succeeds --
    no baseline yet, or it was saved with gaps and load() refuses it (see
    autoresearch/baseline.py) -- but the attempts directory is returned
    either way, so pass-rate/duration/cost can show partial progress.
    """
    from autoresearch import baseline as baseline_mod

    attempts_dir = baseline_mod.attempts_dir(sha)
    readings = baseline_mod.load(sha)
    if not readings:
        return None, attempts_dir
    import statistics
    mean_correctness = statistics.mean(r.correctness for r in readings.values())
    return mean_correctness, attempts_dir


def _lever_and_sha_from_name(run_name: str) -> tuple[str, str]:
    """Run dirs are named f"{lever}-{sha}-{int(started)}" (optimize.py).

    Parsed from the name rather than read from summary.json, which doesn't
    exist until the run finishes -- exactly the file --watch mode most needs
    to work without.
    """
    parts = run_name.rsplit("-", 2)
    if len(parts) != 3:
        raise SystemExit(f"{run_name!r} doesn't look like a run directory name "
                         f"(expected <lever>-<sha>-<timestamp>)")
    lever, sha, _timestamp = parts
    return lever, sha


def run_dir_has_started_optimizing(run_dir: Path) -> bool:
    """Whether GEPA has begun at all, vs. still measuring the baseline.

    optimize.py only constructs EngineConfig(run_dir=.../gepa) after baseline
    measurement returns, so this directory's existence is a reasonable proxy
    for "the slow, one-time baseline pass is done" without needing to parse
    anything -- it just has to exist, not contain a complete state yet.
    """
    return (run_dir / "gepa").is_dir()


def build(run_name: str) -> str:
    run_dir = RUNS_DIR / run_name
    if not run_dir.is_dir():
        raise SystemExit(f"{run_dir} does not exist -- is {run_name!r} a real run directory?")

    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else None
    if summary is not None:
        sha = summary["sha"]
    else:
        _, sha = _lever_and_sha_from_name(run_name)

    baseline_correctness, baseline_attempts = _baseline_correctness(sha)

    loss_section = ""
    scores_path = run_dir / "candidate_scores.json"
    if scores_path.exists():
        loss = extract.candidate_loss_series(run_dir, baseline_correctness)
        evals_note = summary.get("evaluations_run", "?") if summary else "?"
        panel = render.candidate_loss_panel(
            loss["points"], baseline_loss=loss["baseline_loss"], best_idx=loss["best_idx"],
            title="Every candidate GEPA proposed",
            subtitle=f'{len(loss["points"])} candidates, {evals_note} evaluations',
        )
        loss_section = f'<div class="grid">{panel}</div>'
    elif not run_dir_has_started_optimizing(run_dir):
        loss_section = (
            '<p class="note">Still measuring the baseline -- the GEPA optimization phase '
            "hasn't started yet, so there's nothing to plot here.</p>"
        )
    else:
        loss_section = (
            '<p class="note">GEPA is still searching -- candidate_scores.json is written once '
            "the whole optimization run finishes, so this fills in at the end, not incrementally.</p>"
        )

    before = extract.pass_rate_and_duration(baseline_attempts)
    candidate_attempts = run_dir / "attempts"
    after = extract.pass_rate_and_duration(candidate_attempts)
    bars_section = (
        render.pass_rate_duration_bars(before, after)
        if before is not None
        else '<p class="note">No baseline attempts recorded yet -- baseline measurement is '
             "just starting.</p>"
    )

    before_cost = extract.cost_rollup(baseline_attempts)
    after_cost = extract.cost_rollup(candidate_attempts)
    cost_rows = "".join(f"""<tr><td class="key">{escape(label)}</td><td>${cost:,.2f}</td></tr>"""
                        for label, cost in (("Baseline (before)", before_cost),
                                            ("This run's kept attempts (after)", after_cost)))

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if summary is not None:
        lever = summary.get("lever", "?")
        iterations = summary.get("iterations_requested", "?")
        status = "finished"
    else:
        lever, _ = _lever_and_sha_from_name(run_name)
        iterations = "?"
        status = "in progress"

    return f"""<div class="viz-root"><div id="tip"></div><div class="wrap">
<h1>Run report: {escape(run_name)}</h1>
<p class="lede">Lever <code>{escape(str(lever))}</code> &middot; commit {escape(sha)}
&middot; up to {escape(str(iterations))} iterations &middot; <b>{escape(status)}</b>
&middot; generated {generated}</p>

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


def _page(body: str, *, refresh_seconds: int | None = None) -> str:
    # Meta-refresh, not JS polling: this file is reopened straight from disk
    # (file://), no server behind it, so the browser itself has to be the
    # thing that decides to reload -- a live progress UI, not a page you
    # have to remember to reopen by hand.
    refresh = f'<meta http-equiv="refresh" content="{refresh_seconds}">' if refresh_seconds else ""
    return f"<!DOCTYPE html>\n<html><head><meta charset='utf-8'>{refresh}" \
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
        # A touch over the --watch interval, so the browser's own reload
        # lands after the next rebuild is already on disk, not just before it.
        refresh = args.watch + 2 if args.watch else None
        out_path.write_text(_page(build(args.run), refresh_seconds=refresh))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] wrote {out_path}")

    once()
    if args.watch:
        print(f"open {out_path} in a browser -- it reloads itself every "
              f"{args.watch}s while this keeps running (ctrl-c to stop)")
        try:
            while True:
                time.sleep(args.watch)
                once()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
