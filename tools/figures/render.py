"""Draws the figures as inline SVG. No plotting library, no build step.

Colors are the validated default palette from the data-viz reference, kept as
CSS custom properties so light and dark swap in one place. The three-series
categorical set clears every all-pairs gate in both modes; aqua sits below 3:1
on the light surface, which is why every line carries a direct label and every
figure ships a table view.
"""

from __future__ import annotations

import json
from html import escape

SERIES = ["--series-1", "--series-2", "--series-3"]

PANEL_W, PANEL_H = 430, 300
M_L, M_R, M_T, M_B = 46, 92, 14, 38


def _x(i: int, n: int) -> float:
    return M_L + (PANEL_W - M_L - M_R) * (i / n if n else 0)


def _y(v: float) -> float:
    return M_T + (PANEL_H - M_T - M_B) * (1 - v)


def _declutter(labels: list[dict], gap: float = 13.0) -> list[dict]:
    """Nudges endpoint labels apart so close final values stay readable."""
    ordered = sorted(labels, key=lambda d: d["y"])
    for a, b in zip(ordered, ordered[1:]):
        if b["y"] - a["y"] < gap:
            b["y"] = a["y"] + gap
    return ordered


def line_panel(runs: list[dict], *, invert: bool, title: str, subtitle: str) -> str:
    """One panel: best-so-far trajectory per run, with candidate evals as dots.

    invert=True plots 1 - score, so the same data reads as a descending loss.
    """
    n = max(len(r["iterations"]) - 1 for r in runs)
    val = (lambda s: 1.0 - s) if invert else (lambda s: s)
    parts = [
        f'<svg viewBox="0 0 {PANEL_W} {PANEL_H}" role="img" '
        f'aria-label="{escape(title)}. {escape(subtitle)}" class="panel">'
    ]

    # Recessive hairline grid, solid — never dashed.
    for t in range(6):
        v = t / 5
        y = _y(v)
        parts.append(
            f'<line x1="{M_L}" y1="{y:.1f}" x2="{PANEL_W - M_R}" y2="{y:.1f}" '
            f'stroke="var(--grid)" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{M_L - 8}" y="{y + 3.5:.1f}" text-anchor="end" '
            f'class="tick">{v:.1f}</text>'
        )
    for i in range(n + 1):
        parts.append(
            f'<text x="{_x(i, n):.1f}" y="{PANEL_H - M_B + 16}" text-anchor="middle" '
            f'class="tick">{i}</text>'
        )
    parts.append(
        f'<line x1="{M_L}" y1="{_y(0):.1f}" x2="{PANEL_W - M_R}" y2="{_y(0):.1f}" '
        f'stroke="var(--axis)" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="{(M_L + PANEL_W - M_R) / 2:.0f}" y="{PANEL_H - 4}" '
        f'text-anchor="middle" class="axis-title">GEPA iteration</text>'
    )

    ends = []
    for si, run in enumerate(runs):
        col = f"var({SERIES[si]})"
        pts = [(_x(it["i"], n), _y(val(it["best_so_far"]))) for it in run["iterations"]]
        d = " ".join(("M" if k == 0 else "L") + f"{x:.1f},{y:.1f}" for k, (x, y) in enumerate(pts))
        parts.append(
            f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )

        for it in run["iterations"]:
            if it["candidate_score"] is None or it["i"] == 0:
                continue
            cx, cy = _x(it["i"], n), _y(val(it["candidate_score"]))
            kept = it["candidate_score"] >= run["base"]
            tip = (
                f'{run["arm"]} · iteration {it["i"]} · candidate {it["candidate_index"]}'
                f' · scored {it["candidate_score"]:.4f} on the five held-out questions'
                f' · {"kept as new best" if kept else "evaluated, not better than base"}'
            )
            # 2px surface ring keeps overlapping marks separable.
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" fill="{col}" '
                f'stroke="var(--surface-1)" stroke-width="2" class="dot" '
                f'data-tip="{escape(tip)}"><title>{escape(tip)}</title></circle>'
            )

        last = run["iterations"][-1]
        ends.append({
            "y": _y(val(last["best_so_far"])),
            "x": _x(last["i"], n) + 7,
            "text": run["arm"],
            "col": col,
        })

    for lab in _declutter(ends):
        parts.append(
            f'<text x="{lab["x"]:.1f}" y="{lab["y"] + 3.5:.1f}" '
            f'class="endlabel" fill="{lab["col"]}">{escape(lab["text"])}</text>'
        )

    parts.append("</svg>")
    return (
        f'<figure class="panel-fig"><figcaption><b>{escape(title)}</b>'
        f'<span>{escape(subtitle)}</span></figcaption>{"".join(parts)}</figure>'
    )


