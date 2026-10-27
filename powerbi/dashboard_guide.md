# Power BI build guide — HLE vs IG, Worlds 2026

Step-by-step instructions for assembling the four-page report from the 16
star-schema CSVs in `data/powerbi/`.

> **No `.pbix` is included.** Power BI Desktop cannot be scripted from this
> project, so the report is delivered as data + this guide + the DAX measure
> list in `dax_measures.md` + the theme in `theme.json`. Expect 60–90 minutes
> to build it by hand; every visual is specified below with its field wells.

---

## 0. Prerequisites

- Power BI Desktop (Windows) — free download, no licence needed for the build.
- `data/powerbi/` populated by the pipeline:
  ```bat
  python src\run_pipeline.py
  ```
- Optional: `powerbi/theme.json` and `powerbi/dax_measures.md` from this folder.

## 1. Import the data

**Get Data → Text/CSV** and load each file in `data/powerbi/`. When the file
picker opens, select all 19 CSVs at once and press *Open* — Power BI loads
each as a separate query.

| Query | Rows | Grain |
|---|---:|---|
| `DimDate` | 175 | one row per calendar date |
| `DimTeam` | 57 | one row per team (16 flagged `is_worlds_cohort = 1`) |
| `DimGame` | 630 | one row per game |
| `DimMetric` | 23 | one row per documented KPI |
| `FactTeamGame` | 1,260 | one row per team per game |
| `FactTeamForm` | 1,260 | one row per team per game, pre-game rolling form |
| `FactTeamKPI` | 16 | one row per Worlds team (5/10/20 windows) |
| `FactMatchKPI` | 103 | one row per KPI/window/event |
| `FactTargetFeature` | 34 | one row per team per metric (last-10 snapshot) |
| `FactTeamEventStat` | 800 | one row per team per event |
| `FactPrediction` | 5 | one row per model specification |
| `FactFixturePrediction` | 2 | one row per upcoming fixture (the slate) |
| `FactFixtureFeature` | 2 | the pre-game feature vector behind each slate row |
| `FactValidationLog` | 2 | one row per pre-registered prediction and its score |
| `FactScenario` | 9 | one row per scenario |
| `FactModelMetric` | 5 | one row per model (holdout metrics) |
| `FactModelCoefficient` | 18 | one row per model × feature |
| `FactModelCalibration` | 24 | one row per sample × probability bin |
| `FactFeatureContribution` | 5 | one row per primary-model feature |

**Do not** use the *Folder* connector: it will try to combine the CSVs into a
single table because the schemas differ.

## 2. Data types (Power Query)

Select each query → *Transform Data* → set the types:

| Column | Type | Applies to |
|---|---|---|
| `date` | Date | DimDate, DimGame, FactTeamGame, FactTeamForm |
| `date_key` | Whole number | all fact and dim tables |
| `match_start_utc`, `generated_at_utc`, `scored_at_utc` | Date/Time | FactPrediction, PostMatchValidationLog |
| `win`, `is_hle`, `is_ig`, `is_target_team`, `is_worlds_cohort`, `is_primary`, `is_key_event`, `first_blood` | Whole number | all |
| `p_hle`, `p_ig`, `bootstrap_p05`, `bootstrap_p50`, `bootstrap_p95`, `holdout_accuracy`, `holdout_brier`, `holdout_log_loss`, `holdout_auc` | Decimal number | FactPrediction |
| `brier_score`, `log_loss`, `predicted_p_hle`, `predicted_p_ig` | Decimal number | PostMatchValidationLog |
| `oe_game_id`, `match_id`, `team`, `opponent` | Text | all |

Leave everything else on *Detect*. Load, then **Close & Apply**.

## 3. Relationships

Delete every auto-detected relationship first (**Model → Manage relationships
→ cancel all**, then create the ones below). `DimDate` can otherwise be
auto-detected twice against the same fact tables.

