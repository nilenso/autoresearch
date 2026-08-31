# Figures

Charts for [`../agent-friendly-cli-paper.md`](../agent-friendly-cli-paper.md).

## View it

GitHub renders a committed `.html` file as source, not as a page. To see the
charts, open it through htmlpreview:

<https://htmlpreview.github.io/?https://github.com/nilenso/autoresearch/blob/main/docs/figures/gepa-trajectories.html>

Or clone and open `docs/figures/gepa-trajectories.html` directly — the page is
self-contained, with no external scripts, styles, or fonts.

## What is in it

The page opens with **Evaluator design** — the tool, the task, the failure
taxonomy (classes A–F plus class-C subtypes), and the scoring rubric as two bar
charts: the top-level 60/20/20 split, and how the 60 correctness points divide
into 5 scoring components (final outcome, self-recovery, guidance, route,
attribution). Failure-class severity only feeds into the 2-point attribution
slice — it does not otherwise split the 60%. A full glossary of the terms used
on the page is collapsed behind a `<details>` toggle further down.

| Figure | Shows |
|---|---|
| 0 | The baseline at commit `3009509`: 500 classified calls split by failure class, then the 55 class-C calls split by subtype. Establishes that half of all failures are silent. |
| 1 | GEPA best-so-far held-out loss (`1 − score`) per iteration, for Arm B, Arm C, and the narrow 4-file tool run. |
| 2 | All six arms/runs at a glance, as short cards with a trace and/or arm-report link each, followed by (2b) the four paired experiments as before → after failure instances on matched attempt subsets, each labelled with the arm that produced it. Exp 3 is Arm D, Exp 4 is Arm E. |

Below the figures, **Reading across the arms** is organized as short bullet
lists rather than prose: why the two GEPA arms barely moved, what actually
improved, what this round got wrong, what to change in the next run, and what
the study is not entitled to claim. A **Traces & runs** table near the bottom
links every run mentioned on the page to its trace on the
[Hugging Face dataset](https://huggingface.co/datasets/nilenso/autoresearch);
runs added after the 2026-08-25 HF publish (the narrow tool-run and Arm E) are
marked "not yet published" instead of guessing at a URL. Terms defined in the
glossary include the three different 60s in this study, which are easy to
confuse:

- the optimizer budget is **60 evaluations** (the runs spent 61–63), not 60 iterations;
- each run took only **8–9 iterations**, because one iteration costs several evaluations;
- the baseline is **60 attempts**, which is 30 questions run twice (`REPEATS = 2`), not 60 questions.

The two figures use different axes on purpose. The GEPA arms are optimizers with
an iteration axis; the paired arms are single interventions measured once, whose
outcome is a count of failure instances rather than a score. Drawing the second
group as a line would mean inventing an x-axis they do not have.

**The three runs share one fixed validation set.** `questions.split()` is
deterministic — every Nth question after sorting by id, stratified by tier — so all
three held out the same five questions (`hardware-near-bikepaths`,
`pharmacies-monaco`, `street-canonical-form`, `unsupported-hours-and-ratings`,
`which-admin-areas`). The split is recorded per run as `heldout_questions` in each
`summary.json`; the `val_questions` key beside it is vestigial and always empty.

That makes the gap between the three starting points meaningful. Same commit, same
five questions, and the base scores still range from 0.5764 to 0.7637 — a spread of
**0.187** that comes from nothing but run-to-run variance in agent behaviour and
environment. That is 31× Arm C's +0.006 and 12× the narrow tool run's +0.016, so
neither optimizer "win" is separable from noise. Read the curves for their shape,
not their height.

## Rebuilding

```bash
python3 tools/figures/build_figures.py
```

This works anywhere. Where `experiments/runs/` is present the numbers are
re-extracted from the raw artifacts; where it is not, the build falls back to the
committed `figure-data.json` and says so. That directory is gitignored — 384MB of
raw command stdout, including one 221MB GeoJSON dump, which GitHub would reject
outright — so the fallback is the normal path for everyone except the machine that
produced the runs.

The fallback can only change layout and prose. Every plotted value comes from
`figure-data.json`, so no rebuild can silently alter a measurement; changing a
number requires the raw runs.
