#!/usr/bin/env python3
"""Builds docs/figures/gepa-trajectories.html from the run artifacts.

    python3 tools/figures/build_figures.py

Writes a self-contained page (no external assets, no JS libraries) plus the
figure-data.json it was drawn from, so every number on the page can be checked
against experiments/runs/ without rerunning anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import extract  # noqa: E402
import render  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "figures"

STYLE = """
:root { color-scheme: light dark; }
.viz-root {
  color-scheme: light;
  --page: #f9f9f7; --surface-1: #fcfcfb;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,.10);
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a;
  --ramp-light: #86b6ef; --ramp-dark: #1c5cab; --connector: #c3c2b7;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) .viz-root {
    color-scheme: dark;
    --page: #0d0d0d; --surface-1: #1a1a19;
    --text-primary: #fff; --text-secondary: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,.10);
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70;
    --ramp-light: #86b6ef; --ramp-dark: #184f95; --connector: #383835;
  }
}
:root[data-theme="dark"] .viz-root {
  color-scheme: dark;
  --page: #0d0d0d; --surface-1: #1a1a19;
  --text-primary: #fff; --text-secondary: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,.10);
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70;
  --ramp-light: #86b6ef; --ramp-dark: #184f95; --connector: #383835;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); }
.viz-root {
  background: var(--page); color: var(--text-primary); min-height: 100vh;
  font: 14px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
  padding: 40px 24px 72px;
}
.wrap { max-width: 1000px; margin: 0 auto; }
h1 { font-size: 25px; line-height: 1.25; margin: 0 0 6px; letter-spacing: -.01em; }
h2 { font-size: 17px; margin: 44px 0 4px; letter-spacing: -.005em; }
h3 { font-size: 14.5px; margin: 26px 0 2px; letter-spacing: -.003em; }
table.arms td, table.arms th { text-align: left; font-variant-numeric: normal; vertical-align: top; }
table.arms td:first-child { white-space: nowrap; }
.lede, .note { color: var(--text-secondary); margin: 0 0 4px; }
.prov { color: var(--muted); font-size: 12.5px; margin: 10px 0 0; }
.callout {
  border: 1px solid var(--border); border-left: 3px solid var(--series-2);
  background: var(--surface-1); border-radius: 8px;
  padding: 14px 16px; margin: 22px 0 8px; color: var(--text-secondary);
}
.callout b { color: var(--text-primary); }
.card {
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 10px; padding: 18px 18px 10px; margin: 14px 0;
}
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); gap: 8px; }
.panel { width: 100%; height: auto; display: block; overflow: visible; }
.panel-fig { margin: 0; }
.panel-fig figcaption { margin: 0 0 2px 4px; font-size: 13px; }
.panel-fig figcaption b { color: var(--text-primary); }
.panel-fig figcaption span { color: var(--muted); margin-left: 8px; font-size: 12.5px; }
.tick { fill: var(--muted); font-size: 10.5px; font-variant-numeric: tabular-nums; }
.axis-title { fill: var(--muted); font-size: 11px; }
.endlabel { font-size: 11.5px; font-weight: 600; }
.rowlabel { fill: var(--text-primary); font-size: 12.5px; }
.rowsub { fill: var(--muted); font-size: 11px; }
.endval { fill: var(--text-secondary); font-size: 12.5px; font-variant-numeric: tabular-nums; }
.dot { cursor: default; }
.legend { display: flex; flex-wrap: wrap; gap: 16px; margin: 4px 0 2px 4px; font-size: 12.5px; color: var(--text-secondary); }
.legend span { display: inline-flex; align-items: center; gap: 7px; }
.sw { width: 20px; height: 3px; border-radius: 2px; display: inline-block; }
.sw.dot-sw { width: 10px; height: 10px; border-radius: 50%; }
table { border-collapse: collapse; width: 100%; font-size: 12.5px; margin-top: 6px; }
th, td { text-align: right; padding: 6px 10px; border-bottom: 1px solid var(--grid); font-variant-numeric: tabular-nums; }
th:first-child, td:first-child { text-align: left; font-variant-numeric: normal; }
th { color: var(--muted); font-weight: 600; }
td { color: var(--text-secondary); }
td.key { color: var(--text-primary); }
details { margin: 10px 0 0; }
summary { cursor: pointer; color: var(--text-secondary); font-size: 12.5px; padding: 4px 0; }
ul.bullets { margin: 6px 0 14px; padding-left: 20px; color: var(--text-secondary); }
ul.bullets li { margin: 5px 0; }
ul.bullets b { color: var(--text-primary); }
.arm-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px; margin: 12px 0; }
.arm-card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; }
.arm-card .tag { display: inline-block; font-size: 10.5px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
.arm-card h4 { margin: 4px 0 6px; font-size: 13.5px; }
.arm-card p { margin: 0 0 6px; font-size: 12.5px; color: var(--text-secondary); }
.arm-card .result { font-size: 12.5px; color: var(--text-primary); font-weight: 600; }
a.trace { font-size: 11.5px; white-space: nowrap; }
.pending { color: var(--muted); font-size: 11.5px; font-style: italic; }
.pbars { display: flex; flex-direction: column; gap: 18px; margin: 12px 0 4px; }
.pbar-row { display: grid; grid-template-columns: minmax(150px, 220px) 1fr 52px; gap: 14px; align-items: center; }
.pbar-label b { display: block; font-size: 12.5px; color: var(--text-primary); }
.pbar-label .rowsub { display: block; font-size: 11px; color: var(--muted); margin-top: 2px; }
.pbar-track { display: flex; flex-direction: column; gap: 5px; }
.pbar-line { display: flex; align-items: center; gap: 8px; }
.pbar-wrap { flex: 1; background: var(--grid); border-radius: 3px; height: 12px; overflow: hidden; }
.pbar-bar { height: 100%; border-radius: 3px; min-width: 2px; }
.pbar-bar.before { background: var(--ramp-light); }
.pbar-bar.after { background: var(--ramp-dark); }
.pbar-val { font-size: 11px; color: var(--text-secondary); font-variant-numeric: tabular-nums; width: 22px; text-align: right; }
.pbar-delta { text-align: right; font-size: 13px; font-weight: 600; color: var(--series-3); white-space: nowrap; }
#tip {
  position: fixed; pointer-events: none; opacity: 0; transition: opacity .1s;
  background: var(--surface-1); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: 7px;
  padding: 7px 10px; font-size: 12px; max-width: 320px;
  box-shadow: 0 6px 22px rgba(0,0,0,.18); z-index: 9;
}
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .93em; }
footer { color: var(--muted); font-size: 12.5px; margin-top: 40px; }
"""

SCRIPT = """
(function () {
  var tip = document.getElementById('tip');
  document.addEventListener('mouseover', function (e) {
    var t = e.target.closest('[data-tip]');
    if (!t) return;
    tip.textContent = t.getAttribute('data-tip');
    tip.style.opacity = '1';
  });
  document.addEventListener('mousemove', function (e) {
    if (tip.style.opacity !== '1') return;
    var r = tip.getBoundingClientRect();
    var x = Math.min(e.clientX + 14, window.innerWidth - r.width - 8);
    var y = Math.max(e.clientY - r.height - 12, 8);
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  });
  document.addEventListener('mouseout', function (e) {
    if (e.target.closest('[data-tip]')) tip.style.opacity = '0';
  });
})();
"""


# Where each run's trace lives on the HF dataset. Confirmed 2026-08-31 by
# browsing https://huggingface.co/datasets/nilenso/autoresearch/tree/main --
# the mirror lives under agent-friendly-cli/, reorganized into named
# experiment/arm folders (not a flat copy of this repo's own paths, and not
# the older experiments/published/.../run-summaries/*.json snapshot scheme).
# Each run links to its confirmed `runs/` directory rather than a guessed
# leaf filename, since individual filenames inside it were not verified.
HF_BASE = "https://huggingface.co/datasets/nilenso/autoresearch/tree/main/agent-friendly-cli/"
RUN_DIR = {
    "agenteval-measurement-3009509": "experiments/00-baseline-agenteval/runs",
    "agenteval-measurement-3009509-retry-incomplete": "experiments/00-baseline-agenteval/runs",
    "after-categories-truncation-hint-00bff1a": "experiments/01-categories-truncation-warning/runs",
    "after-count-wrong-column-hint-7c794ff": "experiments/02-count-wrong-column-hint/runs",
    "after-wrong-type-hint-tool-9ba1187": "experiments/03-wrong-type-hint-arm-d/runs",
    "prompt-3009509-1787544952": "arms/arm-b-prompt-gepa/runs",
    "tool-3009509-1787550419": "arms/arm-c-full-repo-gepa/runs",
    "arm-e-categories-search-c-truncated-4a197c3": "arms/arm-e-failure-routed-search/runs",
    "arm-a-new-evaluator-count-zero-hint-9a2496d": "arms/arm-a-loop-as-skill",
    "arm-a-new-evaluator-skill-bus-station-6c04003": "arms/arm-a-loop-as-skill",
    "arm-a-new-evaluator-count-flag-parity-05ef72c": "arms/arm-a-loop-as-skill",
}
# tool-narrow's exact folder under arm-c-full-repo-gepa/{runs,invalid-runs}
# was not confirmed by directory browsing, so it is not linked rather than
# guessed at.
PENDING_TRACE = {
    "tool-3009509-1787049966": "not confirmed under HF arms/arm-c-full-repo-gepa/ — local: experiments/runs/tool-3009509-1787049966/",
}
REPORT_DIR = {
    "Arm A": "arms/arm-a-loop-as-skill",
    "Arm B": "arms/arm-b-prompt-gepa",
    "Arm C": "arms/arm-c-full-repo-gepa",
    "Arm D": "experiments/03-wrong-type-hint-arm-d/arm-d",
    "Arm E": "arms/arm-e-failure-routed-search",
}
# The run each arm-row is best represented by, for a single trace link per card.
ARM_RUN = {
    "Arm B": "prompt-3009509-1787544952",
    "Arm C": "tool-3009509-1787550419",
    "tool-narrow": "tool-3009509-1787049966",
    "Arm D": "after-wrong-type-hint-tool-9ba1187",
    "Arm E": "arm-e-categories-search-c-truncated-4a197c3",
}


def trace_link(run_id: str) -> str:
    if run_id in RUN_DIR:
        return f'<a class="trace" href="{HF_BASE}{RUN_DIR[run_id]}" target="_blank" rel="noopener">browse run &#8599;</a>'
    if run_id in PENDING_TRACE:
        return f'<span class="pending" title="{escape(PENDING_TRACE[run_id])}">not confirmed</span>'
    return "&mdash;"


def report_link(arm: str) -> str:
    if arm in REPORT_DIR:
        return f'<a class="trace" href="{HF_BASE}{REPORT_DIR[arm]}" target="_blank" rel="noopener">arm folder &#8599;</a>'
    return ""


def gepa_table(runs: list[dict]) -> str:
    head = (
        "<tr><th>Run</th><th>Lever</th><th>Editable files</th><th>Candidates</th>"
        "<th>Evaluations</th><th>Base</th><th>Final best</th><th>Delta</th><th>Trace</th></tr>"
    )
    rows = "".join(
        f'<tr><td class="key">{r["arm"]}</td><td>{r["lever"]}</td>'
        f'<td>{r["editable_files"]}</td><td>{r["candidates"]}</td>'
        f'<td>{r["evaluations"]}</td><td>{r["base"]:.4f}</td>'
        f'<td>{r["final_best"]:.4f}</td><td>{r["delta"]:+.4f}</td>'
        f'<td>{trace_link(r["run"])}</td></tr>'
        for r in runs
    )
    return f"<table>{head}{rows}</table>"


def iteration_table(runs: list[dict]) -> str:
    head = (
        "<tr><th>Run</th><th>Iter</th><th>Outcome</th><th>Parent</th>"
        "<th>Candidate score</th><th>Best so far</th></tr>"
    )
    body = []
    for r in runs:
        for it in r["iterations"]:
            cand = "—" if it["candidate_score"] is None else f'{it["candidate_score"]:.4f}'
            parent = "—" if it["parent"] is None else str(it["parent"])
            body.append(
                f'<tr><td class="key">{r["arm"]}</td><td>{it["i"]}</td>'
                f'<td>{it["outcome"].replace("_", " ")}</td><td>{parent}</td>'
                f'<td>{cand}</td><td>{it["best_so_far"]:.4f}</td></tr>'
            )
    return f'<table>{head}{"".join(body)}</table>'


def paired_table(rows: list[dict]) -> str:
    head = (
        "<tr><th>Experiment</th><th>Arm</th><th>Subtype</th><th>Attempts</th>"
        "<th>Before</th><th>After</th><th>Change</th><th>Trace</th></tr>"
    )
    body = "".join(
        f'<tr><td class="key">{r["label"]}</td><td>{r.get("arm", "—")}</td>'
        f'<td>{r["subtype"]}</td>'
        f'<td>{r["attempts"]}</td><td>{r["before"]}</td><td>{r["after"]}</td>'
        f'<td>{r["after"] - r["before"]:+d}</td><td>{trace_link(r["run"])}</td></tr>'
        for r in rows
    )
    return f"<table>{head}{body}</table>"


# The five arms as the paper describes them (Sections 6.1-6.5). This is study
# structure, not measurement: only the "result" column is echoed from run data,
# and every such number also appears in a figure above it. Arm A never produced
# a plottable outcome, which is itself the finding.
ARMS = [
    ("Arm A", "Can an agent run the whole research loop itself?",
     "3 candidates, the whole 60-attempt bank each",
     "None accepted. Two enrichments timed out; one run halted at 37/60.",
     "not plotted"),
    ("Arm B", "Can agent-friendliness be supplied as instructions?",
     "botmap/data/skill.md only",
     "+0.0000. Best held-out program was the base prompt; final patch empty.",
     "Figure 1"),
    ("Arm C", "Does seeing the whole codebase help it find the right file to fix?",
     "83 tracked files, ~557k chars of context",
     "+0.0060, within noise (not a real gain). Best patch edited .gitignore and left &quot;new file needed&quot; notes.",
     "Figure 1"),
    ("tool-narrow", "Same idea as Arm C, but allowed to touch far less.",
     "4 files",
     "+0.0161. The biggest gain any optimizer managed — still inside the wobble.",
     "Figure 1"),
    ("Arm D", "Can the list of measured failures tell us what to try next?",
     "1 tool-side hint (7 experiments proposed, 1 run here, 1 handed to Arm E)",
     "c-wrong-type 3 &#8594; 0 on a 4-attempt subset.",
     "Figure 2, Exp 3"),
    ("Arm E", "What if we only test a change where it could possibly help?",
     "1 new subcommand",
     "c-truncated 25 &#8594; 1 on the full 13-attempt affected subset.",
     "Figure 2, Exp 4"),
]


# What each failure class means. The counts come from the data; these
# descriptions are the taxonomy from paper Section 3.1.
CLASS_MEANING = {
    "clean": "The call did what was asked and told no lies.",
    "A": "Hard failure — usage error or traceback, with no usable way forward.",
    "B": "Guided failure — the command failed but named a next step, so the agent could recover.",
    "C": "Silent wrong — the command succeeded and misled the agent anyway. The dangerous one.",
    "D": "Wasteful route — the agent got there via a needlessly broad or expensive path.",
}


def baseline_table(data: dict) -> str:
    cc = data["baseline"]["class_counts"]
    total = sum(cc.values())
    order = ["clean", "C", "A", "B", "D"]
    head = "<tr><th>Class</th><th>What it means</th><th>Calls</th><th>Share</th></tr>"
    body = "".join(
        f'<tr><td class="key">{k}</td><td>{CLASS_MEANING[k]}</td>'
        f'<td>{cc[k]}</td><td>{100 * cc[k] / total:.1f}%</td></tr>'
        for k in order if k in cc
    )
    return f'<table class="arms">{head}{body}</table>'


def arms_cards() -> str:
    cards = []
    for arm, q, surface, result, where in ARMS:
        pieces = [report_link(arm)]
        if arm in ARM_RUN:
            pieces.append(trace_link(ARM_RUN[arm]))
        links = " &middot; ".join(x for x in pieces if x)
        cards.append(
            f'<div class="arm-card"><span class="tag">{where}</span>'
            f'<h4>{arm}</h4><p>{q}</p>'
            f'<p><b>Could change:</b> {surface}</p>'
            f'<p class="result">{result}</p>'
            f'{f"<p>{links}</p>" if links else ""}</div>'
        )
    return f'<div class="arm-cards">{"".join(cards)}</div>'


# Failure taxonomy from paper §3.1 / autoresearch/agenteval/score.py
# CLASS_SEVERITY_PENALTIES. The penalty is how hard a class is charged in the
# attribution sub-score (2 of the 100 points) -- it is not a share of the 60%.
CLASS_TAXONOMY = [
    ("A", "Hard / unguided failure", "usage error, raw traceback, no usable way forward", 1.00),
    ("B", "Guided / recoverable failure", "command fails but names a usable next step", 0.10),
    ("C", "Silent wrong", "command succeeds or looks plausible, but misleads the agent", 1.00),
    ("D", "Degenerate route", "works, but via a needlessly broad or expensive path", 0.45),
    ("E", "Environment / quota failure", "excluded entirely — never charged to the CLI", None),
    ("F", "Agent-side failure", "e.g. an ignored hint — recorded, not charged to the CLI", None),
]

# The scoring rubric's fixed shape (paper §3.3; autoresearch/agenteval/score.py).
SCORE_TOP = [
    {"name": "Correctness & recoverability", "value": 60, "fill": "var(--series-2)"},
    {"name": "Token efficiency", "value": 20, "fill": "var(--series-1)"},
    {"name": "Wall-clock time", "value": 20, "fill": "var(--series-3)"},
]
SCORE_SUB = [
    {"name": "Final outcome", "value": 20, "fill": "var(--series-2)"},
    {"name": "Self-recovery", "value": 20, "fill": "var(--ramp-dark)"},
    {"name": "Guidance quality", "value": 12, "fill": "var(--ramp-light)"},
    {"name": "Route quality", "value": 6, "fill": "var(--series-1)"},
    {"name": "Attribution", "value": 2, "fill": "var(--muted)"},
]


def evaluator_design_section() -> str:
    taxonomy_items = "".join(
        f'<li><b>Class {c} &mdash; {name}:</b> {desc}'
        + (f' <span class="pending">(attribution penalty {pen:.2f})</span>'
           if pen is not None else ' <span class="pending">(not charged to the CLI)</span>')
        + '</li>'
        for c, name, desc, pen in CLASS_TAXONOMY
    )
    return f"""
