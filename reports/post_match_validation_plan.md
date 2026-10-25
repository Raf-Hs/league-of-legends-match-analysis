# Post-match validation plan — HLE vs IG, Worlds 2026 Swiss Day 3

This document is the pre-registered rule set for scoring the prediction made
before the match. It exists so the result cannot be retro-fitted: the rules
below are exactly what `src/score_match.py` implements, and they are applied to
the row that was already written to `powerbi/post_match_validation_log.csv`
**before** the scheduled start.

| Item | Value |
|---|---|
| Match | Hanwha Life Esports (HLE) vs Invictus Gaming (IG), best of 1 |
| Oracle's Elixir match ID | `115660540726095045` |
| Scheduled start | 2026-10-25 17:00 UTC |
| Data cutoff (no post-cutoff information used) | 2026-10-25 16:20 UTC |
| Match state at collection | `unstarted` |
| Primary model | `M3_core5` — 5 features, L2 logistic regression, `C=0.5`, no intercept (side-neutral) |
| Pre-registered probability | HLE **43.9%** / IG **56.1%** |
| 90% bootstrap interval (HLE) | 37.2% – 51.6% |
| Holdout metrics | AUC 0.494 · Brier 0.255 (coin flip 0.250) · log loss 0.703 (coin flip 0.693) |

## Why the probability is logged, not just the pick

The headline call is "close to a coin flip with a marginal IG lean". Logging
the probability — not the pick — is what makes the result scoreable: a
directionally correct 51% prediction is worth less than a 90% one, and the
Brier score captures that difference.

## Scoring rules

Applied by `python src/score_match.py --winner HLE|IG`:

1. **Brier score** — `(p_HLE − actual_HLE_win)²`, where `actual_HLE_win` is 1
   for an HLE win and 0 for an IG win. Lower is better; a coin flip scores
   **0.2500**.
2. **Log loss** — `−ln(p_of_the_actual_winner)`, using the predicted
   probability of the team that actually won. Lower is better; a coin flip
   scores **0.6931**.
3. **Correct pick** — the model's direction (HLE if `p_HLE ≥ 0.5`, otherwise
   IG) compared with the actual winner. Recorded as `Yes` / `No`.
4. **Context fields** — HLE's side, the patch played and the game duration are
   recorded when they can be confirmed, because side assignment alone moves
   the estimate by roughly 9 points (48.4% vs 39.4% for HLE).
5. **The original prediction is never overwritten.** The script fills only the
   empty result columns of the existing row and appends to `notes`.

## Decision rule (fixed in advance)

The prediction is judged against the baselines, not against a narrative:

- Brier ≤ 0.2500 and log loss ≤ 0.6931 → the model beat the coin flip on this
  match.
- Brier > 0.2500 → the model did worse than a coin flip on this match.
- Either way, **one match does not validate the model.** The honest read stays
  the holdout result: AUC 0.494 over 72 games with 33 positives is not
  distinguishable from chance, and the correct conclusion after scoring is
  reported as such.

## Current status

The log row in `powerbi/post_match_validation_log.csv` is still pending
(`actual_winner` empty, note: "Pending result; prediction was generated before
the scheduled start"). Nothing in this repository claims a result that has not
been observed.

## Refresh

```bash
python src/score_match.py --winner IG --side blue --patch 16.20 --source "Oracle's Elixir match page"
python src/score_match.py --winner HLE --dry-run   # preview without writing
```

Then update the holdout metrics in `reports/model_card.md` and re-run
`python src/run_pipeline.py` if the underlying feed is refreshed.
