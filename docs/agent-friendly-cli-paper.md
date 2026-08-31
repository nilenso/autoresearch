# What Makes a Command-Line Interface Agent-Friendly?

*A multi-arm empirical study deriving design principles from AI-agent traces*

**Priyanga P. Kini** · nilenso · August 2026

## Abstract

Command-line interfaces are increasingly used by AI coding agents as operational tools. Yet most CLIs are designed for humans: terse output, implicit defaults, silent truncation, and documentation that assumes background judgment. This paper studies what makes a CLI friendly to AI agents using `botmap`, a command-line interface over Overture map data, as a testbed. The study ran five arms: an agent-led research loop, a prompt-only optimizer, a full-repository code optimizer, a taxonomy-driven targeted-experiment arm, and a failure-routed design arm. The intended output was not a single winning patch but a set of empirically grounded design principles. To support this, we built an evaluator that records agent/tool interactions, classifies failures, probes silent wrong answers, and scores correctness, recoverability, token efficiency, and wall-clock time.

In a 60-attempt baseline, the dominant failures were not crashes or parse errors but *silent wrongness*: successful commands that led the agent to false conclusions. Class C (silent wrong) accounted for 55 of the 111 classified failures. We then ran four paired before/after experiments, each changing one tool behavior and measuring one failure subtype on a matched subset. Warning when category listings were truncated cut truncation failures from 13 to 5. Naming the correct field when a value was queried in the wrong one cut wrong-column failures from 2 to 0. Naming the correct resource type cut wrong-type failures from 3 to 0, with completion caveats. The strongest result came from adding a searchable vocabulary primitive, `botmap categories --search TERM`, which cut truncation failures from 25 to 1 across every baseline attempt that exhibited them.

These results support a general thesis: an agent-friendly CLI makes interpretation, completeness, uncertainty, and recovery paths explicit. The CLI should not merely expose functions; it should expose enough state for an agent to repair its next command.

## 1. Introduction

AI agents increasingly operate through shells. They inspect files, run tests, call cloud CLIs, query databases, and compose tools whose designers expected human operators. This changes the usability problem. A human sees a suspiciously short list or an unexpected zero and may ask, "is this complete?" An agent often treats that same output as evidence and continues confidently.

This paper asks:

> What makes a command-line interface agent-friendly?

We investigate the question with `botmap`, a CLI for querying Overture map data. The user gives an AI agent a natural-language map question, such as "How many hospitals are there in Rhode Island?", and the agent must discover and run appropriate `botmap` commands. The core task is not whether `botmap` contains correct data. It is whether an AI agent can find, choose, and trust the right command sequence unaided.

Our central finding is that agent-hostile CLIs fail quietly. The most dangerous failure is not a crash. It is a successful command that returns a plausible but incomplete or misleading result: a capped category list, an unexplained zero, or a value queried in the wrong field. Agent-friendly CLI design is therefore largely recovery design. The CLI must expose enough interpretation and diagnostic information for the agent to correct itself.

### 1.1 Why arms rather than one optimization run

The experiment was deliberately organized around *arms* rather than a single linear optimization run. Each arm represents a different hypothesis about where an agent-friendly interface comes from:

- **Arm A — loop-as-a-skill.** Have an agent follow an explicit research loop, proposing and screening candidate CLI improvements itself.
- **Arm B — prompt lever.** Optimize only the agent-facing instructions, leaving the CLI untouched.
- **Arm C — full-repo lever.** Give the optimizer broad repository context and broad tool-edit permissions, while keeping the evaluator read-only.
- **Arm D — taxonomy-driven experiments.** Turn the measured failure taxonomy into the next targeted paired experiments.
- **Arm E — failure-class routing.** Route each candidate only to the attempts whose failure subtype its mechanism could plausibly fix, instead of screening every candidate across the whole question bank.

Arms B and C used **GEPA** (Genetic-Pareto), a reflective optimizer that proposes candidate edits, evaluates them against a held-out set, reads the resulting traces, and keeps a Pareto frontier of the best performers rather than a single best score [1]. Arms A, D, and E were agent-led or orchestrated rather than GEPA-driven. The arms are best understood as evidence-generating probes, not as contestants where the highest aggregate score decides the conclusion.

### 1.2 Contributions

1. A **failure taxonomy** for agent/CLI interaction that separates hard failures, guided failures, and silent wrongness, with subtypes that are individually actionable (§3.1).
2. An **evaluator** that detects silent wrong answers through differential probes and scores recoverability as a first-class metric, guarded by sabotage fixtures (§3).
3. A **baseline measurement** over 60 agent attempts showing that silent wrongness, not crashing, is the dominant failure mode (§4).
4. Four **paired before/after experiments** isolating single CLI behaviors against single failure subtypes (§5).
5. A **method comparison** across five arms showing that failure-class routing found a shippable affordance that neither GEPA arm produced (§6).
6. Seven **design principles** for agent-friendly CLIs, each traced to a measured failure mode and labelled with its evidence strength (§7).