| From (1) | To (many) | Cross-filter | Active |
|---|---|---|---|
| `DimDate[date_key]` | `FactTeamGame[date_key]` | Single | Yes |
| `DimDate[date_key]` | `FactTeamForm[date_key]` | Single | Yes |
| `DimTeam[team]` | `FactTeamGame[team]` | Single | Yes |
| `DimTeam[team]` | `FactTeamForm[team]` | Single | Yes |
| `DimTeam[team]` | `FactTeamEventStat[team]` | Single | Yes |
| `DimTeam[team]` | `FactTeamKPI[team]` | Single | Yes |
| `DimTeam[team]` | `FactTargetFeature[team]` | Single | Yes |
| `DimGame[oe_game_id]` | `FactTeamGame[oe_game_id]` | Single | Yes |
| `DimGame[oe_game_id]` | `FactTeamForm[oe_game_id]` | Single | Yes |

**Deliberately unconnected** (they are presentation tables and would create
ambiguous paths): `FactMatchKPI`, `FactPrediction`, `FactScenario`,
`FactModelMetric`, `FactModelCoefficient`, `FactModelCalibration`,
`FactFeatureContribution`, `FactFixturePrediction`, `FactFixtureFeature`,
`FactValidationLog`, `DimMetric`.

### Hide these columns

Right-click → *Hide in report view*: `DimDate[date_key]`, `DimGame[match_id]`,
`DimGame[game_in_match]`, `FactTeamGame[gd10_players]`, `FactTeamGame[match_id]`,
`FactTeamGame[oe_game_id]`, `FactTeamForm[oe_game_id]`, `FactTeamKPI[first_game_utc]`.

### Sort by column

- `DimDate[month_name]` → sort by `DimDate[month]`.
- `DimDate[day_name]` → sort by `DimDate[day_of_week]`.
- `DimMetric[metric]` → sort by `DimMetric[metric]` (alphabetical) unless you
  want business order — the table has no explicit order column, so add one in
  Power Query if you need a fixed sequence.

## 4. Theme

**View → Themes → Browse for themes** → select `powerbi/theme.json`.

| Role | Colour |
|---|---|
| HLE / primary accent | `#D97706` (amber) |
| IG / secondary accent | `#2563EB` (blue) |
| Positive | `#059669` (green) |
| Negative | `#DC2626` (red) |
| Neutral / warning | `#D97706` (amber) |
| Background / cards | `#FFFFFF` |
| Border | `#E5E7EB` |

Pin the two team colours to the HLE and IG series in every visual (**Format →
Data colours → Customize**) so the colour means the same thing on all four
pages.

---

## 5. Page 1 — Executive Summary

**Canvas:** 1280 × 720, page background `#FFFFFF`.

| # | Visual | Type | Field wells |
|---|---|---|---|
| 1 | *P(Team A)* | Card | Values `Primary P (Team A)` |
| 2 | *P(Team B)* | Card | Values `Primary P (Team B)` |
| 3 | *Lean* | Card | Values `Predicted Lean` |
| 4 | *90% interval* | Card | Values `Bootstrap Low (Team A)`, `Bootstrap Mid (Team A)`, `Bootstrap High (Team A)` — set *Concatenate* |
| 5 | *Holdout AUC* | Card | Values `Holdout AUC`, plus a text box underneath: `Coin Flip AUC` |
| 6 | *Holdout Brier* | Card | Values `Holdout Brier`, plus `Coin Flip Brier` |
| 7 | *Model range* | Clustered bar | Axis `FactPrediction[model]`, Values `FactPrediction[p_team_a]`; add a constant line at 0.50 (**Analytics → Constant line**) |
| 7b | *Match slate* | Table | Rows `FactFixturePrediction[match_label]`, Values `FactFixturePrediction[p_team_a_game]`, `FactFixturePrediction[p_team_b_game]`, `FactFixturePrediction[p_team_a_bo3]`, `FactFixturePrediction[bootstrap_p05]`, `FactFixturePrediction[bootstrap_p95]` |
| 8 | *Scenario table* | Table | Rows `FactScenario[scenario]`, Values `Scenario P (HLE)`, `Scenario P (IG)`, `FactScenario[note]` |
| 9 | *Model comparison* | Table | Rows `FactModelMetric[model]`, Values `FactModelMetric[accuracy]`, `FactModelMetric[brier]`, `FactModelMetric[log_loss]`, `FactModelMetric[auc]` |
| 10 | *Caveat banner* | Text box | See text below |

