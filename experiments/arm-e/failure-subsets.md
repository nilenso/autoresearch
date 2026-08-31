# Arm E failure-class subsets

Source: `/Users/priyangapkini/nilenso/ai-playground/autoresearch/experiments/runs/agenteval-measurement-3009509/agenteval-summary-with-retries.json`

The subsets route each candidate only to attempts where its mechanism can plausibly affect the measured failure.

| Subset | Priority | Baseline attempts | Baseline failures | Selected questions | Candidate / status |
|---|---:|---:|---:|---|---|
| `combined-accepted-patches-priority` | 0 | 14 | 30 | `asian-restaurants-rollup`, `basic-category-rollup`, `beach-accessibility-malta`, `bike-parking-coverage`, `bus-stops-cambridge`, `bus-stops-with-coffee`, `ev-charging-gap`, `residential-share-cambridge` | combined tool-side hints: 00bff1a + 7c794ff + 9ba1187 |
| `c-truncated` | 1 | 13 | 25 | `asian-restaurants-rollup`, `basic-category-rollup`, `beach-accessibility-malta`, `bike-parking-coverage`, `bus-stops-cambridge`, `bus-stops-with-coffee`, `ev-charging-gap` | cand/categories-truncation-hint @ 00bff1a |
| `c-wrong-column` | 2 | 2 | 2 | `bike-parking-coverage`, `residential-share-cambridge` | cand/count-wrong-column-hint @ 7c794ff |
| `c-wrong-type` | 3 | 2 | 3 | `beach-accessibility-malta`, `residential-share-cambridge` | arm-d/wrong-type-hint-tool @ 9ba1187 |
| `c-unknown` | 4 | 11 | 25 | `asian-restaurants-rollup`, `beach-accessibility-malta`, `bike-parking-coverage`, `bus-stops-cambridge`, `bus-stops-with-coffee`, `ev-charging-gap`, `malta-highways-absent-class`, `residential-share-cambridge`, `street-canonical-form` | not yet accepted; requires probe split before paid run |
| `A` | 5 | 17 | 38 | `basic-category-rollup`, `beach-accessibility-malta`, `building-parts-detail`, `bus-stops-cambridge`, `bus-stops-with-coffee`, `ev-charging-gap`, `junction-density`, `malta-highways-absent-class`, `pharmacies-monaco`, `pharmacy-near-address`, `residential-share-cambridge`, `reykjavik-diacritic`, `street-canonical-form`, `waterfront-buildings-reykjavik` | not yet accepted; A-to-B recovery candidate needed |

## Attempt lists

### `combined-accepted-patches-priority`

Principle: Validate the accepted/provisional tool-side principles together before a full-bank run.

- `beach-accessibility-malta__r1` (A=2, B=2, c-truncated=2, c-unknown=3, c-wrong-type=2)
- `bike-parking-coverage__r1` (B=2, c-truncated=3, c-wrong-column=1)
- `bus-stops-cambridge__r1` (A=2, B=1, c-truncated=3, c-unknown=3)
- `asian-restaurants-rollup__r1` (c-truncated=2, c-unknown=6)
- `basic-category-rollup__r1` (c-truncated=2)
- `basic-category-rollup__r2` (A=1, B=1, c-truncated=2)
- `bike-parking-coverage__r2` (B=1, c-truncated=2, c-unknown=3)
- `bus-stops-with-coffee__r1` (A=3, B=2, c-truncated=2, c-unknown=1)
- `bus-stops-with-coffee__r2` (c-truncated=2)
- `ev-charging-gap__r2` (A=14, c-truncated=2)
- `residential-share-cambridge__r2` (A=1, c-wrong-column=1, c-wrong-type=1)
- `asian-restaurants-rollup__r2` (c-truncated=1)
- `bus-stops-cambridge__r2` (c-truncated=1, c-unknown=1)
- `ev-charging-gap__r1` (D=1, c-truncated=1, c-unknown=2)

### `c-truncated`

Principle: Make completeness explicit; never silently truncate discovery output.