### 1.3 Roadmap

§2 describes the tool and task. §3 describes the evaluator and the taxonomy it produces. §4 reports the baseline. §5 reports the four paired experiments; the candidates tested there came from the arms described in §6, which also reports what each arm did and did not produce. §7 states the principles, §8 credits each arm's contribution, and §9 contrasts human-friendly with agent-friendly design. §10 states threats to validity and §11 the next experiments.

## 2. Research setting

### 2.1 Tool under study

`botmap` is a command-line interface over Overture map data. It exposes commands for places, buildings, roads, administrative areas, and related geospatial entities. Typical operations include counting features, sampling data, resolving place names, and downloading filtered outputs.

This makes it a useful stress test for agent usability because it combines several common CLI challenges:

- multiple resource types;
- domain-specific vocabulary;
- structured filters;
- ambiguous place names;
- large outputs;
- expensive data operations;
- JSON and non-JSON output modes.

### 2.2 Agent task

For each question, the agent receives only a plain-English prompt and a shell. It must infer which commands to run. We record each command, its output, the final answer, token usage, wall-clock duration, and whether the attempt completed.

### 2.3 Why ordinary scoring was insufficient

The original scorer applied a single label per CLI call, derived from whether stderr looked like an error. That answers one question — *did this call error?* — and we were reading it as an answer to a different one — *did this go well?*

It got both directions wrong. It **punished the tool for being helpful**: when `count` found nothing and suggested `did you mean: bus_station?`, the helpful message was classified as an error, which also destroyed the agent's ability to demonstrate recovery. And it **rewarded the tool for being silent**: a query for a category that never existed printed `0`, exited 0, and wrote nothing to stderr, so it scored as a clean call even though the agent then reported a wrong answer.

A zero row count is not a clean answer. It is an *unverified* one. It can mean "there are genuinely none" or "you asked the wrong question and I won't tell you which." Separating those two meanings is what the rest of the method is built on, so we replaced the scorer with an evaluator centered on trace classification, differential probes, and recoverability.

## 3. Evaluator

The evaluator writes `record-v2` artifacts — per-attempt traces holding every command, its stdout and stderr, token counts, timings, the final answer, and the classification assigned to each call — for all retained attempts. It classifies outcomes at both the command level and the attempt level.

### 3.1 Failure taxonomy

We use the following classes:

| Class | Meaning | Example |
|---|---|---|
| A | Hard or unguided failure | usage error, raw traceback, no useful recovery |
| B | Guided/recoverable failure | command fails but gives a usable next step |
| C | Silent wrong | command succeeds or appears plausible but misleads the agent |
| D | Degenerate route | agent uses unnecessarily broad or expensive route |
| E | Environment/quota failure | excluded from CLI blame |
| F | Agent-side failure | e.g. ignored hint; recorded separately, not charged to CLI |

Class C is further subdivided. The important subtypes in this study were:

- `c-truncated`: a bounded list was treated as complete;
- `c-unknown`: an unexplained empty result whose reason probes could not establish;
- `c-wrong-type`: the filter worked under a different resource type;
- `c-wrong-column`: the value existed in another field.

### 3.2 Units used throughout this paper

Three units appear in the results and are easy to conflate:

| Unit | Meaning | Typical magnitude |
|---|---|---|
| **Attempt** | One agent run against one question, start to final answer | 60 in the baseline |
| **Call** | One `botmap` invocation inside an attempt | ~500 in the baseline |
| **Failure instance** | One call classified into a failure class or subtype | 111 in the baseline |

A single attempt can contain several failure instances of the same subtype, so subtype counts are always larger than the number of affected attempts. Every before/after figure in §5 counts **failure instances**, and each experiment names the attempt subset it was measured on.

### 3.3 Scoring rubric

The top-level score is:

| Component | Weight |
|---|---:|
| Correctness and recoverability | 60% |
| Token efficiency | 20% |
| Wall-clock time | 20% |

Correctness/recoverability is further split into final outcome correctness, self-recovery, guidance quality, route quality, and attribution. This reflects the premise that an agent-friendly CLI is not one that never errors; it is one that enables the agent to recover without human intervention.

### 3.4 Differential probes

When an apparently successful command returns a suspicious result, the evaluator may run CLI-only probes. For example, if `count -t infrastructure --where subtype=bicycle_parking` returns zero, the probe may test whether `class=bicycle_parking` returns rows. These probes turn otherwise invisible silent failures into auditable classifications.

### 3.5 Sabotage gate

The evaluator includes sabotage fixtures: known-bad examples for each failure class and subtype. If the evaluator cannot detect a failure it is meant to measure, optimizer runs are blocked from proceeding.

### 3.6 Instrumentation caveat

The evaluator itself can be wrong. During the experiment, an early entity probe confused US state abbreviations with ISO country codes: `Cambridge, MA` and `Malta, MT` were initially treated as possible country-code contradictions. Repairing that false positive changed the failure distribution. This became a methodological lesson: evaluator bugs can manufacture product insights.