**Text box (visual 10) — copy verbatim:**

```
Pre-match forecast — LYON vs Invictus Gaming, Worlds 2026 Swiss Day 5, best of 3.
Start 2026-10-28 23:00 UTC · Data cutoff 2026-10-27 00:00 UTC · Oracle's Elixir match 115660540726095065 (state: unstarted at collection).

Primary model: LYON 41.4% / IG 58.6% per game · 37.2% / 62.8% as a best of 3.
90% bootstrap interval for LYON: 33.5%–48.9%.

Honest read: on the 85-game chronological holdout the model does not beat a coin
flip (AUC 0.477, Brier 0.259 vs 0.250, log loss 0.712 vs 0.693).
Treat this as close to even with a marginal IG lean, not a confident forecast.
```

**Formatting notes**

- Card 1 and 2: amber and blue respectively, 28 pt callout values.
- Cards 5 and 6 must show the coin-flip baseline *next to* the model value —
  a Brier score without its baseline is meaningless.
- On visual 7, colour the `Core 5 (primary)` bar in amber and the rest in grey.

## 6. Page 2 — Team Performance

**Slicers (top of page):** `DimTeam[team]` (multi-select), `DimDate[year_month]`
(optional), `DimTeam[is_worlds_cohort]` (default: *is* 1).

| # | Visual | Type | Field wells |
|---|---|---|---|
| 1 | *LYON record* | Card | `LYON Last 10 Wins`, `LYON Last 10 Losses` (concatenate as "W–L") |
| 2 | *IG record* | Card | `IG Last 10 Wins`, `IG Last 10 Losses` |
| 3 | *LYON vs IG form rank* | Card | `LYON Form Rank (last 10)`, `IG Form Rank (last 10)` |
| 4 | *Rolling win rate* | Line chart | Axis `FactTeamForm[date]`, Values `Rolling Win Rate (10)`, Legend `DimTeam[team]`; filter `DimTeam[is_target_team] = 1` |
| 5 | *Rolling GD@10* | Line chart | Axis `FactTeamForm[date]`, Values `Rolling GD10 (10)`, Legend `DimTeam[team]`, same filter |
| 6 | *Last-10 rates* | Clustered bar | Axis `FactTargetFeature[metric]` (filter to `win_rate`, `first_blood_rate`), Legend `FactTargetFeature[team]`, Values `FactTargetFeature[value]`; filter `FactTargetFeature[window] = "last10"` |
| 7 | *Last-10 gold profile* | Clustered bar | Axis `FactTargetFeature[metric]` (filter to `gd10`, `gold_diff`), Legend `FactTargetFeature[team]`, Values `FactTargetFeature[value]` |
| 8 | *Objective composite* | Bar chart | Axis `FactTargetFeature[metric]` (filter to `objective_score`), Legend `FactTargetFeature[team]`, Values `FactTargetFeature[value]` |
| 9 | *Form index by team* | Bar chart | Axis `DimTeam[team]`, Values `FactTeamKPI[form_index_last10]`; filter `DimTeam[is_worlds_cohort] = 1`, sort descending |
| 10 | *Window matrix* | Matrix | Rows `DimTeam[team]`, Values `FactTeamKPI[last5_win_rate]`, `FactTeamKPI[last10_win_rate]`, `FactTeamKPI[last20_win_rate]`, `FactTeamKPI[last10_gold_diff]`, `FactTeamKPI[last10_gd10]` |

**Formatting notes**

- Set a zero line on visuals 6–8 and let the axis cross at 0 so "better" is
  visible at a glance.
- Use the theme colours: HLE amber, IG blue.
- Add a caption to each chart stating the window, e.g. *"Last 10 games ending
  2026-10-25 16:20 UTC"*.

## 7. Page 3 — Match History

