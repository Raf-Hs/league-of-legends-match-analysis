# Model Card — HLE vs IG Pre-Match Model

## 1. Model overview

| Item | Detail |
|---|---|
| Model name | HLE vs IG pre-match form model |
| Version | 1.0 |
| Date | 2026-10-25 |
| Type | L2-regularized logistic regression |
| Target | Probability that team_a (blue side in historical data) wins |
| Primary use | Pre-match probability estimate for a single Bo1 |
| Output | P(HLE win) = 43.9%, P(IG win) = 56.1% |
| Uncertainty | 90% bootstrap interval for HLE: 37.2%–51.6% |
| Training sample | 174 games between Worlds 2026 teams |
| Holdout | 72 games, chronological |
| Holdout AUC | 0.494 |
| Holdout Brier | 0.255 (coin flip: 0.250) |
| Holdout log loss | 0.703 (coin flip: 0.693) |

## 2. Intended use

**Intended:**

- Demonstrate a reproducible, leakage-controlled analytics pipeline.
- Provide a structured, transparent pre-match probability estimate.
- Quantify uncertainty and show why a single Bo1 is hard to predict.
- Serve as a baseline for post-match validation and future feature work.

**Not intended:**

- Betting, wagering, or financial decisions.
- Roster, contract, or scouting decisions.
- Claims about player quality or causality.
- High-confidence forecasting. The holdout does not support that.

## 3. Data

### 3.1 Source

Oracle's Elixir public API, the same data that powers `oracleselixir.com`. The CSV download was unavailable (Google Drive quota exceeded). The API fallback is recorded in `data/raw/collection_manifest.json`.

### 3.2 Sample construction

- 16 Worlds 2026 teams, up to 50 recent games each.
- 636 unique completed games, 1,272 team-game rows.
- 222 games between two Worlds teams.
- 174 modelling games after requiring at least five prior games and complete features.
- No target-match leakage: match `115660540726095045` is absent from the fact and model tables.

### 3.3 Features

| Feature | Definition | Window |
|---|---|---|
| `wr_10_diff` | team_a win rate − team_b win rate | last 10 games |
| `gd10_10_diff` | team_a mean GD@10 − team_b mean GD@10 | last 10 games |
| `gold_diff_10_diff` | team_a mean final gold diff − team_b mean final gold diff | last 10 games |
| `kd_diff_10_diff` | team_a mean kill diff − team_b mean kill diff | last 10 games |
| `obj_10_diff` | team_a mean objective composite − team_b mean objective composite | last 10 games |

Objective composite = tower diff + dragon diff + 2 × baron diff.

All features are pre-game. Rolling features are shifted so the current game is excluded. The target match's features are computed from the last 10 games before the cutoff.

### 3.4 Why GD@10, not GD@15

The API does not expose GD@15. GD@10 is the sum of five players' `gxd10` and is used as a clearly labeled proxy. It is not identical to GD@15 and may understate or overstate early-game control depending on lane assignments and game state.

## 4. Modelling

### 4.1 Split

- **Train:** games before 2026-09-01 — 102 games (2026-06-30 to 2026-08-30).
- **Test:** games from 2026-09-02 to 2026-10-25 — 72 games.
- No shuffling. No future information in training.

### 4.2 Estimator

- Standardize features on the training fold only.
- L2 logistic regression, `C=0.5`, `fit_intercept=False`, `max_iter=5000`.
- Why no intercept: every historical `team_a` is blue side, but the target side is unconfirmed. An intercept would encode the training period's blue-side rate. The model is side-neutral; side is handled as a scenario.
- `C=0.5` was fixed before evaluating the holdout. A sensitivity check over C is reported in `data/processed/scenario_analysis.csv` and the model comparison table.

### 4.3 Prediction

The target vector is HLE minus IG:

| Feature | Value |
|---|---:|
| Win rate diff | 0.0 |
| GD@10 diff | +745.6 |
| End-game gold diff | −1,654.7 |
| Kill diff diff | +0.5 |
| Objective composite diff | −2.0 |

The model output is **43.9% HLE**.

## 5. Performance

### 5.1 Holdout metrics