def candidate_loss_panel(points: list[dict], *, baseline_loss: float | None,
                         best_idx: int | None, title: str, subtitle: str) -> str:
    """Every candidate GEPA proposed, not just the best-so-far line.

    Unlike line_panel (iteration on the x-axis, one run's best-so-far only),
    this scatters every candidate's loss (1 - val score) against the actual
    cumulative evaluation count it was discovered at -- the unit the paper's
    own trajectory figures use, and the one --budget/max_metric_calls share
    -- with the best-so-far step line traced through them and the baseline
    drawn as a horizontal reference. Loss=0 (perfect) plots at the bottom and
    loss=1 (worst) at the top, the same convention line_panel(invert=True)
    already uses, so the line moving down reads as "getting better" in both.
    """
    max_evals = max((p["evaluations"] or 0) for p in points) if points else 1
    max_evals = max_evals or 1
    parts = [
        f'<svg viewBox="0 0 {PANEL_W} {PANEL_H}" role="img" '
        f'aria-label="{escape(title)}. {escape(subtitle)}" class="panel">'
    ]

    for t in range(6):
        v = t / 5
        y = _y(v)
        parts.append(
            f'<line x1="{M_L}" y1="{y:.1f}" x2="{PANEL_W - M_R}" y2="{y:.1f}" '
            f'stroke="var(--grid)" stroke-width="1"/>'
        )
        parts.append(f'<text x="{M_L - 8}" y="{y + 3.5:.1f}" text-anchor="end" class="tick">{v:.1f}</text>')
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        ev = round(max_evals * frac)
        x = M_L + (PANEL_W - M_L - M_R) * frac
        parts.append(f'<text x="{x:.1f}" y="{PANEL_H - M_B + 16}" text-anchor="middle" class="tick">{ev}</text>')
    parts.append(
        f'<line x1="{M_L}" y1="{_y(0):.1f}" x2="{PANEL_W - M_R}" y2="{_y(0):.1f}" '
        f'stroke="var(--axis)" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="{(M_L + PANEL_W - M_R) / 2:.0f}" y="{PANEL_H - 4}" '
        f'text-anchor="middle" class="axis-title">Cumulative evaluations</text>'
    )

    def xf(evals: int | None) -> float:
        return M_L + (PANEL_W - M_L - M_R) * ((evals or 0) / max_evals)

    if baseline_loss is not None:
        by = _y(baseline_loss)
        parts.append(
            f'<line x1="{M_L}" y1="{by:.1f}" x2="{PANEL_W - M_R}" y2="{by:.1f}" '
            f'stroke="var(--series-2)" stroke-width="1.5" stroke-dasharray="4 3"/>'
        )
        parts.append(
            f'<text x="{PANEL_W - M_R + 5:.1f}" y="{by + 3.5:.1f}" '
            f'class="endlabel" fill="var(--series-2)">baseline</text>'
        )

    # Best-so-far step line through every candidate, in discovery order.
    step_pts = [(xf(p["evaluations"]), _y(p["best_so_far"])) for p in points]
    if step_pts:
        d = " ".join(("M" if k == 0 else "L") + f"{x:.1f},{y:.1f}" for k, (x, y) in enumerate(step_pts))
        parts.append(
            f'<path d="{d}" fill="none" stroke="var(--series-1)" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )

    # Every candidate as its own point -- not just the ones that improved.
    for p in points:
        cx, cy = xf(p["evaluations"]), _y(p["loss"])
        is_best = p["candidate"] == best_idx
        tip = (
            f'Candidate {p["candidate"]} · {p["evaluations"]} evaluations so far'
            f' · loss {p["loss"]:.4f}' + (" · BEST" if is_best else "")
        )
        r = 5.5 if is_best else 3.5
        fill = "var(--series-3)" if is_best else "var(--series-1)"
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" '
            f'stroke="var(--surface-1)" stroke-width="2" class="dot" '
            f'data-tip="{escape(tip)}"><title>{escape(tip)}</title></circle>'
        )

    parts.append("</svg>")
    return (
        f'<figure class="panel-fig"><figcaption><b>{escape(title)}</b>'
        f'<span>{escape(subtitle)}</span></figcaption>{"".join(parts)}</figure>'
    )


