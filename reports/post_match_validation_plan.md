# Post-match validation plan — Worlds 2026 Swiss stage

This document is the pre-registered rule set for scoring the predictions made
**before** each match. It exists so a result cannot be retro-fitted: the rules
below are exactly what `src/score_match.py` implements, and they are applied to
rows that are written to `powerbi/post_match_validation_log.csv` **before** the
scheduled start.

The log is append-only: a new row is registered before every fixture, and the
result columns are filled in afterwards. The original prediction is never
overwritten.

## Registered fixtures

| # | Match | Format | Start (UTC) | Cutoff | Pre-registered probability | Status |
|---|---|---|---|---|---|---|
| 1 | HLE vs IG (`115660540726095045`) | Bo1 | 2026-10-25 17:00 | 2026-10-25 16:20 | HLE **43.9%** / IG **56.1%** (CI 37.2–51.6%) | **Scored** |
| 2 | LYON vs IG (`115660540726095065`) | Bo3 | 2026-10-28 23:00 | 2026-10-27 00:00 | LYON **41.4%** / IG **58.6%** per game (CI 33.5–48.9%) · **37.2% / 62.8%** series | **Pending** |

Every row also records the model id, the holdout metrics at the time of the
forecast and the data cutoff, so a later reader can tell exactly which model
version produced which number.

## Why the probability is logged, not just the pick

The headline call is always "close to a coin flip with a marginal lean".
Logging the probability — not the pick — is what makes the result scoreable: a
directionally correct 51% prediction is worth less than a 90% one, and the
Brier score captures that difference.

## Scoring rules

Applied by `python src\score_match.py --winner <código o nombre>`:

1. **Brier score** — `(p_team_a − actual_team_a_win)²`, where
   `actual_team_a_win` is 1 for a team_a win and 0 for a team_b win. Lower is
   better; a coin flip scores **0.2500**.
2. **Log loss** — `−ln(p_of_the_actual_winner)`, using the predicted
   probability of the team that actually won. Lower is better; a coin flip
   scores **0.6931**.
3. **Correct pick** — the model's direction (team_a if `p_team_a ≥ 0.5`,
   otherwise team_b) compared with the actual winner. Recorded as `Yes` / `No`.
4. **Context fields** — the side played by team_a, the patch and the game
   duration are recorded when they can be confirmed, because side assignment
   alone moves the estimate by roughly 9 points.
5. **The original prediction is never overwritten.** The script fills only the
   empty result columns of the existing row and appends to `notes`.

## Decision rule (fixed in advance)

The prediction is judged against the baselines, not against a narrative:

- Brier ≤ 0.2500 and log loss ≤ 0.6931 → the model beat the coin flip on this
  match.
- Brier > 0.2500 → the model did worse than a coin flip on this match.
- Either way, **one match does not validate the model.** The honest read stays
  the holdout result: AUC ≈ 0.47–0.49 over 72–85 games is not distinguishable
  from chance, and the correct conclusion after scoring is reported as such.

## Outcome of fixture 1 (HLE vs IG, 2026-10-25)

| Item | Value |
|---|---|
| Pre-registered | HLE 43.9% / IG 56.1% · pick **IG** |
| Actual | **IG won** (blue side), 29–9 kills, +9,252 gold, 28.6 min, patch 16.20 |
| Brier | **0.1924** (coin flip 0.2500) → better than the baseline |
| Log loss | **0.5774** (coin flip 0.6931) → better than the baseline |
| Correct pick | **Yes** |

Read it correctly: the model was right on **one** match and produced a
probability that beat the coin-flip baseline on that match. The model itself is
still not distinguishable from chance on 85 holdout games (AUC 0.477, Brier
0.258). A single correct call is an observation, not a validation.

## Current status

Fixture 1 is scored and the row is closed. Fixture 2 is **pending**: the row was
written on 2026-10-27, before the 2026-10-28 23:00 UTC start, and the result
columns are intentionally empty. Nothing in this repository claims a result that
has not been observed.

## Refresh

```bat
REM preview without writing
python src\score_match.py --winner iG --dry-run

REM write the result
python src\score_match.py --winner iG --side blue --patch 16.20 --source "Oracle's Elixir singleGame ..."
```

For a different fixture, pass its id explicitly:

```bat
python src\score_match.py --match-id 115660540726095065 --winner LYON --side red
```

Then update `reports/model_card.md` and, if the underlying feed was refreshed,
re-run `python src\run_pipeline.py`.
