# Model Card — Worlds 2026 pre-match win-probability model

## 1. Model overview

| Item | Detail |
|---|---|
| Model name | Worlds 2026 intra-cohort form model |
| Version | 1.1 (refit on data through 2026-10-27 00:00 UTC) |
| Date | 2026-10-27 |
| Type | L2-regularized logistic regression |
| Target | Probability that team_a (the blue side in the historical feed) wins a game |
| Primary use | Pre-match probability estimate for a single fixture, plus a best-of-3 series conversion |
| Current output | LYON **41.4%** / IG **58.6%** per game · **37.2% / 62.8%** as a best of 3 |
| Uncertainty | 90% bootstrap interval for LYON: 33.5%–48.9% |
| Training sample | 179 games between Worlds 2026 teams (of 226 eligible) |
| Holdout | 85 games, chronological |
| Holdout AUC | 0.477 |
| Holdout Brier | 0.259 (coin flip: 0.250) |
| Holdout log loss | 0.712 (coin flip: 0.693) |

**Headline caveat:** on the refreshed holdout the model is **at or slightly
worse than a coin flip** on every metric. It is a structured baseline and a
transparent way to quantify form — not a betting model. Version 1.0 (data
through 2026-10-25) scored AUC 0.494 / Brier 0.255 on a 72-game holdout; the
extra games moved it marginally down, which is what an honest refit looks like.

## 2. Intended use

**Intended:**

- Demonstrate a reproducible, leakage-controlled analytics pipeline.
- Provide a structured, transparent pre-match probability estimate.
- Quantify uncertainty and show why a single fixture is hard to predict.
- Serve as a baseline for pre-registered post-match validation.

**Not intended:**

- Betting, wagering, or financial decisions.
- Roster, contract, or scouting decisions.
- Claims about player quality or causality.
- High-confidence forecasting. The holdout does not support that.

## 3. Data

### 3.1 Source

Oracle's Elixir public API, the same data that powers `oracleselixir.com`.
The bulk CSV was unavailable (Google Drive quota exceeded); the API fallback
is recorded in `data/raw/collection_manifest.json`.

### 3.2 Sample construction

- 16 Worlds 2026 teams, up to 50 recent games each.
- 630 unique completed games, 1,260 team-game rows.
- 226 games between two Worlds teams; 179 modelling games after requiring at
  least five prior games and complete features.
- No target-match leakage: match `115660540726095065` is absent from the fact
  and model tables, and the check is re-run on every pipeline execution.

### 3.3 Features

| Feature | Definition | Window |
|---|---|---|
| `wr_10_diff` | team_a win rate − team_b win rate | last 10 games |
| `gd10_10_diff` | team_a mean GD@10 − team_b mean GD@10 | last 10 games |
| `gold_diff_10_diff` | team_a mean final gold diff − team_b mean final gold diff | last 10 games |
| `kd_diff_10_diff` | team_a mean kill diff − team_b mean kill diff | last 10 games |
| `obj_10_diff` | team_a mean objective composite − team_b mean objective composite | last 10 games |

Objective composite = tower diff + dragon diff + 2 × baron diff.

All features are pre-game. Rolling features are shifted so the current game is
excluded. For an unplayed fixture the "last 10" are the ten most recent games
of each team before the collection cutoff.

### 3.4 Why GD@10, not GD@15

The API does not expose GD@15. GD@10 is the sum of five players' `gxd10` and
is used as a clearly labeled proxy.

### 3.5 Best-of-3 conversion

`P(series win) = p² · (3 − 2p)` — the probability of winning at least two of
three games, assuming independent games and a constant per-game probability
(no side or draft adaptation). This is a stated simplification: the model's
native output is a per-game probability, and the series number is derived from
it.

## 4. Modelling

### 4.1 Split

- **Train:** games before 2026-09-01 — 94 games (2026-06-30 to 2026-08-30).
- **Test:** games from 2026-09-02 to 2026-10-26 — 85 games.
- No shuffling. No future information in training.

### 4.2 Estimator

- Standardize features on the training fold only.
- L2 logistic regression, `C=0.5`, `fit_intercept=False`, `max_iter=5000`.
- Why no intercept: every historical `team_a` is blue side, but the target side
  is unconfirmed. An intercept would encode the training period's blue-side
  rate. The model is side-neutral; side is handled as a scenario.
- `C=0.5` was fixed before evaluating the holdout. A sensitivity check is in
  `data/processed/scenario_analysis.csv`.

### 4.3 Current prediction (LYON vs IG, 2026-10-28 23:00 UTC, Bo3)

The target vector is LYON minus IG:

| Feature | Value |
|---|---:|
| Win rate diff | 0.0 |
| GD@10 diff | +91.7 |
| End-game gold diff | −3,191.8 |
| Kill diff diff | −1.1 |
| Objective composite diff | −3.7 |

Model output: **41.4% LYON per game** → **37.2% LYON as a best of 3**.

## 5. Performance

### 5.1 Holdout metrics