## 4. Baseline measurement

We ran a baseline measurement on botmap commit `3009509`.

| Run | Attempts run | Completed | Botmap calls | Cost | Duration |
|---|---:|---:|---:|---:|---:|
| Baseline | 60 / 60 | 51 | 486 | $15.50 | 323.8 min |
| Retry incomplete | 9 / 9 | 2 | — | $0.31 | — |

The retry run preserved original artifacts and only supplied successful replacements for transient incomplete attempts, bringing the retained set to 60 attempts of which 53 completed.

After enrichment and repair, the combined baseline distribution was:

```json
{
  "records": 60,
  "attempts_with_failures": 34,
  "class_counts": {
    "clean": 389,
    "C": 55,
    "B": 15,
    "A": 38,
    "D": 3
  },
  "subtype_counts": {
    "c-truncated": 25,
    "c-unknown": 25,
    "c-wrong-type": 3,
    "c-wrong-column": 2
  }
}
```

Read this at call level: 500 classified calls across the 60 retained attempts — the baseline's 486 plus the calls contributed by the two replacement attempts. Of those, 389 were clean and 111 were failure instances, spread over 34 attempts.

The largest visible problem was Class C silent wrongness, at 55 of 111 failure instances. This matters because it means conventional "did the command fail?" evaluation would miss half the failures, and specifically the half most likely to produce confident wrong answers.

## 5. Paired experiments

We then ran targeted before/after experiments. Each experiment changed one tool behavior and compared a matched subset of questions against the baseline traces. The candidates came from the arms described in §6: Experiments 1 and 2 from the paired-experiment programme, Experiment 3 from Arm D, and Experiment 4 from Arm E.

All four interventions follow the same output contract: stdout stays machine-readable and unchanged, and the new guidance goes to stderr. This is what makes the changes safe to ship into a pipeline, and it is generalized as a principle in §7.4.

### 5.1 Experiment 1: never silently truncate output

**Hypothesis.** If a CLI returns a capped list, it should say the list is incomplete and name the recovery action.

**Failure targeted.** `c-truncated`.

**Change.** Candidate `00bff1a` changed `botmap categories` so that when `--top N` truncates the category list, the command emits a warning on stderr while preserving JSON stdout:

```text
[botmap] Showing top N of TOTAL categories. This list is truncated; rerun with
`--top TOTAL` or a larger --top before concluding a category is absent.
```

**Subset.** `bike-parking-coverage`, `basic-category-rollup`, `bus-stops-cambridge`, two repeats each — 6 attempts.

**Result.**

| Metric | Before | After |
|---|---:|---:|
| `c-truncated` instances | 13 | 5 |

Other failures remained, so the result does not prove full task success. It supports the narrower principle that silent truncation is agent-hostile and that explicit truncation warnings improve recovery.

### 5.2 Experiment 2: if a value exists elsewhere, say where

**Hypothesis.** If a query returns zero because a value was used in the wrong field, the CLI should name the correct field.

**Failure targeted.** `c-wrong-column`.

**Change.** Candidate `7c794ff` changed `botmap count`: when `class=X` or `subtype=X` returns zero, it tests the paired field. If the paired field has rows, stderr names the correction:

```text
[botmap] 0 rows for subtype='bicycle_parking', but class='bicycle_parking'
returns 1,844. Try `--where class=bicycle_parking` before concluding none exist.
```

**Subset.** `bike-parking-coverage`, `residential-share-cambridge`, two repeats each — 4 attempts.

**Result.**

| Metric | Before | After |
|---|---:|---:|
| `c-wrong-column` instances | 2 | 0 |

This confirms the principle only in its narrow form — that a zero caused by a *known adjacent field* should name that field. It does not show that zero-result diagnostics in general are safe or sufficient, and the baseline count was small.

### 5.3 Experiment 3: if the same filter works under another type, name the type

**Hypothesis.** If the same filter returns rows under a different resource type, the CLI should name that type and give the retry command.

**Failure targeted.** `c-wrong-type`.

**Change.** Arm D candidate `9ba1187` added a wrong-type hint for zero counts, following the same stdout/stderr contract as Experiments 1 and 2.

**Subset.** `beach-accessibility-malta`, `residential-share-cambridge`, two repeats each — 4 attempts.

**Result.**

| Metric | Before | After |
|---|---:|---:|
| `c-wrong-type` instances | 3 | 0 |

However, only 2 of the 4 after-attempts completed. This result is therefore provisional: the target subtype went to zero, but on a subset small enough and incomplete enough that it needs replication and a performance review before the principle can be called confirmed.

### 5.4 Experiment 4: make vocabulary discovery searchable

**Hypothesis.** A CLI should not force agents to discover vocabulary by increasing `--top N` or piping long category lists through `grep`. It should expose a bounded, task-directed vocabulary discovery primitive.

**Failure targeted.** Primarily `c-truncated`, with secondary relevance to vocabulary-related `c-unknown` failures.

