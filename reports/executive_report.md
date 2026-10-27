# Executive report — LYON vs IG, Worlds 2026 Swiss Day 5

**Prepared:** 2026-10-27 00:30 UTC (more than two days before the 2026-10-28 23:00 UTC start)
**Data cutoff:** 2026-10-27 00:00 UTC
**Match:** LYON (2024 American Team) vs Invictus Gaming — **best of 3**
**Block:** Worlds 2026, Swiss Day 5 · **Oracle's Elixir match ID:** `115660540726095065`
**Status at collection:** `unstarted`

> This report replaces the pre-match note for the 25 October fixture, which has
> already been played and **scored**: see
> [`validated_forecast_hle_vs_ig.md`](validated_forecast_hle_vs_ig.md) (HLE vs
> IG, 25 Oct: forecast HLE 43.9% / IG 56.1% → **IG won**, Brier 0.1924 vs a
> 0.250 coin flip, pick correct — one observation, not a validation).

---

## 1. Executive summary

**The call:** **IG 58.6% / LYON 41.4% per game** under the primary side-neutral
model, and **IG 62.8% / LYON 37.2%** if the series is converted to a best of
three under the stated independence assumption. The 90% bootstrap interval for
LYON is **33.5%–48.9%**, so the interval still contains 50%.

**Why the lean to IG:** IG is materially better at the end of games and at
objectives. Over the last 10 games IG's end-game gold difference is **+1,064**
against LYON's **−2,127** (a 3,192 swing), and the objective composite is
**+2.0 vs −1.7**. LYON's compensating edge is early: it is ahead on GD@10
(−396 vs −488) and first blood (40% vs 20%), but those leads are not being
converted — its last-10 GD@10 is still negative.

**Why you should not over-trust it:** the refreshed chronological holdout is
**worse than a coin flip**, not better. On 85 unseen games the primary model
scores **AUC 0.477, Brier 0.259, log loss 0.712** against coin-flip baselines of
0.250 and 0.693, and picks correctly only 42.4% of the time. The honest
conclusion is a close-to-even series with a modest IG lean, and the number to
quote is the interval, not the point estimate.

**Decision recommendation:** if a single directional call is required, take
**IG**, size the confidence as low, and treat the Wednesday slate as
unpredictable at the match level. Do not use this model as a stand-alone
betting or selection tool.

---

## 2. Match context

| Item | Detail |
|---|---|
| Fixture | LYON (2024 American Team) vs Invictus Gaming |
| Start | 2026-10-28 23:00 UTC (Swiss Day 5, second match of the day) |
| Format | **Best of 3** — the first two Swiss fixtures in this feed were best of 1; every remaining fixture is best of 3 |
| Worlds 2026 record | LYON 3–2 (5 games) · IG 2–1 (3 games) |
| Last series | LYON lost 1–2 to Gen.G on 25 Oct (elimination-round decider) · IG beat HLE 29–9 on 25 Oct |
| Head-to-head in sample | **None** — LYON and IG have not met in the collected data |
| Rest | LYON ~3.0 days · IG ~3.2 days |
| Patch | 16.20 for both teams' Worlds games |
| The other Wednesday fixture | Movistar KOI vs T1, 20:00 UTC — model: **49.5% / 50.5%**, i.e. a coin flip |

---

## 3. Data and method

### 3.1 Data

- **Source:** Oracle's Elixir public API (the same data that powers `oracleselixir.com`).
- **Coverage:** 16 Worlds 2026 teams, **630** unique completed games, **1,260** team-game rows, seeded with each team's last 50 games and expanded by opponents' lists.
- **Cutoff:** every feature uses only games started before **2026-10-27 00:00 UTC**. The target match is excluded and validated as absent.
- **Sampling caveat:** the union is not a complete season graph (LYON 53 games, IG 50 in the sample).

### 3.2 Model

- **Sample:** 226 games between Worlds teams; **179** with ≥5 prior games per side and complete features.
- **Split:** chronological. Train = 94 games before 2026-09-01; test = **85** games from 2026-09-02 to 2026-10-26.
- **Features (primary, 5):** last-10 differences in win rate, GD@10, end-game gold diff, kill differential, objective composite.
- **Estimator:** L2 logistic regression, standardized features, `C=0.5`, **no intercept** (side-neutral, because the side assignment is unknown pre-match).
- **Uncertainty:** 1,000-draw bootstrap of the full 179-game modelling sample.
- **Best-of-3 conversion:** `P(series) = p² · (3 − 2p)`, i.e. the probability of winning at least 2 of 3 games, assuming games are independent and the per-game probability is constant (no side or draft adaptation). Stated as a simplification, not a model of Bo3 dynamics.

---

## 4. Evidence

### 4.1 Form is level, the profiles are not

| Window | LYON | IG |
|---|---:|---:|
| Last 5 | 2–3 (40%) | 4–1 (80%) |
| Last 10 | 5–5 (50%) | 5–5 (50%) |
| Last 20 | — see `team_kpis.csv` | — |
| vs Worlds teams (sample) | 17–10 (63.0%) | 8–9 (47.1%) |
| Worlds 2026 Main Event | 3–2 (5 games) | 2–1 (3 games) |