| Model | Features | AUC | Brier | Log loss | Accuracy |
|---|---:|---:|---:|---:|---:|
| **Coin flip** | 0 | 0.500 | **0.250** | **0.693** | **49.4%** |
| Win rate only | 1 | 0.476 | 0.257 | 0.707 | 47.1% |
| Core 4 | 4 | 0.478 | 0.259 | 0.712 | 42.4% |
| **Core 5 (primary)** | **5** | **0.477** | **0.259** | **0.712** | **42.4%** |
| 8-feature | 8 | 0.458 | 0.262 | 0.717 | 40.0% |

**Interpretation:** no specification beats the coin flip on the refreshed
holdout. The AUC is 0.477 with 85 games and 42 positives, so the point estimate
is not evidence of skill in either direction.

### 5.2 Calibration

| Holdout bin | n | Mean prediction | Observed |
|---|---:|---:|---:|
| < 0.40 | 15 | 34.1% | 33.3% |
| 0.40–0.45 | 8 | 42.1% | 75.0% |
| 0.45–0.50 | 17 | 47.8% | 70.6% |
| 0.50–0.55 | 18 | 52.6% | 38.9% |
| 0.55–0.60 | 13 | 57.3% | 38.5% |
| > 0.60 | 14 | 65.4% | 50.0% |

The holdout is overconfident at the high end and underconfident in the
0.40–0.50 band. With 85 games the bins are small and the curve is indicative,
not precise.

### 5.3 Coefficient stability

All 90% bootstrap intervals include zero:

| Feature | Standardized coefficient | 5th percentile | 95th percentile |
|---|---:|---:|---:|
| Win rate | −0.349 | −0.820 | +0.144 |
| GD@10 | −0.145 | −0.431 | +0.151 |
| End-game gold diff | +0.400 | −0.057 | +0.884 |
| Kill diff | +0.026 | −0.427 | +0.509 |
| Objective composite | +0.143 | −0.318 | +0.617 |

The features are highly collinear (up to 0.94 among win rate, gold diff, kill
diff and objectives). Individual coefficient signs must not be interpreted
causally.

## 6. Validated case study (HLE vs IG, 2026-10-25)

The first registered forecast has been played and scored under the
pre-registered rules.

| Item | Value |
|---|---|
| Pre-registered probability | HLE 43.9% / IG 56.1% (CI 37.2%–51.6%) |
| Result | **IG won** (blue side), 29–9 kills, +9,252 gold, 28.6 min, patch 16.20 |
| Brier score | **0.1924** (coin flip 0.2500) |
| Log loss | **0.5774** (coin flip 0.6931) |
| Correct pick | **Yes** |

One observation. It beat the coin-flip baselines on that match, but the
holdout is still at chance, so the model is **not** validated. Full write-up:
[`reports/validated_forecast_hle_vs_ig.md`](validated_forecast_hle_vs_ig.md).

## 7. Limitations

1. **Partial sample:** last-50-game seeding, expanded by opponents' lists.
2. **No side confirmation:** the primary model is side-neutral; side is a scenario.
3. **No head-to-head for the current fixture:** LYON and IG have not played in the sample.
4. **No draft/roster/patch/player features:** the model is form-only.
5. **Collinearity:** the five features overlap heavily; coefficients are unstable.
6. **Small test set:** 85 games, 42 positives. Metrics have wide sampling error.
7. **Distribution shift:** training base rate 61.7% team_a wins vs 49.4% in the test fold.
8. **Stage aggregates:** event objective rates are not game-level features.
9. **Series conversion is a simplification:** independent games, constant per-game probability.
10. **No market comparison:** the model is not benchmarked against betting odds.

## 8. Ethical and operational considerations

- Do not present the output as a certain forecast. The interval contains 50%.
- Do not use the model for wagering or financial decisions.
- Do not infer player quality or causality from coefficients.
- Disclose the data cutoff and the pre-match status whenever the prediction is shown.
- Score every forecast against the pre-registered rules; do not tune on outcomes.
- If the model is refreshed, version the data cutoff and the code commit.

## 9. Maintenance

- **Refresh cadence:** after each match day during Worlds.
- **Monitoring:** rolling Brier score, log loss, calibration slope and AUC over the last 20–40 matches.
- **Retraining:** retrain only after enough new matches (suggest 20+) and always with a chronological split.
- **Feature expansion:** consider side, draft, roster, patch, player-level gold/xp and market-implied probabilities.
- **Kill criteria:** if rolling AUC stays below 0.52 over 40+ matches, keep the model as a descriptive baseline and do not present it as a predictive edge.

## 10. Reproducibility

```bat
python src\run_pipeline.py
```

Outputs:

- `data/processed/prediction_summary.json`
- `data/processed/fixture_predictions.csv` (the full slate)
- `data/processed/model_comparison.csv`
- `data/processed/model_coefficients.csv`
- `data/processed/model_calibration.csv`
- `data/processed/scenario_analysis.csv`
- `data/processed/validation_report.json`

Environment: Python 3.12.10, pandas 3.1.0, numpy 2.5.4, scikit-learn 1.9.1, matplotlib 3.11.2, requests 2.34.2.
