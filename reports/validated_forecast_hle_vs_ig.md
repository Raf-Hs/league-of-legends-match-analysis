# Validated forecast — HLE vs IG, Worlds 2026 Swiss Day 3

**A pre-registered prediction, an observed result, and an honest score.**

| Item | Value |
|---|---|
| Match | Hanwha Life Esports (HLE) vs Invictus Gaming (IG) — best of 1 |
| Oracle's Elixir match id | `115660540726095045` |
| Block | Worlds 2026 Main Event, Swiss Day 3 |
| Scheduled start | 2026-10-25 17:00 UTC (game actually started 17:19:41 UTC) |
| Data cutoff (pre-registered) | 2026-10-25 16:20 UTC — no information after this point was used |
| Match state at collection | `unstarted` |
| Model | `M3_core5` — 5 features, L2 logistic regression, `C=0.5`, no intercept (side-neutral) |
| **Pre-registered probability** | **HLE 43.9% / IG 56.1%** (90% bootstrap interval for HLE: 37.2%–51.6%) |
| Pre-registered pick | **IG** (p > 0.5) |
| Holdout metrics at the time | AUC 0.494 · Brier 0.255 (coin flip 0.250) · log loss 0.703 (coin flip 0.693) |

## What was registered, and when

The probability was written to `powerbi/post_match_validation_log.csv` at
**2026-10-25 16:47 UTC** — thirteen minutes before the scheduled start, and
from data collected between 16:25 and 16:26 UTC with a hard cutoff of 16:20
UTC. The row still contained only the prediction; the result columns were
empty.

That is the point of the exercise: the number was fixed before anyone knew
the result, so it can be scored without hindsight.

## What actually happened

| | |
|---|---|
| Winner | **Invictus Gaming** |
| Side | IG blue, HLE red |
| Kills | IG 29 – HLE 9 |
| Gold | IG 60,355 – HLE 51,103 (**+9,252**) |
| Objectives | IG 7 towers / 4 dragons; HLE 3 towers / 0 dragons / 1 baron |
| Duration | 28.6 minutes (1,716 s) |
| Patch | 16.20 |
| Source | Oracle's Elixir `singleGame` `oe:game:9a1f197da4a391abb754cd654cf31f71` |

## Score (rules fixed in advance)

`python src\score_match.py --winner IG --side red --patch 16.2 --duration 28.6`

| Metric | Model | Coin flip | Verdict |
|---|---:|---:|---|
| Brier score | **0.1924** | 0.2500 | better than baseline |
| Log loss | **0.5774** | 0.6931 | better than baseline |
| Correct pick | **Yes** (IG) | — | direction correct |

Reproduce it without writing anything:

```bat
python src\score_match.py --match-id 115660540726095045 --winner IG --dry-run
```

## Why the model leaned IG, and whether that mattered

The pre-match evidence was split: HLE had the better early game (last-10
GD@10 +202 vs −544, 70% first-blood rate vs 10%), IG had the better end game
and objective profile (last-10 end-game gold +757 vs −898, objective composite
+2.6 vs +0.6). The model weighted IG's objective control and end-game gold
difference more heavily, producing the 43.9/56.1 split.

The realised game matched that reading closely: IG won on objectives (7–3
towers, 4–0 dragons) and on a +9,252 gold swing. But **the observed margin is
not evidence that the model is good** — the model forecast a 56% chance for
IG and the same 56% chance would have been recorded for most of the plausible
IG-favoured scenarios. One match cannot separate a 51% model from a 60% model.

## What this does and does not prove

**Does:**
- The pipeline is reproducible and honest end to end: collect → clean → model →
  register → score, with no post-hoc edits to the prediction.
- The pre-registered number beat both coin-flip baselines on this fixture.
- The side assumption was worth logging: HLE was red, and the side-neutral
  43.9% sat between the blue-side (48.4%) and red-side (39.4%) scenarios.

**Does not:**
- It does **not** validate the model. The chronological holdout (now 85 games,
  42 positives) still gives AUC 0.477, Brier 0.259 and log loss 0.712 — at or
  slightly worse than chance. A single correct call does not change that.
- It does not prove the feature set works. The winning margin came from the
  same objective-control signal the model leaned on, but the model has no
  mechanism to be right for the right reason in a single game.
- It says nothing about the *next* fixture. The next forecast (LYON vs IG on
  2026-10-28) is a separate pre-registration in the same log, scored the same
  way.

## Where the numbers live

| Artefact | Path |
|---|---|
| Pre-registered row (scored) | `powerbi/post_match_validation_log.csv` |
| Scoring rules | `reports/post_match_validation_plan.md` |
| Model card (holdout metrics) | `reports/model_card.md` |
| Raw source payload | `data/raw/game_details/oe_game_9a1f197da4a391abb754cd654cf31f71.json.gz` |
| Power BI export of the log | `data/powerbi/FactValidationLog.csv` |
