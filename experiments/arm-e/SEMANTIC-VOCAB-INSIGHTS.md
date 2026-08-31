# Arm E — semantic / regional vocabulary skill instruction

**Verdict: rejected.** The instruction did not reduce the failure class it targets.
It left `c-vocabulary` unchanged where it already occurred and *introduced* one new
occurrence where the control had none.

Date: 2026-08-31. Model: claude-sonnet-5. Question bank: `experiments/questions.yaml`.

---

## 1. What changed

One commit, prompt-only, no code:

- Branch `cand/categories-search-semantic-skill` @ **f93a7d2**
- Worktree `/Users/priyangapkini/workspace/ar-search-semantic/botmap`
- Base: `cand/categories-search` @ **4a197c3** (the `categories --search TEXT` candidate)
- Diff: `botmap/data/skill.md` only, +24 lines

The addition tells the agent that `--search` is a substring match over the vocabulary
Overture actually uses, that it should restate the question's concept as short generic
English stems and try them one at a time before concluding a category is absent, and
gives a five-row example table (chemist→pharmacy/drug, petrol pump→gas/station/fuel,
cycle parking→bike/bicycle/parking, bus stand→bus/station/transit/stop,
EV charger→ev/charging/charger).

Also added to the bank: **`petrol-pumps-cambridge`** ("How many petrol pumps are there
in Cambridge, Massachusetts?"), tier 2. Chosen because `petrol` shares no substring with
Overture's `gas_station`, so `--search petrol` provably returns nothing — substring search
on the question's own wording cannot succeed. This is the sharpest available test of
semantic mapping. It has no baseline, so it was run on both arms.

## 2. Run dirs and cost

| Run dir | Arm | Attempts | Cost |
|---|---|---|---|
| `experiments/runs/arm-e-semantic-vocab-f93a7d2` | treatment f93a7d2 | 5 | $3.36 |
| `experiments/runs/arm-e-semantic-vocab-repairs-f93a7d2` | treatment f93a7d2 | 4 | $0.82 |
| `experiments/runs/arm-e-petrol-control-4a197c3` | control 4a197c3 | 1 | $0.21 |
| `experiments/runs/arm-e-categories-search-c-truncated-4a197c3` | control 4a197c3 | 13 | $3.77 (pre-existing) |

**Spend for this experiment: $4.39 / 10 attempts.** The 13-attempt control run was already
in flight when this work began and is reused as the comparison arm.

Supporting artifacts, all under `experiments/arm-e/`: `semantic-vocab-subset.json`,
`semantic-vocab-repairs-subset.json`, `petrol-control-subset.json`,
`petrol-vocab-subset.json`, `compare_semantic_vocab.py`, `semantic-vocab-comparison.json`,
and the three run logs.

## 3. Did agents use `--search`?

Yes on both arms, unprompted. The control — which has only the basic "prefer `--search`
before concluding absence" note from 4a197c3 — used it on 11 of 13 attempts.

The one place the treatment *stopped* using it is notable: on `asian-restaurants-rollup`
it issued **zero** `--search` calls and instead ran `categories --top 980` three times,
enumerating the whole vocabulary. 20 calls versus the control's 3, and it earned a
`c-truncated` failure the control did not have. The instruction pushed that attempt off
the mechanism the instruction is about.

## 4. Did agents try semantic / regional terms?

**The control already did, without being told.** This is the finding that undercuts the
whole premise:

| Attempt | Control terms (no semantic note) |
|---|---|
| `basic-category-rollup` | `pharmacy`, `drug` |
| `bike-parking-coverage` | `bike`, `bicycle` |
| `bus-stops-cambridge` | `bus`, `stop`, `transit`, `station` |
| `bus-stops-with-coffee` | `bus`, `transit`, `coffee`, `stop`, `station`, `platform` |
| `ev-charging-gap` | `charg` (a well-chosen stem) |

These are close to the exact term sets the new note prescribes.

The treatment did widen exploration on two attempts, reaching genuinely regional wording:

| Attempt | Control | Treatment |
|---|---|---|
| `bike-parking-coverage` | `bike, bicycle` (2) | `bike, bicycle, parking, rack, stand, dock` (6) |
| `bus-stops-with-coffee` | 6 terms | 12 terms, incl. `halt`, `shelter`, `mta`, `public_transport` |

`stand` and `halt` are precisely the regional forms the brief named. So the instruction
is *followed*. It just does not help.

### The petrol result

The clearest single comparison. Treatment followed the note's petrol row verbatim:

```
categories --search gas ; --search fuel ; --search station
count --where categories.primary=gas_station
```

Control skipped discovery entirely and hit the answer on its second call:

```
count --where categories.primary=gas_station
```

Both got the same answer; the control took fewer calls. The model already knows
petrol pump = gas station and applies that mapping *before* reaching for a tool. On the
hardest case in the design — where substring search provably cannot work — the
instruction was unnecessary.

Note also that the treatment's three terms are literally the table row. The brief asked to
avoid hardcoding a synonym map in code so the LLM could do the mapping itself. A synonym
table in the prompt is the same coupling relocated from `cli.py` to `skill.md`; the agent
looked the terms up rather than reasoning to them.

## 5. Target failure movement

`c-vocabulary` — querying a `categories.primary` value that does not exist in the area —
is the class this instruction targets.

| Question | Control | Treatment | Movement |
|---|---|---|---|
| `bus-stops-cambridge` | r1 ✗, r2 ✗ (2/2) | r2 ✗ (1/1) | **none** |
| `bike-parking-coverage` | r1 ✓, r2 ✓ (0/2) | r2 ✗ (1/1) | **regression** |

Run-wide: control 2 occurrences in 13 attempts; treatment 2 in 9.

**Why it fails.** On `bus-stops-cambridge` the treatment searched `bus, transit, stop,
station` and then queried `categories.primary=bus_stop` anyway — a value its own search
had just shown is absent from all 980 category values. The agent discovers the vocabulary
correctly and then ignores the result. The failure is not in *finding* terms; it is in
*acting on what the search returned*. The instruction improves a step that was not broken.

**Why it regresses.** On `bike-parking-coverage` the broadened brainstorm (`rack`, `stand`,
`dock`) led the agent to try `bicycle_parking`, a plausible-sounding value that does not
exist — creating a `c-vocabulary` failure the control never had. Prompting for more
candidate vocabulary increases the number of guesses at absent categories.

**Context that limits the headroom:** the `--search` feature alone (4a197c3, no semantic
note) already cut `c-truncated` from 25 failures across the baseline subset to **1** across
the control's whole 13-attempt run. The feature did the work; there was almost nothing left
for the instruction to claim.

## 6. Caveats

1. **Small n.** 10 attempts, one repeat per cell. Every per-question comparison rests on
   1–2 attempts per arm. Directional at best.

2. **Three of the five original treatment attempts made zero botmap calls.** The agent
   answered `basic-category-rollup` from memory and pulled `bike-parking-coverage` and
   `bus-stops-cambridge` off the web (Cambridge GIS, MBTA API). All three were re-run and
   engaged normally, so this was drift, not the edit — and in two of them the agent never
   loaded the skill at all, whose frontmatter is byte-identical to the control's. Root
   cause not established.

3. **The runner scores zero-call attempts as `ok=true`.** The first treatment run reported
   `ok=5/5` when only 2 attempts used the CLI. Raw failure totals are also biased by this:
   a zero-call attempt contributes zero failures, making an arm look better for free. Any
   Arm E summary built on `ok` counts will overstate success wherever the agent skipped the
   tool. Worth fixing independently of this experiment.

4. **The bank cannot test the regional half of the instruction.** Every question uses
   US-standard English — "drugstores and pharmacies", "bike parking", "bus stops". None
   says chemist, medical store, bus stand, or cycle stand. Only the semantic-expansion half
   was exercised. `petrol-pumps-cambridge` was added to close part of this gap; the other
   regional forms remain untested.

5. **Concurrency.** The treatment ran alongside the control run. No mechanism links this to
   agent behaviour, but timing figures are not clean.

## 7. Recommendation

Do not merge f93a7d2. The instruction is followed faithfully and buys nothing: the model
already performs semantic mapping natively (petrol → `gas_station` with no search at all),
the control already probes multiple related terms unprompted, and broadening the brainstorm
increased guesses at non-existent categories.

If `c-vocabulary` is worth attacking, target the step that actually fails: the agent
querying a category value that its own `--search` just reported as absent. That is a
tool-side affordance — for example, having `count`/`places` fail loudly with the near-miss
vocabulary when a `categories.primary` value matches nothing in the area — not a prompt
instruction telling the model to think of more words.