**Change.** Arm E candidate `4a197c3` added `botmap categories --search TERM`, plus a short skill note telling agents to use `--search` when looking for a specific kind of place. The implementation still scans the selected area to count categories; the improvement is not indexing speed but discoverability. Agents can ask for category values matching `bike`, `bus`, `station`, `pharmacy`, or `restaurant` directly instead of guessing a larger top-N cutoff.

**Subset.** All 13 baseline attempts that contained a `c-truncated` failure — which between them account for all 25 baseline instances of that subtype. This is a superset of Experiment 1's 6-attempt subset, so the before-figures differ: 13 instances on those 6 attempts, 25 instances across all 13.

**Result.**

| Metric | Before | After |
|---|---:|---:|
| `c-truncated` instances | 25 | 1 |

The run completed all 13 attempts, all OK, with 231 botmap calls, cost $3.77, and duration 65.4 minutes. The agent used `--search` directly in completed attempts, including `--search bike`, `--search bicycle`, `--search bus`, `--search station`, `--search pharmacy`, `--search drug`, and `--search restaurant`.

This is the strongest evidence in the study: the largest subset, full completion, and near-elimination of the target subtype. It also exposes a remaining gap. Substring search finds `gas_station` if the agent searches `gas` or `station`, but not if the user says "petrol pump." A follow-on semantic/regional vocabulary experiment was started to test whether the agent should be explicitly told to try regional equivalents such as "medical store → pharmacy" and "petrol pump → gas station." Early observation suggested the `--search` affordance alone already prompted the model to try several semantic variants, so the extra instruction may be redundant.

### 5.5 Summary of paired results

| # | Intervention | Subtype | Attempts | Before → After | Status |
|---|---|---|---:|---:|---|
| 1 | Truncation warning | `c-truncated` | 6 | 13 → 5 | Confirmed, partial |
| 2 | Wrong-column hint | `c-wrong-column` | 4 | 2 → 0 | Confirmed, small n |
| 3 | Wrong-type hint | `c-wrong-type` | 4 | 3 → 0 | Provisional, 2/4 completed |
| 4 | `categories --search` | `c-truncated` | 13 | 25 → 1 | Confirmed, all completed |

## 6. Multi-arm experiment structure

The paired experiments established individual properties. The arms tested where such properties come from: agent skill, prompt guidance, broad code optimization, or taxonomy-driven targeted experiments.

### 6.1 Arm A: loop-as-a-skill

Arm A tested whether an agent following explicit research-loop skills could produce and screen candidates without GEPA. This arm represents the hypothesis that agent-friendly CLI principles can be discovered by an agent that reads traces, proposes changes, verifies mechanisms, and records findings as a disciplined loop. It later measured existing candidates under the new evaluator.

Arm A attempted a three-candidate screen using the full question bank for each candidate. This made the arm slow and expensive by construction: each candidate required up to 60 agent attempts before comparison, rather than a small matched subset targeted at one failure class. Two candidates reached all 60 scheduled attempts; a third was intentionally stopped at 37/60 when the experiment was halted to control spend. The completed runs still had many incomplete or non-OK agent attempts, and enrichment timed out for the first two, so their class distributions are not directly comparable to the enriched baseline. The main qualitative insight was that helpful hints are necessary but not sufficient: the tool can provide guidance, and the agent may still ignore it.

Arm A candidates and verdicts:

| Candidate | Lever | Intended property | Run status | Verdict / reason |
|---|---|---|---|---|
| `cand/count-zero-hint @ 9a2496d` | Tool | Turn silent zero results into guided recovery by naming likely fixes | 60/60 scheduled attempts; 45 completed/OK; enrichment timed out | Not accepted as a broad winner because enriched comparison failed. Retained as directional evidence: raw records contained more guided Class B calls and one `ignored_hint`, showing both the value and limit of hints. |
| `cand/skill-bus-station @ 6c04003` | Instructions | Tell the agent to use the working bus-station value rather than an incorrect transit value | 60/60 scheduled attempts; 33 completed/OK; enrichment timed out | Not accepted. Completion was low and post-run classification was not comparable to baseline. It also reinforced the Arm B lesson that static instructions are weaker than runtime discovery and diagnostics. |
| `cand/count-flag-parity @ 05ef72c` | Tool | Accept natural flag spellings on `count`, such as parity with convenience commands | Stopped at 37/60 scheduled attempts | Inconclusive. The run was intentionally halted, not failed. Earlier evidence suggested the new affordance may not matter if agents do not naturally reach for that command shape. |

No Arm A candidate was accepted as a full-bank improvement. The accepted contribution from Arm A was methodological: running every candidate against all 60 questions is too slow for early principle discovery. Smaller paired experiments produced clearer evidence by spending attempts only where a candidate was expected to affect a known failure mode. That lesson is what Arm E later formalized (§6.5).

### 6.2 Arm B: prompt lever