def pass_rate_duration_bars(before: dict, after: dict | None, *,
                            before_label: str = "Model before",
                            after_label: str = "Model + learned skill after") -> str:
    """Two small grouped bar charts: pass rate (%) and mean duration (s).

    Separate charts rather than one dual-axis chart, so percentages and
    seconds each get an axis that reads at face value -- matches the
    paper's own Figure 2 shape (pass rate + avg duration, per configuration).
    `after` is None when the run wasn't executed with --keep-runs, in which
    case this renders the "before" bar alone and says why the other is
    missing rather than inventing a number.
    """
    rows = [(before_label, before)]
    if after is not None:
        rows.append((after_label, after))

    def bar_group(get_value, *, fmt, axis_label, max_value) -> str:
        h = 60 * len(rows) + 30
        parts = [f'<svg viewBox="0 0 {BAR_W} {h}" role="img" aria-label="{escape(axis_label)}" class="panel wide">']
        span = BAR_W - BAR_L - BAR_R - 140
        for i, (label, data) in enumerate(rows):
            y = 14 + i * 60
            value = get_value(data)
            w = span * (value / max_value) if max_value else 0
            parts.append(f'<text x="0" y="{y + 14}" class="rowlabel">{escape(label)}</text>')
            parts.append(
                f'<rect x="140" y="{y}" width="{max(w, 2):.1f}" height="26" rx="4" '
                f'fill="var(--series-1)" class="dot" data-tip="{escape(label)}: {fmt(value)}"/>'
            )
            parts.append(f'<text x="{150 + w:.1f}" y="{y + 18}" class="endval">{fmt(value)}</text>')
        parts.append("</svg>")
        return "".join(parts)

    pass_rate_svg = bar_group(
        lambda d: 100 * d["pass_rate"], fmt=lambda v: f"{v:.1f}%",
        axis_label="Pass rate", max_value=100,
    )
    max_duration = max(d["mean_duration_s"] for _, d in rows) or 1
    duration_svg = bar_group(
        lambda d: d["mean_duration_s"], fmt=lambda v: f"{v:.0f}s",
        axis_label="Average duration", max_value=max_duration * 1.15,
    )

    missing_note = "" if after is not None else (
        '<p class="note">No "after" data yet -- rerun the optimizer with '
        '<code>--keep-runs</code> to keep the attempts this needs.</p>'
    )
    return (
        f'<div class="grid">'
        f'<figure class="panel-fig"><figcaption><b>Pass rate</b>'
        f'<span>share of kept attempts that completed</span></figcaption>{pass_rate_svg}</figure>'
        f'<figure class="panel-fig"><figcaption><b>Average duration</b>'
        f'<span>mean resolution time, seconds</span></figcaption>{duration_svg}</figure>'
        f'</div>{missing_note}'
    )


def paired_bars(rows: list[dict]) -> str:
    """Before/after as two bars per experiment, each row scaled to its own peak.

    A single shared axis let Exp 4's 25 dwarf Exp 2's 2 -- both are complete
    fixes, but only one was visible. Scaling each row independently makes
    every experiment's own drop legible regardless of its absolute size; the
    raw counts (still the thing that matters, not a %) stay as text on the
    bars themselves and in the table below.
    """
    parts = []
    for r in rows:
        peak = max(r["before"], r["after"], 1)
        before_w = 100 * r["before"] / peak
        after_w = 100 * r["after"] / peak
        drop = 100 * (r["before"] - r["after"]) / r["before"] if r["before"] else 0
        arm = r.get("arm")
        sub = f'{arm} &middot; {r["subtype"]} &middot; n={r["attempts"]}' if arm else \
            f'{r["subtype"]} &middot; n={r["attempts"]}'
        parts.append(f"""<div class="pbar-row">
<div class="pbar-label"><b>{escape(r["label"])}</b><span class="rowsub">{sub}</span></div>
<div class="pbar-track">
<div class="pbar-line"><div class="pbar-wrap"><div class="pbar-bar before" style="width:{before_w:.1f}%"></div></div><span class="pbar-val">{r["before"]}</span></div>
<div class="pbar-line"><div class="pbar-wrap"><div class="pbar-bar after" style="width:{after_w:.1f}%"></div></div><span class="pbar-val">{r["after"]}</span></div>
</div>
<div class="pbar-delta">&minus;{drop:.0f}%</div>
</div>""")
    return f'<div class="pbars">{"".join(parts)}</div>'


BAR_W, BAR_H, BAR_L, BAR_R = 640, 46, 4, 4