<h2>Evaluator design</h2>
<ul class="bullets">
<li><b>Tool under test:</b> <code>botmap</code>, a CLI over Overture map data &mdash;
multiple resource types, domain vocabulary, structured filters, ambiguous place
names, large/expensive outputs.</li>
<li><b>Task:</b> the agent gets a plain-English question and a shell, nothing else.
Every command, output, token count, timing and final answer is recorded.</li>
<li><b>Why the naive scorer (&quot;did it error?&quot;) was replaced:</b> it punished
helpful error messages and rewarded silent zero-result answers &mdash; a clean exit
code is not the same thing as a correct answer.</li>
</ul>

<h3>Failure taxonomy</h3>
<ul class="bullets">{taxonomy_items}</ul>
<p class="note">Class C is further split by subtype: <code>c-truncated</code> (a capped
list read as complete), <code>c-unknown</code> (an unexplained empty result),
<code>c-wrong-type</code> (right filter, wrong resource type), <code>c-wrong-column</code>
(right filter, wrong field). Figure 0 below shows how the baseline's 111 failure
instances split across these.</p>

<h3>Scoring rubric &mdash; how the 100 points split</h3>
<div class="card">
<figure class="panel-fig"><figcaption><b>Top level</b>
<span>correctness/recoverability vs. token efficiency vs. speed</span></figcaption>
{render.stacked_bar(SCORE_TOP, label="Top-level score weights")}
{render.bar_legend(SCORE_TOP)}</figure>
<figure class="panel-fig" style="margin-top:14px"><figcaption><b>Inside the 60 correctness points</b>
<span>5 scoring components &mdash; not the failure classes directly</span></figcaption>
{render.stacked_bar(SCORE_SUB, label="Correctness/recoverability sub-weights", pct_of=100)}
{render.bar_legend(SCORE_SUB, pct_of=100)}</figure>
</div>
<ul class="bullets">
<li>60/20/20 means an agent-friendly CLI is graded mostly on <b>whether the agent could
recover</b>, not on how fast or cheap the attempt was.</li>
<li>The 60 correctness points split into 5 <i>scoring components</i>, not the 4 failure
classes: <b>final outcome 20</b>, <b>self-recovery 20</b>, <b>guidance quality 12</b>,
<b>route quality 6</b>, <b>attribution 2</b>.</li>
<li>Failure-class severity (the A/B/C/D penalties above) only feeds into
<b>attribution</b> &mdash; the smallest slice, 2 of 100 points. Class B is charged at
just 0.10 because a guided failure is mostly forgiven once the agent uses the
guidance to recover.</li>
</ul>

