"""Draws the figures as inline SVG. No plotting library, no build step.

Colors are the validated default palette from the data-viz reference, kept as
CSS custom properties so light and dark swap in one place. The three-series
categorical set clears every all-pairs gate in both modes; aqua sits below 3:1
on the light surface, which is why every line carries a direct label and every
figure ships a table view.
"""

from __future__ import annotations

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