Arm B tested whether agent-friendliness can be supplied as instructions rather than built into the CLI. It ran GEPA over `botmap/data/skill.md` only. The prompt optimizer tried five candidates across 63 evaluations. The best held-out program remained the base prompt; the final patch was empty.

This does not prove prompts cannot help. It shows that in this run, increasingly detailed instructions did not beat the base. Qualitatively, prompt candidates tended to grow into long manuals. They often rediscovered tool-side needs such as zero-result diagnosis, place-name normalization, and spatial joins.

Arm B's proposed skill patches clustered into the following changes:

| Skill-patch suggestion | Intended benefit | Why it was not accepted as the final result |
|---|---|---|
| Add a question-to-command decision table | Help the agent map common user questions to `count`, `places`, `where`, `at`, `addresses`, and boundary commands | It made the skill longer and more prescriptive, but did not improve held-out score over the base prompt. It also risked becoming stale as the CLI changed. |
| Add a zero-result protocol | Prevent agents from treating a guessed filter's `0` as absence | This identified a real principle, but the prompt is the wrong enforcement point. The paired tool-side wrong-column and wrong-type experiments showed the stronger form: diagnose the zero at runtime. |
| Add category and value discovery guidance | Encourage agents to enumerate valid values before guessing filters | Useful as documentation, but still required the agent to remember and execute the checklist. The truncation experiment showed that discovery commands themselves must expose completeness. |
| Add a schema cheatsheet | Reduce field/type confusion such as `class` vs `subtype` | It duplicated knowledge that already lives in the tool schema and can drift. Runtime schema/discovery commands are a safer home for this information. |
| Add shell quoting and filter-syntax warnings | Avoid command failures from unquoted places or `height>150` redirection | Helpful for Class A/B failures, but the evaluated baseline's most important measured signal was silent wrongness. These instructions did not produce a winning candidate. |
| Add a place-resolution ladder | Help agents recover from `where` failures, diacritics, qualifiers, and missing neighborhoods | This suggested a real CLI need: better place matching and clearer `no_match` suggestions. But prose lists of examples are brittle compared with a tool-side `placematch`/normalization mechanism. |
| Add boundary/GIS guidance | Stop agents from using unsupported `division_area` downloads when they need polygons | Useful documentation, but narrow and not shown to improve the measured target classes in Arm B. |
| Add anti-patterns | Warn against repeated failing commands, global downloads, parsing human stdout, unsupported filters, and ignored stderr | The anti-pattern list grew into a manual. It increased instruction burden without winning held-out evaluation. |
| Add transit-stop guidance | Clarify whether transit stops are `place` or `infrastructure` features and which category names to try | Some candidates embedded dubious or dataset-dependent vocabulary. This is exactly the kind of knowledge that should be discoverable from the CLI, not fossilized in a prompt. |
| Add spatial-join guidance | Explain that "X within N metres of Y" currently requires exporting two datasets and computing geometry externally | This was mostly a feature request. It did not fit a prompt-only patch and was better captured as a missing CLI command, e.g. a future `nearby` or spatial-join command. |
| Request new code abstractions such as `normalize.py`, `placematch.py`, and `nearby.py` | Move recurring recovery logic into code | These were outside Arm B's editable surface. They were rejected as prompt patches but retained as design signals for future tool-side work. |

The rejection criterion was therefore not that the suggestions were useless. They were rejected because Arm B was a prompt-only arm and the held-out optimizer did not find a prompt rewrite better than the base. Many suggestions survived in a different form: as principles, or as candidate tool-side interventions.

### 6.3 Arm C: full-repo context and broad edit surface

Arm C tested whether broad repository context helps an optimizer locate the true implementation homes of agent-facing failures. It gave GEPA broad read context and broad edit permissions while excluding evaluator files. The corrected run used 83 editable tracked text files and about 557k characters of read-only repository context.

The best patch was not a useful product change; it mostly changed `.gitignore` and embedded "new file needed" notes. The valuable signal was in the proposer's repeated requests for missing abstractions:

- shared zero-result diagnostics;
- centralized error handling;
- place-name normalization;
- generic suggestion/alias machinery.

Arm C candidates and rejected/retained signals:

| Candidate / suggestion | Intended benefit | Verdict / reason |
|---|---|---|
| Best generated patch: `.gitignore` edits plus embedded notes | Clean local artifacts and record future files needed | Rejected as a CLI improvement. It changed no agent-facing behavior, so it could not support a product claim. |
| `botmap/zero_results.py` | Centralize empty-result diagnostics across `count`, `sample`, `roads`, `water`, `landuse`, and `addresses` | Rejected as an immediate Arm C output because no working module was produced. Retained as a strong design signal because it recurred and aligns with measured `c-wrong-column`, `c-wrong-type`, and `c-unknown` failures. |
| `botmap/errors.py` | Convert raw STAC/S3/network failures into contextual messages with retry or scoping advice | Not accepted as implemented; only requested. Retained as a future principle candidate: environment failures should be distinguishable from user/query errors. |
| `botmap/placenames.py` | Add diacritic folding, transliteration, aliases, and better no-match suggestions | Not accepted as implemented; only requested. Retained as a plausible home for the "echo interpretation / recover place resolution" principle. |
| `botmap/suggest.py` | Provide generic suggestions for unknown commands, plural/singular variants, and hyphen/underscore aliases | Not accepted as implemented; only requested. Retained as a cross-command design idea: suggestion machinery should be shared, not ad hoc. |
| Invalid early full-repo candidate surfaces | Let optimizer edit broad files, including evaluator files or evaluator-adjacent tests | Rejected and invalidated. An optimizer must not be allowed to improve by changing the exam. |