| # | Visual | Type | Field wells |
|---|---|---|---|
| 1 | *Head-to-head* | Card | `Head-to-Head Games` (expected value: **0**) |
| 2 | *Recent games* | Table | `FactTeamGame[date]`, `FactTeamGame[team]`, `FactTeamGame[opponent]`, `FactTeamGame[side]`, `FactTeamGame[win]`, `FactTeamGame[duration_min]`, `FactTeamGame[gold_diff]`, `FactTeamGame[gd10]`, `FactTeamGame[objective_score]`; filter `DimTeam[is_target_team] = 1`, sort by `date` descending, keep 20 rows |
| 3 | *Gold diff over time* | Line chart | Axis `FactTeamGame[date]`, Values `FactTeamGame[gold_diff]`, Legend `DimTeam[team]`; filter `DimTeam[is_target_team] = 1` |
| 4 | *Early vs late game* | Scatter | X `FactTeamGame[gd10]`, Y `FactTeamGame[gold_diff]`, Legend `DimTeam[team]`, Size `FactTeamGame[gold]`, Details `FactTeamGame[date]`, `FactTeamGame[opponent]`; filter `DimTeam[is_target_team] = 1` |
| 5 | *Wins by opponent* | Clustered bar | Axis `FactTeamGame[opponent]`, Values `Wins`; filter `DimTeam[is_target_team] = 1`, Top N = 10 |
| 6 | *Event profile* | Matrix | Rows `FactTeamEventStat[event]`, Columns `FactTeamEventStat[team]`, Values `FactTeamEventStat[first_tower_pct]`, `FactTeamEventStat[first_dragon_pct]`, `FactTeamEventStat[baron_pct]`; filter `FactTeamEventStat[is_key_event] = 1` |
| 7 | *Side balance* | Card | `Blue Side Win Rate` with the note *"blue-side win rate across the 636-game sample"* |

**Formatting notes**

- Visual 4 is the money visual on this page: HLE's points sit high on the X
  axis (early gold) and low on the Y axis (end-game gold), IG's the reverse.
- Visual 6 needs a caption: *"OE stage aggregates — context only, never model
  inputs."*
- Sort visual 6 by `FactTeamEventStat[event]` alphabetically, then move the
  two target teams to the top manually if desired.

## 8. Page 4 — Prediction & Validation

| # | Visual | Type | Field wells |
|---|---|---|---|
| 1 | *Prediction* | Card | `Primary P (Team A)`, `Primary P (Team B)`, `Predicted Lean` |
| 2 | *Uncertainty* | Card | `Bootstrap Low (Team A)`, `Bootstrap High (Team A)` (concatenate as a range) |
| 2b | *Series (Bo3)* | Card | `Target Series Probability (Bo3)`, `Target Series Interval (Low)`, `Target Series Interval (High)` |
| 3 | *Specification range* | Clustered bar | Axis `FactPrediction[model]`, Values `FactPrediction[p_team_a]`, constant line 0.50 |
| 4 | *Feature contributions* | Waterfall | Category `FactFeatureContribution[label]`, Values `FactFeatureContribution[log_odds_contribution]`; add a "Total" category using `Total Log-Odds Contribution` |
| 5 | *Coefficients* | Clustered bar | Axis `FactModelCoefficient[label]`, Values `Coefficient`; filter `FactModelCoefficient[model] = "M3_core5"`; tooltip `Coefficient Low (90%)`, `Coefficient High (90%)` |
| 6 | *Calibration* | Scatter | X `FactModelCalibration[mean_pred]`, Y `FactModelCalibration[observed]`, Size `FactModelCalibration[n]`, Legend `FactModelCalibration[sample]`; filter `sample` to `holdout_primary_core5` |
| 7 | *Model comparison* | Table | Rows `FactModelMetric[model]`, Values `FactModelMetric[accuracy]`, `FactModelMetric[brier]`, `FactModelMetric[log_loss]`, `FactModelMetric[auc]`, `FactModelMetric[n]` |
| 8 | *Validation status* | Card | `Result Status`, `Scored Matches`, `Running Brier Score` |
| 8b | *Validation log* | Table | Rows `FactValidationLog[match_label]`, Values `FactValidationLog[predicted_p_team_a]`, `FactValidationLog[actual_winner]`, `FactValidationLog[brier_score]`, `FactValidationLog[log_loss]`, `FactValidationLog[correct_pick]` |
| 9 | *Method note* | Text box | See text below |