- `bike-parking-coverage__r1` (B=2, c-truncated=3, c-wrong-column=1)
- `bus-stops-cambridge__r1` (A=2, B=1, c-truncated=3, c-unknown=3)
- `asian-restaurants-rollup__r1` (c-truncated=2, c-unknown=6)
- `basic-category-rollup__r1` (c-truncated=2)
- `basic-category-rollup__r2` (A=1, B=1, c-truncated=2)
- `beach-accessibility-malta__r1` (A=2, B=2, c-truncated=2, c-unknown=3, c-wrong-type=2)
- `bike-parking-coverage__r2` (B=1, c-truncated=2, c-unknown=3)
- `bus-stops-with-coffee__r1` (A=3, B=2, c-truncated=2, c-unknown=1)
- `bus-stops-with-coffee__r2` (c-truncated=2)
- `ev-charging-gap__r2` (A=14, c-truncated=2)
- `asian-restaurants-rollup__r2` (c-truncated=1)
- `bus-stops-cambridge__r2` (c-truncated=1, c-unknown=1)
- `ev-charging-gap__r1` (D=1, c-truncated=1, c-unknown=2)

### `c-wrong-column`

Principle: If a value exists under another field, name the field and retry command.

- `bike-parking-coverage__r1` (B=2, c-truncated=3, c-wrong-column=1)
- `residential-share-cambridge__r2` (A=1, c-wrong-column=1, c-wrong-type=1)

### `c-wrong-type`

Principle: If the same filter works under another feature type, name the type and retry command.

- `beach-accessibility-malta__r1` (A=2, B=2, c-truncated=2, c-unknown=3, c-wrong-type=2)
- `residential-share-cambridge__r2` (A=1, c-wrong-column=1, c-wrong-type=1)

### `c-unknown`

Principle: A zero result should carry a falsifiable explanation or safe next probe.

- `asian-restaurants-rollup__r1` (c-truncated=2, c-unknown=6)
- `beach-accessibility-malta__r1` (A=2, B=2, c-truncated=2, c-unknown=3, c-wrong-type=2)
- `bike-parking-coverage__r2` (B=1, c-truncated=2, c-unknown=3)
- `bus-stops-cambridge__r1` (A=2, B=1, c-truncated=3, c-unknown=3)
- `residential-share-cambridge__r1` (c-unknown=3)
- `ev-charging-gap__r1` (D=1, c-truncated=1, c-unknown=2)
- `beach-accessibility-malta__r2` (c-unknown=1)
- `bus-stops-cambridge__r2` (c-truncated=1, c-unknown=1)
- `bus-stops-with-coffee__r1` (A=3, B=2, c-truncated=2, c-unknown=1)
- `malta-highways-absent-class__r1` (c-unknown=1)
- `street-canonical-form__r1` (c-unknown=1)

### `A`

Principle: Hard errors should become guided retry paths.

- `ev-charging-gap__r2` (A=14, c-truncated=2)
- `bus-stops-with-coffee__r1` (A=3, B=2, c-truncated=2, c-unknown=1)
- `junction-density__r2` (A=3)
- `beach-accessibility-malta__r1` (A=2, B=2, c-truncated=2, c-unknown=3, c-wrong-type=2)
- `bus-stops-cambridge__r1` (A=2, B=1, c-truncated=3, c-unknown=3)
- `reykjavik-diacritic__r1` (A=2)
- `waterfront-buildings-reykjavik__r1` (A=2)
- `basic-category-rollup__r2` (A=1, B=1, c-truncated=2)
- `building-parts-detail__r1` (A=1, B=1)
- `malta-highways-absent-class__r2` (A=1, B=1)
- `pharmacies-monaco__r1` (A=1)
- `pharmacies-monaco__r2` (A=1)
- `pharmacy-near-address__r1` (A=1)
- `pharmacy-near-address__r2` (A=1)
- `residential-share-cambridge__r2` (A=1, c-wrong-column=1, c-wrong-type=1)
- `reykjavik-diacritic__r2` (A=1)
- `street-canonical-form__r2` (A=1)