A methodological correction occurred here: an earlier full-repo mode accidentally allowed evaluator files in the editable surface. That run was invalidated. The evaluator must remain read-only; otherwise the optimizer can improve the score by changing the exam.

### 6.4 Arm D: taxonomy-driven targeted experiments

Arm D took the current failure distribution and proposed the next experimental wave: zero-result diagnostics, wrong-type hints, A-to-B recovery, discovery commands, entity-resolution echoing, progress estimates, full-bank replication, and instruction-vs-tool comparisons. It also executed the small wrong-type hint experiment reported in §5.3. Arm D represents the main methodological turn of the project: the arms do not merely optimize a score; they convert measured failure classes into falsifiable CLI-design principles.

Arm D candidates and status:

| Candidate / experiment | Target failure | Intended property | Status | Verdict / reason |
|---|---|---|---|---|
| Wrong-type hint, `arm-d/wrong-type-hint-tool @ 9ba1187` | `c-wrong-type` | If a zero-count filter returns rows under another feature type, name that type and give the retry command | Ran on 4-attempt matched subset; 2/4 attempts completed | Provisionally accepted as principle evidence: target subtype moved `3 → 0`, but full-bank generality and performance safety remain untested. |
| Discovery command | Vocabulary and schema discovery failures | Add first-class search/list commands instead of requiring large dumps and grep | **Executed in Arm E** as `categories --search` (§5.4) | Accepted. Target subtype moved `25 → 1` on the full 13-attempt affected subset with all attempts completing. |
| Zero-result diagnostics | `c-unknown`, vocabulary/true-zero ambiguity | Give a falsifiable explanation or safe next probe for empty results | Planned only | Not accepted yet. Requires better probes to split `c-unknown`; otherwise the experiment would overclaim from instrumentation debt. |
| A-to-B recovery | Class A hard/unguided failures | Convert raw usage failures into guided retry messages | Planned only | Not accepted yet. Needs zero-spend triage because some messages may already be guided but classified as A. |
| Entity-resolution echo | Wrong or ambiguous entity resolution | Echo canonical place, region, country, bbox, and candidates | Planned only | Not accepted yet. Motivated by the MA/MT evaluator repair, but no paired product experiment was run. |
| Progress / estimate experiment | Long-running operations and timeouts | Surface cost/progress so agents can decide whether to wait, narrow, or stop | Planned only | Not accepted yet. It is a hypothesis from run/enrichment timeouts, not a measured CLI intervention. |
| Instruction-vs-tool comparison | Placement of guidance | Compare the same recovery principle as prompt instruction versus runtime CLI hint | Planned only | Not accepted yet. This is needed to test the Arm B vs tool-side interpretation directly. |

### 6.5 Arm E: failure-class routing and searchable discovery

Arm E was added after Arm A showed that full-bank screening of every candidate is too slow for early discovery. Instead of running each patch across all 60 attempts, Arm E used the enriched baseline taxonomy as an experimental router:

1. split attempts by observed failure subtype;
2. run each candidate only on the subset where its mechanism could plausibly act;
3. accept or reject the candidate on target failure movement;
4. reserve full-bank validation for a later combined patch set.

This produced the `categories --search` experiment reported in §5.4. The candidate was not generated by GEPA. It came from interpreting the same signal GEPA had already noticed: agents struggled with category vocabulary. Arm B, the prompt-only GEPA arm, proposed more instruction, larger category listings, and grep-like discovery habits. Arm C, the code-editing GEPA arm, also saw the shape of the problem, repeatedly asking for suggestion and discovery abstractions such as `botmap/suggest.py`. But even with broad repository context and broad code-edit permission, Arm C did not produce the concrete shippable affordance:

```bash
botmap categories --search TERM
```

| Arm | Saw vocabulary/discovery pain? | Produced `categories --search`? | Produced validated target improvement? |
|---|---|---|---|
| Arm B: prompt GEPA | Yes, partly | No | No |
| Arm C: code GEPA | Yes, partly | No | No |
| Arm E: failure-routed design | Yes | Yes | Yes: `c-truncated 25 → 1` |

Arm E's result clarifies the difference between *recognizing* a problem and *designing the right affordance* for it. Both GEPA arms saw that discovery was hard, but expressed the insight either as longer manuals or as vague "new file needed" architecture notes. The failure-class method converted the pain into a narrow CLI operation that could be tested directly. This is the study's main methodological result: the optimizer did not need help seeing that discovery was hard; it needed help turning that observation into a small, measurable interface primitive.