<h3>Guardrails</h3>
<ul class="bullets">
<li><b>Differential probes:</b> a suspicious zero (e.g.
<code>--where subtype=bicycle_parking</code> &#8594; 0) is re-tested under a related
filter before it is trusted as a real absence.</li>
<li><b>Sabotage gate:</b> known-bad fixtures for every class/subtype must be caught
before an optimizer run is allowed to start.</li>
</ul>
"""


def read_across(data: dict) -> str:
    """The section that says why so little moved, computed where it can be."""
    runs = data["gepa"]
    # Iteration 0 records the untouched tool's own score under candidate_score.
    # It is the thing candidates are compared against, not a candidate, so it
    # must not be counted as one.
    evaluated = [
        (r["arm"], it["candidate_score"], r["base"])
        for r in runs for it in r["iterations"]
        if it.get("candidate_score") is not None and it["outcome"] != "base"
    ]
    below = [e for e in evaluated if e[1] < e[2]]
    budget = sum(r["evaluations"] for r in runs)
    wide = next(r for r in runs if r["arm"] == "Arm C")
    narrow = next(r for r in runs if r["arm"] == "tool-narrow")
    per_file = wide["evaluations"] / wide["editable_files"]
    spread = data["base_spread"]
    sub = data["baseline"]["subtype_counts"]
    unknown, class_c = sub.get("c-unknown", 0), sum(sub.values())
    paired = {r["label"].split("  ")[0]: r for r in data["paired"]}
    exp1, exp2, exp3, exp4 = paired["Exp 1"], paired["Exp 2"], paired["Exp 3"], paired["Exp 4"]

    return f"""
<h2>Reading across the arms</h2>
<p class="note">Figure 1 asks &quot;did the score go up?&quot; Figure 2 asks &quot;did
this specific failure stop happening?&quot; The second question got useful answers;
the first mostly did not &mdash; that gap is the real finding.</p>

<h3>Why the optimizer arms barely moved</h3>
<ul class="bullets">
<li><b>The ruler was coarser than what it measured:</b> three runs of the unchanged
tool scored {spread:.3f} apart &mdash; bigger than every optimizer gain on this page.</li>
<li><b>The budget bought very few real looks:</b> {budget} evaluations across all
three runs produced only {len(evaluated)} fully-tested candidates, and {len(below)}
of those scored worse than the base they started from. Arm C had ~{per_file:.1f}
evaluations per editable file &mdash; not a search, a coin toss.</li>
<li><b>A bigger edit surface made search worse, not better:</b> Arm C
({wide["editable_files"]} files) spent its best patch on <code>.gitignore</code>;
the narrow run ({narrow["editable_files"]} files) produced the biggest optimizer
gain on the page ({narrow["delta"]:+.4f}).</li>
<li><b>Optimizers spotted the problem but couldn't build the fix:</b> both GEPA arms
noticed agents struggling to discover category names, but turned it into longer
instructions (Arm B) or an unwritten <code>suggest.py</code> note (Arm C). Arm E
turned the same signal into one working command,
<code>botmap categories --search TERM</code>, moving its target failure
{exp4["before"]} &#8594; {exp4["after"]}.</li>
</ul>

<h3>What actually improved</h3>
<ul class="bullets">
<li><b>Exp 1 &mdash; truncation warning:</b> {exp1["before"]} &#8594; {exp1["after"]}
on {exp1["attempts"]} attempts.</li>
<li><b>Exp 2 &mdash; wrong-column hint:</b> {exp2["before"]} &#8594; {exp2["after"]}
on {exp2["attempts"]} attempts.</li>
<li><b>Exp 3 &mdash; wrong-type hint (Arm D):</b> {exp3["before"]} &#8594; {exp3["after"]}
on {exp3["attempts"]} attempts, only 2/4 completed &mdash; provisional.</li>
<li><b>Exp 4 &mdash; <code>categories --search</code> (Arm E):</b>
{exp4["before"]} &#8594; {exp4["after"]} across every affected attempt &mdash; the
strongest, most trustworthy result in the study.</li>
<li><b>tool-narrow (GEPA, 4 files):</b> {narrow["delta"]:+.4f} &mdash; the only
optimizer gain, and it still sits inside the {spread:.3f} noise band.</li>
</ul>

<h3>What went wrong this round</h3>
<ul class="bullets">
<li><b>The wobble was never measured directly</b> &mdash; the {spread:.3f} spread
comes from 3 accidental data points, not a designed noise run. A 60-attempt repeat
run exists but recorded failure <i>kinds</i>, not the score each time.</li>
<li><b>Arm A screened on everything instead of what mattered</b> &mdash; all 60
attempts per candidate; two of three enrichments timed out, one run halted at 37/60.</li>
<li><b>The evaluator itself had a bug for part of the run</b> &mdash; US state codes
and country codes were confused (<code>Cambridge, MA</code> vs.
<code>Malta, MT</code>); fixing it changed the failure distribution.</li>
<li><b>Some results shipped on samples too small to trust:</b> Exp 3 moved
{exp3["before"]} &#8594; {exp3["after"]} on 4 attempts, only 2 finished.</li>
</ul>

<h3>What to change in the next run</h3>
<ul class="bullets">
<li><b>Measure the wobble first:</b> run the unchanged tool 10&ndash;20&times; before
spending budget on candidates; require gains to clear ~2&times; the standard deviation.</li>
<li><b>Fewer files, more looks:</b> the 4-file run beat the 83-file run.</li>
<li><b>Route by failure class from the start</b> &mdash; test a candidate only on
the attempts it targets, the way Arm E did.</li>
<li><b>Raise the minimum sample size</b> &mdash; Exp 2 and Exp 3 tested on just 4
attempts each; 4 attempts cannot separate a fix from a coincidence, unlike Exp 4's
full 13-attempt affected subset.</li>
<li><b>Mine rejected optimizer proposals deliberately</b> &mdash; the discards
(zero-result diagnostics, place-name normalisation, a suggestions module) were as
valuable as the accepted patches.</li>
<li><b>Fix instrumentation debt first:</b> {unknown} of {class_c} silent-wrong
instances ({100 * unknown / class_c:.0f}%) are still unexplained
(<code>c-unknown</code>) &mdash; nothing can target that bucket until better probes
split it up.</li>
</ul>
"""


def build(data: dict) -> str:
    runs, paired = data["gepa"], data["paired"]
    held = ", ".join(f"<code>{q}</code>" for q in data["heldout_questions"])
    spread = data["base_spread"]
    spread_txt = " to ".join(f"{v:.4f}" for v in (min(r["base"] for r in runs), max(r["base"] for r in runs)))
    cc = dict(data["baseline"]["class_counts"])
    sc = dict(data["baseline"]["subtype_counts"])
    records, calls = data["baseline"]["records"], sum(cc.values())
    class_c, failures = cc.get("C", 0), sum(v for k, v in cc.items() if k != "clean")
    truncated, unknown = sc.get("c-truncated", 0), sc.get("c-unknown", 0)
    # Class order is fixed rather than sorted by size, so the bar reads
    # clean-then-worsening and stays stable if the counts ever change.
    class_segments = [
        {"name": "clean", "value": cc["clean"], "fill": "var(--ramp-light)"},
        {"name": "C silent wrong", "value": cc.get("C", 0), "fill": "var(--series-2)"},
        {"name": "A hard fail", "value": cc.get("A", 0), "fill": "var(--series-1)"},
        {"name": "B guided fail", "value": cc.get("B", 0), "fill": "var(--series-3)"},
        {"name": "D wasteful", "value": cc.get("D", 0), "fill": "var(--muted)"},
    ]
    subtype_segments = [
        {"name": k, "value": v, "fill": f}
        for k, f in (("c-truncated", "var(--series-2)"), ("c-unknown", "var(--muted)"),
                     ("c-wrong-type", "var(--series-1)"), ("c-wrong-column", "var(--series-3)"))
        if (v := sc.get(k, 0))
    ]
    by_arm = {r["arm"]: r["delta"] for r in runs}
    delta_c, delta_t = by_arm["Arm C"], by_arm["tool-narrow"]
    ratio_c, ratio_t = spread / delta_c, spread / delta_t
    legend = "".join(
        f'<span><i class="sw" style="background:var(--series-{i + 1})"></i>'
        f'{r["arm"]} <span style="color:var(--muted)">({r["lever"]})</span></span>'
        for i, r in enumerate(runs)
    )
    never = [r for r in runs if not r["beat_base"]]

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Optimizer trajectories — agent-friendly CLI study</title>
<style>{STYLE}</style></head>
<body><div class="viz-root"><div class="wrap">

<h1>Optimizer trajectories and paired outcomes</h1>
<p class="lede">Figures for <i>What Makes a Command-Line Interface Agent-Friendly?</i>
Every value is read from <code>experiments/runs/</code> at build time.</p>
<p class="prov">botmap commit <code>{data["commit"]}</code> · baseline
{data["baseline"]["records"]} attempts · generated {date.today().isoformat()} by
<code>tools/figures/build_figures.py</code> ·
<a href="https://huggingface.co/datasets/nilenso/autoresearch" target="_blank"
rel="noopener">dataset &amp; traces on Hugging Face &#8599;</a></p>

{evaluator_design_section()}

<details><summary>Terms used on this page (glossary)</summary>
<div class="card"><table class="arms">
<tr><th>Term</th><th>What it means</th></tr>
<tr><td class="key">rubric score</td><td>A grade from 0 to 1 that the evaluator gives one
attempt at one question. Higher is better. 60% of it is about whether the agent
recovered from trouble, not just whether it got the answer.</td></tr>
<tr><td class="key">held-out set</td><td>Five questions kept aside and never used to
guide the optimizer, so we can check it learned something general rather than
memorising the practice questions.</td></tr>
<tr><td class="key">candidate</td><td>One proposed edit to the tool or its instructions.
The optimizer invents these, then has to decide whether to pay to test each one.</td></tr>
<tr><td class="key">minibatch</td><td>A cheap 3-question screening test. A candidate must
beat its parent here before it earns a full, expensive test on all five held-out
questions. This is why most iterations cost nothing and the line stays flat.</td></tr>
<tr><td class="key">evaluation</td><td>One grading of one candidate. <b>The budget was
60 evaluations</b> — not 60 iterations and not 60 questions. The runs actually spent
61 to 63.</td></tr>
<tr><td class="key">iteration</td><td>One round of: propose a change, screen it cheaply,
maybe test it fully. A single iteration can burn several evaluations, which is why a
budget of 60 evaluations bought only 8 or 9 iterations — that is the whole x-axis of
Figure 1.</td></tr>
<tr><td class="key">attempt</td><td>One agent trying one question once. Every question is
run twice, so the baseline's <b>60 attempts are 30 questions run twice</b>, not 60
questions.</td></tr>
<tr><td class="key">call</td><td>One <code>botmap</code> command run inside an attempt.
The baseline's 60 attempts contain about 500 calls, and it is calls that get
classified.</td></tr>
<tr><td class="key">failure instance</td><td>One call classified as a failure. <b>Figure 2
counts these, not attempts.</b> One attempt can contain several, which is why Exp 4's
25 instances live in only 13 attempts.</td></tr>
<tr><td class="key">failure subtype</td><td>A named way the agent got it wrong — for example
<code>c-truncated</code> means a list was silently cut short, so the agent read a
partial answer as a complete one. Figure 2 counts these instead of scoring them.</td></tr>
</table></div></details>

<h2>Figure 0 · What the baseline looked like</h2>
<p class="note">Everything on this page is measured against one baseline run of the
untouched tool at commit <code>{data["commit"]}</code>: {records} attempts, of which
53 finished, costing about $15.50 and 5.4 hours of wall-clock time (paper §4). Those
attempts contain {calls} classified calls. The first bar splits every call; the
second splits the silent-wrong ones, which is the category the study is really
about. {trace_link("agenteval-measurement-3009509")}</p>
<div class="card">
<figure class="panel-fig"><figcaption><b>All {calls} calls</b>
<span>clean vs each failure class</span></figcaption>
{render.stacked_bar(class_segments, label="Baseline calls by class")}
{render.bar_legend(class_segments)}</figure>
<figure class="panel-fig" style="margin-top:14px"><figcaption><b>The {class_c} silent-wrong calls</b>
<span>class C broken down by subtype</span></figcaption>
{render.stacked_bar(subtype_segments, label="Class C failures by subtype")}
{render.bar_legend(subtype_segments)}</figure>
{baseline_table(data)}
</div>
<ul class="bullets">
<li><b>Half of everything that went wrong went wrong silently:</b> of {failures}
failure instances, {class_c} are class C — the command succeeded and misled the
agent anyway. A conventional &quot;did the command error?&quot; check would have
missed every one of them.</li>
<li>Two subtypes dominate, tied at {truncated} instances each:
<code>c-truncated</code> (a capped list read as complete) and <code>c-unknown</code>
(an empty result nobody could explain).</li>
<li>Experiments 1 and 4 both target <code>c-truncated</code>. Nothing yet targets
<code>c-unknown</code> — you cannot aim at a bucket labelled &quot;cause
unknown&quot;.</li>
</ul>

<div class="callout">
<b>Read this first: the measuring instrument wobbles more than anything it measured.</b>
All three runs started from the untouched tool and were graded on the same five
questions — the code that picks them, <code>questions.split()</code>, always picks
the same ones. Those five were {held}.
So the three starting scores <i>should</i> have been identical. They were not: they
came out {spread_txt}, a gap of <b>{spread:.3f}</b> caused by nothing but the agent
behaving differently each time.
That gap is the size of the wobble. It is {ratio_c:.0f}× bigger than Arm C's
{delta_c:+.3f} (almost certainly noise, not a real gain) and {ratio_t:.0f}× bigger
than the narrow tool run's {delta_t:+.3f}. It is like weighing yourself on a scale
that swings by two kilos
and announcing you lost sixty grams — the loss may be real, but this scale cannot
see it. <b>Read the curves below for their shape, not their height.</b>
</div>

<h2>Figure 1 · GEPA loss trajectories</h2>
<p class="note">Loss = 1 − score, lower is better. The line is the best-so-far loss —
it can only go down or stay flat, since the optimizer never throws away its best
work. Each dot is one candidate that earned a full test; most iterations cost
nothing because most candidates never pass the cheap 3-question screen first.</p>
<div class="legend">{legend}
<span><i class="sw dot-sw" style="background:var(--series-1)"></i>candidate that earned a full test</span></div>
<div class="card">
{render.line_panel(runs, invert=True, title="Loss = 1 − score", subtitle="lower is better")}
{gepa_table(runs)}
<details><summary>Per-iteration detail (every proposal, kept or discarded)</summary>
{iteration_table(runs)}</details>
</div>
<ul class="bullets">
<li>{"; ".join(f'<b>{r["arm"]}</b> ended at its base — {r["candidates"]} candidates, none better' for r in never)}.</li>
<li>On a rubric where the baseline noise band has never been established, a delta of
{delta_c:+.3f} (Arm C) is not a result — it's within measurement noise, not an
improvement. Only the narrow 4-file tool run moved far enough ({delta_t:+.3f}) to
be worth a second look, and even that sits well inside the {spread:.3f} spread
above.</li>
</ul>

<h2>Figure 2 · All experiments, at a glance</h2>
<p class="note">Five arms plus the narrow 4-file GEPA run, each asking a different
question about where agent-friendliness comes from. Result and trace/report links
per experiment:</p>
{arms_cards()}

<h3>Figure 2b · Paired before &#8594; after, on matched attempt subsets</h3>
<p class="note">These four are not optimizers, so there is nothing to plot over time.
Each is one change, made once, then measured as a count: how many times a specific
failure happened before the change vs. after, recounted over exactly the same
attempts the &quot;after&quot; run covered. Each row is scaled to its own count
(not a shared axis), so Exp 2's 2 &#8594; 0 reads as clearly as Exp 4's 25 &#8594; 1
&mdash; a shared scale would shrink the smaller experiments to invisible slivers.</p>
<div class="legend">
<span><i class="sw dot-sw" style="background:var(--ramp-light)"></i>before (baseline)</span>
<span><i class="sw dot-sw" style="background:var(--ramp-dark)"></i>after (intervention)</span></div>
<div class="card">{render.paired_bars(paired)}
{paired_table(paired)}</div>
<ul class="bullets">
<li>Experiments 2 and 3 each moved a handful of failures across only four
attempts — points the right way, but small enough to be luck.</li>
<li>Experiment 4 is the one to trust: it covered every affected attempt and all of
them finished.</li>
</ul>

{read_across(data)}

<h2>Traces &amp; runs</h2>
<p class="note">Every run referenced on this page, in one place. &quot;browse
run&quot; opens that run's directory on the
<a href="https://huggingface.co/datasets/nilenso/autoresearch" target="_blank"
rel="noopener">Hugging Face dataset</a> (confirmed 2026-08-31: it is organized
under <code>agent-friendly-cli/experiments/&lt;NN-name&gt;/runs/</code> and
<code>agent-friendly-cli/arms/&lt;arm&gt;/runs/</code>, not a flat mirror of this
repo's own paths); &quot;not confirmed&quot; means the run's exact folder wasn't
verified rather than guessed at.</p>
<div class="card"><table>
<tr><th>Run</th><th>Trace</th></tr>
{"".join(f'<tr><td class="key">{run_id}</td><td>{trace_link(run_id)}</td></tr>' for run_id in list(RUN_DIR) + list(PENDING_TRACE))}
</table>
<p class="note" style="margin-top:8px">Arm folders: {" &middot; ".join(f'<b>{a}</b> {report_link(a)}' for a in REPORT_DIR)}.</p>
</div>

<footer>Rebuild with <code>python3 tools/figures/build_figures.py</code>.
Underlying values in <code>docs/figures/figure-data.json</code>. Raw traces and arm
reports: <a href="https://huggingface.co/datasets/nilenso/autoresearch"
target="_blank" rel="noopener">huggingface.co/datasets/nilenso/autoresearch</a>.</footer>

</div></div><div id="tip"></div><script>{SCRIPT}</script></body></html>
"""


def load_committed_data() -> dict:
    """Reads the values the page was last built from.

    figure-data.json holds every plotted number, so the page can be rebuilt
    anywhere even though experiments/runs/ never leaves the machine that
    produced it. Only the prose and layout can change on this path -- the
    measurements are whatever the last real extraction wrote.
    """
    data = json.loads((OUT_DIR / "figure-data.json").read_text())
    # Older figure-data.json predates the arm attribution. Backfill it from
    # extract.PAIRED so the labels have exactly one source of truth, rather
    # than being restated here and drifting from the extractor.
    arm_by_run = {run: arm for _, run, _, arm in extract.PAIRED}
    for row in data["paired"]:
        row.setdefault("arm", arm_by_run.get(row["run"], "unattributed"))
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", metavar="DIR", type=Path,
                    help="directory holding the raw run artifacts, if they are not at "
                         "experiments/runs/. The same artifacts are published at "
                         "https://huggingface.co/datasets/nilenso/autoresearch, so a "
                         "checkout of those works here too. Without this, the build "
                         "falls back to the committed figure-data.json.")
    args = ap.parse_args()

    runs = args.runs or ROOT / "experiments" / "runs"
    if runs.is_dir():
        # extract.collect() addresses runs as <root>/experiments/runs, so hand it
        # the grandparent of whichever directory actually holds them.
        data = extract.collect(runs.resolve().parent.parent)
    elif args.runs is not None:
        raise SystemExit(f"--runs {args.runs} is not a directory")
    else:
        print(
            f"{runs} is missing — rebuilding from docs/figures/figure-data.json.\n"
            "The raw run artifacts are gitignored (384MB), so they exist only on the\n"
            "machine that produced them. Every plotted value was saved to that JSON,\n"
            "so layout and prose can be rebuilt here; the measurements cannot change."
        )
        data = load_committed_data()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "figure-data.json").write_text(json.dumps(data, indent=2) + "\n")
    (OUT_DIR / "gepa-trajectories.html").write_text(build(data))
    print(f"wrote {OUT_DIR / 'gepa-trajectories.html'}")
    print(f"wrote {OUT_DIR / 'figure-data.json'}")


if __name__ == "__main__":
    main()