| Model | Features | AUC | Brier | Log loss | Accuracy |
|---|---:|---:|---:|---:|---:|
| Coin flip | 0 | 0.500 | 0.250 | 0.693 | 45.8% |
| Win rate only | 1 | 0.506 | 0.254 | 0.701 | 47.2% |
| Core 4 | 4 | 0.493 | 0.255 | 0.704 | 47.2% |
| **Core 5 (primary)** | **5** | **0.494** | **0.255** | **0.703** | **47.2%** |
| 8-feature | 8 | 0.487 | 0.254 | 0.702 | 45.8% |

**Interpretation:** the model does not beat the coin flip on Brier or log loss. The AUC is essentially 0.50. The 95% confidence interval for AUC on 72 games is wide; a point estimate of 0.494 is not evidence of skill.

### 5.2 Calibration

| Holdout bin | n | Mean prediction | Observed |
|---|---:|---:|---:|
| < 0.40 | 13 | 35.1% | 23.1% |
| 0.40–0.45 | 7 | 42.2% | 71.4% |
| 0.45–0.50 | 15 | 47.6% | 60.0% |
| 0.50–0.55 | 16 | 52.5% | 43.8% |
| 0.55–0.60 | 11 | 57.2% | 45.5% |
| > 0.60 | 10 | 64.4% | 40.0% |

The holdout is overconfident at the high end and underconfident in the 0.40–0.50 range. With 72 games, these bins are small and the curve is indicative, not precise.

### 5.3 Coefficient stability

All 90% bootstrap intervals include zero:

| Feature | Standardized coefficient | 5th percentile | 95th percentile |
|---|---:|---:|---:|
| Win rate | −0.410 | −0.895 | +0.052 |
| GD@10 | −0.127 | −0.409 | +0.186 |
| End-game gold diff | +0.197 | −0.291 | +0.690 |
| Kill diff | +0.181 | −0.258 | +0.662 |
| Objective composite | +0.279 | −0.200 | +0.754 |

The features are highly collinear (0.83–0.94 among the first four performance features). Individual coefficient signs should not be interpreted causally.

## 6. Limitations

1. **Partial sample:** last-50-game seeding, expanded by opponents' lists. Not a complete season game graph.
2. **No side confirmation:** the primary model is side-neutral. Side is a scenario, not a feature.
3. **No head-to-head:** HLE and IG did not play in the collected sample.
4. **No draft/roster/player features:** the model is form-only.
5. **Collinearity:** the five features overlap heavily; coefficients are unstable.
6. **Small test set:** 72 games, 33 positives. Metrics have wide sampling error.
7. **Distribution shift:** training base rate 60.8% team_a wins; test base rate 45.8%. This is a large temporal shift and contributes to the model's poor calibration.
8. **Stage aggregates:** event objective rates are not game-level features.
9. **Bo1 variance:** a single game is inherently high-variance.
10. **No market comparison:** the model is not benchmarked against betting odds.

## 7. Ethical and operational considerations

- Do not present the output as a certain forecast. The interval includes 50%.
- Do not use the model for wagering or financial decisions.
- Do not infer player quality or causality from coefficients.
- Disclose the data cutoff and the pre-match status whenever the prediction is shown.
- Recompute the model after the match and log the result; do not tune on a single outcome.
- If the model is refreshed, version the data cutoff and the code commit.

## 8. Maintenance

- **Refresh cadence:** after each match day during Worlds.
- **Monitoring:** rolling Brier score, log loss, calibration slope, and AUC over the last 20–40 matches.
- **Retraining:** retrain only after enough new matches (suggest 20+) and always with a chronological split.
- **Feature expansion:** consider side, draft, roster, patch, player-level gold/xp, and market-implied probabilities if available.
- **Kill criteria:** if rolling AUC stays below 0.52 over 40+ matches, keep the model as a baseline and do not present it as a predictive edge.

## 9. Reproducibility

```bat
python src\run_pipeline.py
```

Outputs:

- `data/processed/prediction_summary.json`
- `data/processed/model_comparison.csv`
- `data/processed/model_coefficients.csv`
- `data/processed/model_calibration.csv`
- `data/processed/scenario_analysis.csv`
- `data/processed/validation_report.json`

Environment: Python 3.12.10, pandas 3.1.0, numpy 2.5.4, scikit-learn 1.9.1, matplotlib 3.11.2, requests 2.34.2.