def stacked_bar(segments: list[dict], *, label: str, pct_of: float | None = None) -> str:
    """One horizontal bar split into named parts.

    Used for the baseline composition, where the question is "what share of
    this whole is each part", not "how did this change over time". Each segment
    carries its own tooltip; names live in a legend below (see `bar_legend`),
    not as in-bar text -- narrow segments have no room for a label without
    colliding with their neighbours.

    `pct_of` overrides the denominator used for the displayed percentage --
    e.g. a sub-breakdown of a 60-point bucket inside a 100-point total should
    report each part's share of 100, not of 60, so it reads consistently
    against the other bar on the same page and the parts don't visibly fail
    to sum to 100% from rounding.
    """
    total = sum(s["value"] for s in segments)
    pct_base = pct_of if pct_of is not None else total
    span = BAR_W - BAR_L - BAR_R
    parts = [
        f'<svg viewBox="0 0 {BAR_W} {BAR_H}" role="img" '
        f'aria-label="{escape(label)}" class="panel wide">'
    ]
    x = BAR_L
    for i, s in enumerate(segments):
        w = span * s["value"] / total
        fill = s.get("fill", f"var(--series-{(i % 3) + 1})")
        tip = f'{s["name"]}: {s["value"]} of {pct_base:g} ({100 * s["value"] / pct_base:.0f}%)'
        parts.append(
            f'<rect x="{x:.1f}" y="6" width="{max(w - 1.5, 0.5):.1f}" height="{BAR_H - 14}" '
            f'rx="2" fill="{fill}" class="dot" data-tip="{escape(tip)}"/>'
        )
        x += w
    parts.append("</svg>")
    return "".join(parts)


def bar_legend(segments: list[dict], *, pct_of: float | None = None) -> str:
    """HTML legend below a stacked bar: one swatch + name + share per segment.

    Keeps labels out of the SVG entirely, so the legend wraps with ordinary
    flexbox instead of needing manual x-position math that breaks on narrow
    segments. `pct_of` matches the same override on `stacked_bar` -- pass the
    same value to both so the bar and its legend agree.
    """
    total = sum(s["value"] for s in segments)
    pct_base = pct_of if pct_of is not None else total
    # Percentage only; the exact value is still on the bar's hover tooltip.
    items = "".join(
        f'<span><i class="sw dot-sw" style="background:{s.get("fill", "var(--series-1)")}"></i>'
        f'{escape(s["name"])} <span style="color:var(--muted)">'
        f'({100 * s["value"] / pct_base:.0f}%)</span></span>'
        for s in segments
    )
    return f'<div class="legend">{items}</div>'


# ---------------------------------------------------------------------------
# Agent traces -- what actually happened on individual attempts: the
# commands run, the reasoning around them, and the judge's verdict. Colored
# by outcome throughout (pass/fail, call ok/BAD, judge matched/partial/
# deviated) so status reads at a glance rather than only in the tooltip text.
# ---------------------------------------------------------------------------

_PASS_COLOR = "#1baf7a"     # green
_FAIL_COLOR = "#e0475a"     # red
_PARTIAL_COLOR = "#e0a030"  # amber

_VERDICT_COLOR = {"matched": _PASS_COLOR, "partial": _PARTIAL_COLOR, "deviated": _FAIL_COLOR}


def attempt_trace_card(record) -> str:
    """One attempt as a collapsible card: outcome, calls, reasoning trace,
    judge verdict. `record` is an agenteval.contract.Record2.
    """
    border = _PASS_COLOR if record.completed else _FAIL_COLOR
    status = "completed" if record.completed else "did not complete"
    score_text = f'score {record.score:.3f}' if record.score is not None else "score n/a"
    duration_text = f'{record.duration_ms / 1000:.0f}s' if record.duration_ms else "? s"

    calls_html = "".join(_call_row(c) for c in record.calls) or (
        '<div class="trace-empty">(no calls at all)</div>'
    )

    judge_html = ""
    if record.route_judge:
        rj = record.route_judge
        color = _VERDICT_COLOR.get(rj.get("verdict"), "var(--muted)")
        judge_html = (
            f'<div class="trace-judge" style="border-left-color:{color}">'
            f'<span class="trace-badge" style="background:{color}">{escape(str(rj.get("verdict")))}</span>'
            f'<span class="trace-judge-score">{rj.get("adherence", 0):.2f} adherence</span>'
            f'<p>{escape(str(rj.get("rationale", "")))}</p></div>'
        )

    reasoning_html = "".join(_reasoning_row(r) for r in record.reasoning_trace)
    reasoning_section = (
        f'<details class="trace-reasoning"><summary>Reasoning trace '
        f'({len(record.reasoning_trace)} events)</summary>{reasoning_html}</details>'
        if record.reasoning_trace else ""
    )

    return f"""<details class="trace-card" style="border-left-color:{border}">
<summary>
  <span class="trace-badge" style="background:{border}">{escape(status)}</span>
  <b>{escape(record.question_id)}</b>
  <span class="trace-meta">{escape(score_text)} &middot; {escape(duration_text)} &middot; ${record.cost_usd:.2f}</span>
</summary>
<p class="trace-question">{escape(record.question)}</p>
<div class="trace-calls">{calls_html}</div>
{judge_html}
{reasoning_section}
</details>"""