Arm E also started a semantic/regional vocabulary follow-up, on the theory that substring search alone may not map user language to dataset language: "petrol pump" may need `gas_station`, "medical store" may need `pharmacy`, and "bus stop" may need `bus_station`. The first observation was that agents already tried semantically related terms once `--search` existed. That sharpens the next question: should the CLI merely expose local vocabulary and let the model reason, or should the skill explicitly request regional and synonym expansion?

## 7. End result: principles, not patches

The main product of the experiment is the principle set below. Some principles are supported by paired evidence; others are hypotheses suggested by baseline traces and arm outputs. Every principle is traceable to a failure mode and a possible paired experiment.

| Principle | Failure class | Evidence | Status |
|---|---|---|---|
| 7.1 Make completeness explicit | `c-truncated` | Exp 1 (13 → 5), Exp 4 (25 → 1) | Confirmed |
| 7.2 Make zero results diagnostic | `c-wrong-column`, `c-wrong-type`, `c-unknown` | Exp 2 (2 → 0), Exp 3 (3 → 0) | Confirmed for wrong-column; provisional for wrong-type; untested for `c-unknown` |
| 7.3 Name the next action | A, B | Carried by every Exp 1–4 message; never isolated | Hypothesis |
| 7.4 Keep data output stable | — | Design contract held across Exp 1–4 | Constraint, not separately tested |
| 7.5 Make discovery first-class | `c-truncated`, vocabulary `c-unknown` | Exp 4 (25 → 1), all attempts completed | Confirmed |
| 7.6 Echo interpretation | Wrong/ambiguous entity resolution | MA/MT evaluator repair only | Hypothesis |
| 7.7 Treat recovery as a primary metric | All | Built into the rubric at 60% weight | Methodological commitment |

### 7.1 Make completeness explicit

If output is bounded, paginated, sampled, filtered, cached, approximate, or truncated, the CLI should say so. Agents do not reliably infer incompleteness from suspiciously short output.

*Design implication:* include `shown`, `total`, `truncated`, continuation tokens, or exact commands to retrieve the complete result. Preserve stable stdout and put guidance in stderr or structured metadata.

### 7.2 Make zero results diagnostic

A bare zero is not enough when zero may mean wrong field, wrong type, wrong vocabulary, unsupported filter, wrong entity, or true absence. The CLI should distinguish these cases when it can do so cheaply and with high confidence.

*Design implication:* empty-result responses should include recognized filters, unrecognized values, compatible fields, compatible resource types, and safe next probes.

### 7.3 Name the next action

Agent-friendly guidance should be operational. "Invalid option" is less useful than "Try: `botmap count -t place --where categories.primary=hospital`."

*Design implication:* parser errors, validation failures, and warnings should include exact or near-exact retry commands.

### 7.4 Keep data output stable while exposing guidance

All four paired interventions preserved machine-readable stdout and emitted concise guidance on stderr. This pattern lets the CLI remain composable while still guiding the agent, which is why none of the changes would break an existing script.

*Design implication:* do not choose between JSON and recoverability. Use stderr warnings or structured diagnostic fields.

### 7.5 Make discovery first-class

Agents should not have to dump large lists, grep them, and guess higher limits. Schema and vocabulary discovery should be executable. This is the best-supported principle in the study: adding one search primitive removed 24 of 25 truncation failures without losing a single attempt (§5.4).

*Design implication:* provide commands such as `schema`, `fields`, `values`, `categories --search`, and `explain-filter`. Prefer task-directed discovery primitives over asking agents to page through top-N lists or pipe large outputs through `grep`.

### 7.6 Echo interpretation

When a CLI resolves an ambiguous entity, context, namespace, account, region, or default, it should echo what it resolved. This principle was not confirmed by a paired run in this study, but the evaluator's MA/MT repair showed how easily ambiguity can create false conclusions.

*Design implication:* include structured resolution metadata such as query, canonical name, region, country, ID, and scope.

### 7.7 Treat recovery as a primary metric

An agent-friendly CLI is not one that never errors. It is one where errors are recoverable without human intervention.

*Design implication:* measure self-recovery rate, extra calls, extra tokens, and extra wall-clock after a recoverable failure.

## 8. What the arms contributed to the principles

The arms sharpened the distinction between *where a fix can be expressed* and *where it should live*.

- **Arm A** showed that agent-led experimentation can verify mechanisms and preserve qualitative insights, but that full-bank candidate screening is too slow, because every candidate must run across all 60 questions before comparison.
- **Arm B** showed that prompt-only improvements grow into long manuals. Instructions can warn agents about traps, but they are weaker than live CLI diagnostics at the point of failure.
- **Arm C** showed that broad context helps identify missing abstractions — zero-result diagnostics, centralized errors, place-name normalization, suggestion layers — even when the produced patch is useless.
- **Arm D** showed the most productive path for principle discovery: turn each measured failure subtype into a targeted paired experiment.
- **Arm E** showed that routing candidates by failure class converts a recognized problem into a testable interface primitive, and did so where both GEPA arms had stopped at recognition.