**Text box (visual 9):**

```
Primary model: L2 logistic regression, C = 0.5, no intercept (side-neutral), 5 features
(last-10 differences in win rate, GD@10, end-game gold diff, kill diff, objective composite).
Train 94 games before 2026-09-01 · Test 85 games from 2026-09-02 · 1,000-draw bootstrap.
Best-of-3 series probability = p² · (3 − 2p): independent games, constant per-game probability.

Coefficients are unstable: all 90% bootstrap intervals include zero and the
performance features correlate up to 0.94. Read the waterfall as a description
of this fixture, not as causal evidence.
```

**Formatting notes**

- Visual 6: a perfect model sits on the 45° line. Add a constant line on Y at
  0.5 and note the diagonal in a caption, because Power BI cannot draw a
  diagonal reference line without a helper table.
- Visual 5: colour negative coefficients red, positive blue — but state in the
  caption that the signs are not causal.
- Visual 4: the total is **−0.348 log-odds → 41.4%**.

## 9. Accessibility

1. Add alt text to every visual (right-click → *Alt text*). Minimum: what the
   visual shows and the one takeaway, e.g. *"Clustered bar of each model's
   probability for HLE. Core 5 is lowest at 43.9%."*
2. Never encode a result with colour alone — keep the data labels on.
3. The theme's amber/blue pair is colour-blind safe; do not swap in red/green
   for win/loss.
4. Keep the reading order logical (top-left to bottom-right) and tab through
   the visuals; do not place a decorative visual before the headline cards.
5. Font sizes: card values 28 pt, titles 12 pt semibold, body ≥ 9 pt.

## 10. Post-match refresh

1. Score the match:
   ```bat
   python src\score_match.py --winner iG --side blue|red
   ```
2. The row in `powerbi/post_match_validation_log.csv` is filled in with the
   winner, the Brier score, the log loss and whether the pick was correct.
3. Re-run the pipeline so `data/powerbi/FactValidationLog.csv` is refreshed
   (`python src\run_pipeline.py`), then refresh the report; the *Validation
   status* card flips from **Pending** to **Scored**.
4. Update `reports/model_card.md` with the observation — **one match is one
   observation**, not a validation.

## 11. Data refresh after a new match day

1. Update `COLLECTION_CUTOFF_UTC` and `TARGET_MATCH_START_UTC` in `src/config.py`.
2. `python src\run_pipeline.py --refresh` (needs `OE_API_KEY` in the environment).
3. The 19 CSVs in `data/powerbi/` are rewritten in place — open the report and
   hit **Refresh**; no rebinding is needed as long as the file names and
   column names are unchanged.
4. Re-check the target-match exclusion: `python src\validate_outputs.py` must
   report 56/56.

## 12. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Date slicer empty | `date_key` imported as Text | Set `date_key` to Whole number |
| Two relationships between DimDate and the facts | auto-detected duplicates | Cancel auto-detected relationships, recreate the list in §3 |
| Card shows blank | measure depends on a relationship you did not create | create it, or check the filter context |
| `DimTeam` shows only 16 teams | the dimension intentionally covers all 57 observed teams | filter `is_worlds_cohort = 1` for the cohort view |
| Team code for IG looks wrong (`iG`) | that is Oracle's Elixir spelling | filter on `DimTeam[team]` instead |
| `Avg GD10` differs from the reports | `AVERAGE` skips the 84 rows without `gxd10` | expected; the reports use the same rule |
| `FactMatchKPI` cannot be joined to a team | it is a wide comparison table with no team key | use it on its own page without a relationship |
| `FactFixturePrediction` will not join to `DimTeam` | the slate is a presentation table keyed by match, not by team | filter with `FactFixturePrediction[match_label]` instead |