### 4.2 LYON is better early, IG is better late

| Last-10 metric | LYON | IG | Edge |
|---|---:|---:|---|
| GD@10 | **−396** | **−488** | LYON +92 |
| First-blood rate | **40%** | **20%** | LYON +20 pp |
| End-game gold diff | **−2,127** | **+1,064** | **IG +3,192** |
| Kill differential | −1.2 | −0.1 | IG +1.1 |
| Objective composite | −1.7 | **+2.0** | **IG +3.7** |
| Average duration | 32.5 min | 32.5 min | Tie |
| Strength of schedule | 0.80 | 0.57 | LYON faced harder opposition |

**Read:** both teams are negative on GD@10, so neither side is reliably ahead
at 10 minutes. The separation comes at the other end of the map: IG closes
games with more gold and more objectives. LYON's early edge is real but small
and it does not show up in its end-game numbers — the profile of a team that
wins skirmishes and loses the map.

### 4.3 Form index

The descriptive last-10 form index (mean z-score of win rate, gold diff, kill
diff and objective score) ranks **IG 9th of 16** and **LYON 14th of 16**.

### 4.4 Event-level profile (context only, never a model input)

| Event | Team | GP | W–L | GSPD | EGR | MLR | FB% | FT% | FD% | DRG% | BN% |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Worlds 2026 Main Event | LYON | 5 | 3–2 | −2.1% | 40.0 | +20.0 | 20 | 40 | 40 | 43 | 80 |
| Worlds 2026 Main Event | IG | 3 | 2–1 | −0.3% | 70.1 | −3.5 | 67 | 100 | 67 | 58 | 33 |
| MSI 2026 | LYON | 17 | 11–6 | +0.4% | 50.8 | +13.9 | 53 | 76 | 41 | 25 | 45 |
| LPL 2026 Grand Finals | IG | 20 | 14–6 | +5.2% | 81.1 | +2.2 | 69 | 75 | 60 | 57 | 58 |

LYON's Worlds sample is the stronger of the two on barons (80% vs 33%) and on
MLR, but IG's is much better on first tower (100% vs 40%) and first blood. The
samples are tiny (5 and 3 games) and therefore anecdotal.

---

## 5. Prediction and uncertainty

### 5.1 Primary output

| | LYON | IG |
|---|---:|---:|
| Per game | **41.4%** | **58.6%** |
| 90% bootstrap interval (LYON, per game) | **33.5%–48.9%** | — |
| Best of 3 series (independence assumption) | **37.2%** | **62.8%** |
| Series interval (LYON) | 26.1%–48.3% | — |

### 5.2 Model comparison (85-game chronological holdout)

| Model | Features | Holdout AUC | Brier | Log loss | Accuracy |
|---|---:|---:|---:|---:|---:|
| **Coin flip** | 0 | 0.500 | **0.250** | **0.693** | **49.4%** |
| Win rate only | 1 | 0.476 | 0.257 | 0.707 | 47.1% |
| Core 4 | 4 | 0.478 | 0.259 | 0.712 | 42.4% |
| **Core 5 (primary)** | **5** | **0.477** | **0.259** | **0.712** | **42.4%** |
| 8-feature sensitivity | 8 | 0.458 | 0.262 | 0.717 | 40.0% |

**Every specification is at or worse than the coin flip on the refreshed
holdout.** With more data the picture got slightly *worse* (AUC 0.477 vs 0.494
on the previous 72-game holdout), which is what an honest refit looks like: the
model was never carrying skill, and the extra games confirm it. This is the
most important finding in the report.

### 5.3 Why the model leans IG

Target feature contributions to the primary model's log-odds:

| Feature | LYON − IG | Standardized value | Coefficient | Log-odds contribution | Effect |
|---|---:|---:|---:|---:|---|
| End-game gold diff | −3,192 | −0.67 | +0.400 | **−0.269** | Pushes LYON down |
| Objective composite | −3.7 | −0.80 | +0.143 | **−0.114** | Pushes LYON down |
| Kill differential | −1.1 | −0.31 | +0.026 | −0.008 | Slight |
| GD@10 | +92 | +0.04 | −0.145 | −0.005 | Neutral |
| Recent win rate | 0.0 | −0.14 | −0.349 | +0.048 | Slightly up |
| **Net** | | | | **−0.348** | **P(LYON) = 41.4%** |

The negative GD@10 coefficient is a collinearity artefact: win rate, gold
difference, kill difference and objective score correlate up to **0.94**, and
all individual 90% bootstrap intervals include zero. Read the waterfall as a
description of this fixture, not as causal evidence.

### 5.4 Scenarios

