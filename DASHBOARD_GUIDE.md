# Power BI dashboard — build guide (HLE/IG → LYON/IG project)

This is the top-level entry point for the Power BI deliverable. The full
detail (import steps, data types, relationships, every visual's field wells,
accessibility and troubleshooting) lives in
[`powerbi/dashboard_guide.md`](powerbi/dashboard_guide.md). The copy-paste DAX
is in [`powerbi/dax_measures.md`](powerbi/dax_measures.md) and the colour
theme in [`powerbi/theme.json`](powerbi/theme.json).

## Design (inspired by a dark executive dashboard)

- **Canvas:** 1280 × 720, 16:9.
- **Theme:** dark charcoal (`#1A1A1D` background, `#252529` containers), orange
  (`#FF6B35`) as the primary accent and blue (`#2D7FF9`) as the secondary
  accent, light-gray text. Import `powerbi/theme.json` via
  **View → Themes → Browse for themes**.
- **Preview:** `figures/dashboard_preview.png` is a static mockup of the
  intended layout (KPI cards across the top, analytical charts in a compact
  grid, key-findings panel on the side, slate and caveats at the bottom). It is
  a portfolio preview only — the interactive report is assembled in Power BI
  Desktop from the 20 CSVs.

## Sections of the report

1. **Executive Summary** (the single-page executive view) — 6 KPI cards
   (Total Matches, Unique Teams, Competition Stages, Test Matches, ROC-AUC,
   Brier Score), the model-range bar, the scenario table, the model-comparison
   table, and a caveat banner.
2. **Team Performance** — rolling win rate and GD@10, last-10 rates and gold
   profile, objective composite, form index by team, and a window matrix.
3. **Match History** — head-to-head (0), recent games table, gold-diff trend,
   early-vs-late scatter, wins by opponent, event profile, side balance.
4. **Prediction & Validation** — prediction, uncertainty, specification
   range, feature contributions, coefficients, calibration, model comparison,
   validation status, and the method note.

## Data model (9 relationships)

`DimDate` → `FactTeamGame` / `FactTeamForm` · `DimTeam` → `FactTeamGame` /
`FactTeamForm` / `FactTeamEventStat` / `FactTeamKPI` / `FactTargetFeature` ·
`DimGame` → `FactTeamGame` / `FactTeamForm`. The slate, prediction, scenario,
model and validation tables are deliberately unconnected (presentation tables).

## KPIs (dataset scale vs model performance)

| KPI | Source | Notes |
|---|---|---|
| Total Matches Analyzed | `DISTINCTCOUNT(FactTeamGame[oe_game_id]) / 2` | 630 |
| Unique Teams | `DISTINCTCOUNT(FactTeamGame[team])` | 57 (16 in the Worlds cohort) |
| Competition Stages | `DISTINCTCOUNT(FactTeamGame[tournament])` | — |
| Test Matches | `MAX(FactPrediction[test_games])` | 85 |
| Train Matches | `MAX(FactPrediction[train_games])` | 94 |
| Modelling Games | `MAX(FactPrediction[sample_games])` | 179 |
| ROC-AUC | `Holdout AUC` (primary model) | 0.477 |
| Brier Score | `Holdout Brier` | 0.259 |
| Log Loss | `Holdout Log Loss` | 0.712 |
| Accuracy | `Holdout Accuracy` | 42.4% |

Dataset KPIs and model-performance KPIs are deliberately separated so the
dashboard does not imply that a model metric is a dataset property.

## Model evaluation (verified against the pipeline)

| Model | ROC-AUC | Brier | Log loss | Accuracy |
|---|---:|---:|---:|---:|
| Coin flip | 0.500 | 0.250 | 0.693 | 49.4% |
| Win-rate only | 0.476 | 0.257 | 0.707 | 47.1% |
| Core 4 | 0.478 | 0.259 | 0.712 | 42.4% |
| **Core 5 (primary)** | **0.477** | **0.259** | **0.712** | **42.4%** |
| 8 features | 0.458 | 0.262 | 0.717 | 40.0% |

These values were reconciled against `data/processed/model_comparison.csv` and
`prediction_summary.json` by `src/validate_outputs.py` (72/72 checks).

## Filters and interactions

Slicers: `DimTeam[team]`, `DimDate[year_month]`, `DimTeam[is_worlds_cohort]`,
`DimGame[patch]`. Fixed holdout metrics live on their own page and do not
respond to the match slicer, so historical filtering cannot silently change
the evaluation result.

## Validation

- 72/72 automated checks pass (`python src\validate_outputs.py`).
- Dashboard totals reconcile to `data/processed/fact_team_games.csv`
  (1,260 rows = 2 × 630 games).
- No duplicate matches, no incorrect aggregation, no hardcoded example
  findings — every insight panel is generated from `data/processed/*`.
- The model evaluation metrics match the verified report exactly.

## Limitations

- No native `.pbix` is produced (Power BI Desktop was not controlled by this
  project). The deliverable is the CSVs + theme + DAX + this guide, which
  assemble into the report in 60–90 minutes.
- The preview PNG is a static mockup, not the interactive report.
- The model has no demonstrated skill above chance on the holdout; the
  dashboard communicates this honestly rather than hiding it.
- The Bo3 series probability is a derived quantity (independence assumption),
  not a model output — it is labeled as such everywhere it appears.

## Refresh

1. Update `COLLECTION_CUTOFF_UTC`, `TARGET_MATCH_START_UTC`,
   `TARGET_MATCH_ID`, `TEAM_A`/`TEAM_B` and `UPCOMING_FIXTURES` in
   `src/config.py`.
2. `python src\run_pipeline.py --refresh` (needs `OE_API_KEY` in the
   environment).
3. Refresh the report; the 19 CSVs are rewritten in place.
4. Re-run `python src\validate_outputs.py` (must report 72/72).