def _call_row(call: dict) -> str:
    ok = call.get("class") is None
    color = _PASS_COLOR if ok else _FAIL_COLOR
    argv = " ".join(str(a) for a in (call.get("argv") or []))
    err = (call.get("stderr_head") or "").strip()
    err_html = f'<div class="trace-err">{escape(err[:300])}</div>' if err and not ok else ""
    return (
        f'<div class="trace-call">'
        f'<span class="trace-dot" style="background:{color}"></span>'
        f'<code>botmap {escape(argv)}</code>'
        f'<span class="trace-meta">exit {call.get("exit_code")}</span>'
        f'{err_html}</div>'
    )


def _reasoning_row(event: dict) -> str:
    kind = event.get("type")
    if kind == "tool_use":
        try:
            input_text = json.dumps(event.get("input"))
        except TypeError:
            input_text = str(event.get("input") or "")
        text = f'{event.get("name")}({input_text[:200]})'
        return f'<div class="trace-event trace-event-tool">{escape(text)}</div>'
    if kind == "tool_result":
        return f'<div class="trace-event trace-event-result">{escape((event.get("content") or "")[:300])}</div>'
    if kind == "thinking":
        return f'<div class="trace-event trace-event-thinking">{escape((event.get("text") or "")[:300])}</div>'
    return f'<div class="trace-event trace-event-text">{escape((event.get("text") or "")[:300])}</div>'


def attempt_traces_section(records: list, *, title: str) -> str:
    if not records:
        return f'<p class="note">No {escape(title.lower())} kept yet.</p>'
    cards = "".join(attempt_trace_card(r) for r in records)
    return f'<div class="trace-list">{cards}</div>'


# Extra CSS for the trace cards above -- not part of build_figures.py's
# STYLE, since that's specifically the historical report's stylesheet and
# these components only exist in run_report.py's live progress page.
TRACE_STYLE = """
.trace-list { display: flex; flex-direction: column; gap: 8px; margin: 10px 0; }
.trace-card { background: var(--surface-1); border: 1px solid var(--border); border-left: 4px solid; border-radius: 8px; padding: 10px 14px; }
.trace-card summary { cursor: pointer; display: flex; align-items: center; gap: 10px; color: var(--text-primary); font-size: 13px; }
.trace-badge { color: #fff; font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .03em; padding: 2px 8px; border-radius: 10px; }
.trace-meta { color: var(--muted); font-size: 12px; margin-left: auto; }
.trace-question { color: var(--text-secondary); font-size: 12.5px; margin: 8px 0; font-style: italic; }
.trace-calls { display: flex; flex-direction: column; gap: 4px; margin: 8px 0; }
.trace-call { display: flex; align-items: center; gap: 8px; font-size: 12px; flex-wrap: wrap; }
.trace-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.trace-err { flex-basis: 100%; color: #e0475a; font-size: 11.5px; margin-left: 16px; }
.trace-empty { color: var(--muted); font-size: 12.5px; font-style: italic; }
.trace-judge { border-left: 3px solid; padding: 6px 10px; margin: 8px 0; background: var(--page); border-radius: 0 6px 6px 0; }
.trace-judge-score { color: var(--muted); font-size: 12px; margin-left: 8px; }
.trace-judge p { margin: 4px 0 0; font-size: 12.5px; color: var(--text-secondary); }
.trace-reasoning summary { color: var(--text-secondary); font-size: 12px; margin-top: 6px; }
.trace-event { font-size: 11.5px; padding: 4px 8px; margin: 3px 0 3px 12px; border-radius: 4px; }
.trace-event-tool { background: rgba(42,120,214,.12); color: var(--series-1); font-family: ui-monospace, monospace; }
.trace-event-result { background: rgba(27,175,122,.12); color: var(--series-3); font-family: ui-monospace, monospace; }
.trace-event-thinking { color: var(--muted); font-style: italic; }
.trace-event-text { color: var(--text-secondary); }
"""