Read together: GEPA arms were good at *noticing* pain and bad at *shaping* it into an interface. Failure-class routing supplied the missing step. The framework's principles are therefore derived from observed agent struggle, not asserted from taste.

## 9. Human-friendly vs agent-friendly CLIs

Many traditional CLI usability patterns assume human judgment:

- terse errors;
- implicit defaults;
- partial output for readability;
- prose documentation;
- generic usage dumps;
- silent fallback behavior.

For agents, these can be hostile. Agents operate by chaining evidence. If the CLI hides uncertainty or completeness, the agent may convert ambiguity into fact. Agent-friendly CLIs therefore need stronger observability: they should expose what they interpreted, what they omitted, and what command should come next.

This does not mean CLIs should become verbose by default in ways that break scripts. The evidence points to a compositional protocol: stable stdout for data, stderr or explicit diagnostic fields for interpretation and recovery.

## 10. Threats to validity

### 10.1 Single tool and domain

The study uses one geospatial CLI. The principles are likely relevant to other structured CLIs, but replication is needed across tools such as cloud CLIs, database CLIs, logging/search CLIs, and package managers.

### 10.2 Stochastic agents

AI agents are non-deterministic. Paired subsets reduce but do not eliminate route variation. Small improvements require replication before strong claims.

### 10.3 Small matched subsets

Experiments 2 and 3 moved counts of 2 and 3 to zero on 4-attempt subsets. Those are directionally consistent with the taxonomy but too small to carry weight alone. Only Experiment 4, which covered every affected attempt and completed all of them, supports a confident claim.

### 10.4 Incomplete and timed-out attempts

Several runs had incomplete attempts or enrichment timeouts. We preserved these as attempt-level evidence rather than silently replacing them. Some results are therefore explicitly narrow or provisional.

### 10.5 Evaluator errors

The MA/MT false-positive repair showed that evaluator probes can misclassify. The evaluator must remain auditable, sabotage-tested, and conservative when probes are inconclusive.

### 10.6 Optimizer boundary errors

Full-repo optimization initially allowed evaluator files in the editable surface. Those runs were invalidated. This highlights a general risk: optimization experiments must prevent the optimizer from changing the judge.

## 11. Future work

The next experiments should strengthen or falsify the framework:

1. **Zero-result diagnostics.** Add high-confidence diagnostics for empty counts and target `c-unknown` and vocabulary failures — the largest untouched slice of the baseline at 25 instances.
2. **Wrong-type replication.** Rerun the wrong-type hint on a larger subset, then the full bank, and confirm all attempts complete.
3. **A→B recovery.** Convert common usage and raw errors into exact retry commands, and measure Class A reduction plus self-recovery. Triage first: some Class A calls may already be guided but misclassified.
4. **Semantic vocabulary expansion.** `categories --search` handles substrings; test whether regional and synonym mapping ("petrol pump" → `gas_station`) needs an explicit instruction or is already emergent.
5. **Entity resolution echo.** Test ambiguous locations with structured resolution metadata.
6. **Progress and estimates.** Add progress or cost estimates to expensive commands and measure wall-clock and abandonment.
7. **Instruction vs tool comparison.** For a single principle, compare a tool-side hint with a `skill.md` instruction on the same subset — the direct test of the Arm B result.
8. **Combined patch, full bank.** Ship all confirmed interventions together and validate on all 60 questions.
9. **Cross-CLI replication.** Repeat the method on a non-geospatial CLI.

## 12. Conclusion

The main lesson is simple: agent-friendly CLIs make hidden state visible. They expose completeness, interpretation, schema compatibility, and recovery paths.

The multi-arm structure helped separate three questions: what failures agents encounter, where fixes can be expressed, and which general principles survive paired tests. On the first, the most important failures in the botmap study were not commands that crashed but commands that succeeded misleadingly — half of all failure instances. On the second, prompt-only optimization did not beat its base and broad code optimization produced no shippable change, while routing candidates by failure class did. On the third, paired experiments showed that small tool-side changes reduce specific silent-wrong failure classes: warning on truncation, naming the correct field, provisionally naming the correct type, and — most effectively — making vocabulary searchable rather than something the agent must guess its way into.

This suggests a shift in CLI design philosophy. For humans, a CLI can often be terse and rely on judgment. For agents, a CLI should behave like a reliable reasoning partner: stable in its data output, explicit about uncertainty, and concrete about the next command to try.

## References

[1] Agrawal et al. *GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning.* arXiv:2507.19457. <https://arxiv.org/abs/2507.19457>

## Artifact availability

Experiment artifacts, run summaries, and documentation are available at:

```text
https://huggingface.co/datasets/nilenso/autoresearch
```

Local publication index:

```text
experiments/published/agent-friendly-cli-experiment-20260825/README.md
```