| Scenario | P(LYON) | P(IG) | Interpretation |
|---|---:|---:|---|
| Coin flip | 50.0% | 50.0% | No-information baseline |
| **Primary (core 5)** | **41.4%** | **58.6%** | Side-neutral, no intercept |
| Core 4 | 42.6% | 57.4% | Drops objective composite |
| 8-feature sensitivity | 41.5% | 58.5% | Adds FB, duration, SOS |
| Win-rate only | 49.8% | 50.2% | Form-only baseline |
| LYON blue-side prior | 47.2% | 52.8% | Adds the observed 55.9% blue-side rate |
| LYON red-side prior | 35.8% | 64.2% | Adds the observed 44.1% red-side rate |
| Neutralize IG's edges | 49.3% | 50.7% | Zeroes every feature where IG leads |
| Neutralize LYON's edges | 41.6% | 58.4% | Zeroes every feature where LYON leads |

**Side assignment matters as much as the form signal.** If LYON is blue the
call is nearly even; if LYON is red, IG is a clear favourite. The side is not
published pre-match, and the match record's `team1 = LYON` must not be
assumed to mean blue.

### 5.5 The full Wednesday slate

| Start (UTC) | Fixture | Per game | 90% CI (team 1) | Bo3 series | Lean |
|---|---|---:|---:|---:|---|
| 2026-10-28 20:00 | Movistar KOI vs T1 | 50.9% / 49.1% | 41.6%–60.1% | 51.4% / 48.6% | Coin flip |
| 2026-10-28 23:00 | **LYON vs IG** | **41.4% / 58.6%** | **33.5%–48.9%** | **37.2% / 62.8%** | IG |

---

## 6. What would change the call

1. **Confirmed side assignment.** LYON blue → 47.2%; LYON red → 35.8%. This is the single largest sensitivity and it is not in the data yet.
2. **Draft.** The model is draft-agnostic. A decisive early-game or scaling draft could move the true probability by more than the form signal.
3. **Patch.** A patch change would weaken the relevance of the last-10 sample (both teams' Worlds games are on 16.20).
4. **IG's recent map control.** If IG's end-game gold edge is a one-match artefact rather than a trend, the estimate converges to ~49% for LYON (the "neutralize IG's edges" scenario).
5. **Market odds.** The model is not calibrated against a market. A liquid market is likely a better probability estimate than a 187-game form model whose holdout is at chance.

---

## 7. Limitations and risks

- **Weak holdout:** AUC 0.477 and Brier 0.259 vs 0.250 coin flip. The model is a structured baseline, not a reliable predictor.
- **Bo3 conversion is a simplification:** it assumes independent games with a constant per-game probability, and no adaptation between games.
- **No head-to-head:** LYON and IG have not met in the sample.
- **Partial data:** last-50-game seeding, not a complete season graph.
- **Collinearity:** the five features overlap heavily; coefficient signs are unstable.
- **Small test set:** 85 games, 42 positives; metric uncertainty is wide.
- **No side confirmation:** the primary model is side-neutral by design.
- **Stage aggregates:** event objective rates are not game-level features.
- **Bo1 → Bo3 shift:** the model was trained on games, and the target is a series. The per-game probability is the model's native output; the series number is derived.
- **No betting recommendation:** this is an analytics exercise, not financial advice.

---

## 8. Post-match validation

The prediction is pre-registered in `powerbi/post_match_validation_log.csv`
(row `115660540726095065`, registered 2026-10-27). The rules are in
[`post_match_validation_plan.md`](post_match_validation_plan.md) and are
applied by:

```bat
python src\score_match.py --winner LYON|iG --side blue|red --patch 16.20
```

Expected single-game scores under the primary model: Brier **0.3432** if LYON
wins, **0.1960** if IG wins (coin flip 0.2500). One series is one observation;
the running log is the evidence.

---

## 9. Artifact index

| Artifact | Path |
|---|---|
| Cleaned team-game fact | `data/processed/fact_team_games.csv` |
| Game dimension | `data/processed/dim_games.csv` |
| Rolling team form | `data/processed/team_form.csv` |
| Model dataset | `data/processed/model_dataset.csv` |
| Team KPIs | `data/processed/team_kpis.csv` |
| Match KPIs | `data/processed/match_kpis.csv` |
| Target features | `data/processed/target_match_features.csv` |
| **Slate features** | `data/processed/fixture_features.csv` |
| **Slate predictions** | `data/processed/fixture_predictions.csv` |
| Model comparison | `data/processed/model_comparison.csv` |
| Coefficients | `data/processed/model_coefficients.csv` |
| Calibration | `data/processed/model_calibration.csv` |
| Prediction summary | `data/processed/prediction_summary.json` |
| Scenarios | `data/processed/scenario_analysis.csv` |
| Feature contributions | `data/processed/target_feature_contributions.csv` |
| Validation report | `data/processed/validation_report.json` |
| Charts | `figures/01_*.png` … `figures/10_*.png` |
| Power BI tables | `data/powerbi/*.csv` |
| Power BI guide | `powerbi/dashboard_guide.md` |
| DAX measures | `powerbi/dax_measures.md` |
| Validated case study | `reports/validated_forecast_hle_vs_ig.md` |
