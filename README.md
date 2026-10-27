# Esports match analytics & win-probability model — Worlds 2026

A reproducible, end-to-end business-analytics project that forecasts
professional *League of Legends* matches, registers the forecast **before** the
match, scores it afterwards, and publishes the whole thing as Power BI-ready
tables.

| Item | Value |
|---|---|
| Current target | **LYON (2024 American Team) vs Invictus Gaming** — best of 3 |
| Event | Worlds 2026, Swiss Day 5 |
| Scheduled start | **2026-10-28 23:00 UTC** |
| Data cutoff | **2026-10-27 00:00 UTC** |
| Match state at collection | `unstarted` |
| Oracle's Elixir match ID | `115660540726095065` |
| Validated case study | HLE vs IG, 2026-10-25 — **scored** (see below) |

## Headline prediction

> **IG 58.6% / LYON 41.4% per game** under the primary side-neutral model;
> **IG 62.8% / LYON 37.2%** if the series is converted to a best of three
> (independence assumption). 90% bootstrap interval for LYON: **33.5%–48.9%**.
> The refreshed holdout is **worse than a coin flip** (AUC 0.477, Brier 0.259
> vs 0.250, log loss 0.712 vs 0.693, 85 games). **The model provides no
> statistically reliable edge.** The honest call is a close series with a
> modest IG lean, and the number to quote is the interval, not the point
> estimate.

The value of this project is the reproducible pipeline, the KPI framework, the
uncertainty quantification, the pre-registration discipline and the fact that
the weak signal is reported rather than hidden.

## Validated case study — the first forecast was scored

| | |
|---|---|
| Pre-registered (2026-10-25 16:47 UTC) | HLE **43.9%** / IG **56.1%**, pick IG |
| Result | **IG won** (blue side) 29–9, +9,252 gold, 28.6 min, patch 16.20 |
| Brier | **0.1924** vs 0.2500 coin flip |
| Log loss | **0.5774** vs 0.6931 coin flip |
| Correct pick | **Yes** |

The forecast beat both coin-flip baselines on that match. It is still **one
observation**: the holdout remains at chance, so the model is not validated.
Full write-up: [`reports/validated_forecast_hle_vs_ig.md`](reports/validated_forecast_hle_vs_ig.md).

## Business problem and objectives

A pre-match decision has to be made before the game starts: which side of the
match to take, how much confidence to attach, and what evidence would change
the call. Public esports data is plentiful but usually presented as raw
leaderboards — win/loss tables with no idea of how strong the opposition was,
no statement of uncertainty, and no way to check whether the predictor would
have been right.

**Objectives**

1. Build a **decision-grade match forecast** from a public, reproducible data
   source, with the information set frozen at a stated cutoff.
2. Define a **KPI framework** for the cohort — **23 documented metric
   definitions** covering win rate, GD@10, end-game gold difference, kill
   differential, objective composite, first-blood rate, strength of schedule,
   rest days, form index and event objective rates.
3. **Quantify the uncertainty** rather than presenting a point estimate, and
   test the model honestly on a chronological holdout.
4. Deliver an **auditable artefact set** — model card, data-quality log,
   executive report, Power BI-ready tables and a **pre-registered** post-match
   scoring rule — so each forecast can be judged rather than admired.

**Non-objective, stated up front:** this is not a betting model. The holdout
result (AUC ≈ 0.47–0.49) is reported as the headline finding, not buried.

## What is in the project

```
league-of-legends-match-analysis/
├── src/
│   ├── config.py              constants, teams, cutoff, paths (no secrets)
│   ├── collect_data.py        Oracle's Elixir API collection
│   ├── build_dataset.py       cleaning, rolling form, model dataset
│   ├── kpis.py                team/match KPIs, target snapshot, slate features
│   ├── model.py               chronological model, bootstrap, calibration, slate
│   ├── visualizations.py      10 portfolio charts
│   ├── export_powerbi.py      star-schema CSVs for Power BI
│   ├── validate_outputs.py    71 mechanical checks (incl. secret scan)
│   ├── score_match.py         scores the finished match into the validation log
│   └── run_pipeline.py        one-command orchestration
├── data/
│   ├── raw/                   raw API responses + collection manifest
│   ├── processed/             cleaned analysis tables and model outputs
│   └── powerbi/               19 Power BI-ready star-schema CSV tables
├── figures/                   10 PNG charts (200 dpi)
├── powerbi/
│   ├── dashboard_guide.md     page-by-page build instructions (4 pages)
│   ├── dax_measures.md        copy-paste DAX measures
│   ├── theme.json             Power BI colour theme
│   └── post_match_validation_log.csv   pre-registered predictions + results
├── reports/
│   ├── executive_report.md
│   ├── model_card.md
│   ├── data_quality_log.md
│   ├── post_match_validation_plan.md
│   └── validated_forecast_hle_vs_ig.md
├── requirements.txt
└── README.md
```

## Quick start

Windows PowerShell / Command Prompt:

```bat
cd C:\ruta\a\league-of-legends-match-analysis
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

REM Reproduce from the cached raw data (recommended, no API key needed)
python src\run_pipeline.py

REM Or re-fetch from Oracle's Elixir first (needs OE_API_KEY in the environment)
python src\run_pipeline.py --refresh
```

Copy `.env.example` if you prefer a file-based setup — the key is never
committed (`.env` is git-ignored, and the pipeline fails if a literal secret
appears in the source).

The pipeline runs:

1. `build_dataset.py` — cleans 1,260 team-game rows, adds pre-game rolling form, builds the 226-game intra-Worlds model table.
2. `kpis.py` — computes last-5/10/20 KPIs, event aggregates, the target snapshot and the feature vector for every fixture on the next match day.
3. `model.py` — fits the chronological model, bootstraps uncertainty, writes calibration, scenarios and the slate.
4. `visualizations.py` — writes the 10 charts in `figures/`.
5. `export_powerbi.py` — writes the star-schema tables in `data/powerbi/`.
6. `validate_outputs.py` — runs 71 checks including target-match leakage, slate consistency and a hardcoded-secret scan.

Expected final validation: **71/71 checks passed**.

## Data

**Primary source:** the public Oracle's Elixir API that powers `oracleselixir.com`.
**Why not the CSV?** The Oracle's Elixir downloadable CSV was unavailable during collection because the Google Drive quota was exceeded. The API fallback is documented in `data/raw/collection_manifest.json` and `reports/data_quality_log.md`.

**Collection:**

- 16 Worlds 2026 teams, up to 50 recent games per team.
- **630** unique completed games, **1,260** team-game rows, 57 teams in total.
- Game details, team event aggregates, and the upcoming-match record.
- Every game used as a feature starts before **2026-10-27 00:00 UTC**.
- The target match `115660540726095065` is explicitly excluded and validated as absent.

**Important sampling caveat:** team histories are not complete season data. They are seeded with each team's last 50 games and expanded by opponents' lists (LYON has 56 games in the union, IG 51). This is sufficient for last-5/10/20 form, but it is not a complete league-wide game graph.

## Methodology

### Cleaning

- One row per team per game, with mirrored blue/red rows.
- Winner validation, duplicate checks, unpaired-game checks.
- Timezone-aware UTC timestamps and a strict collection cutoff.
- `LYON` is normalised to `LYON (2024 American Team)` because the game-detail feed and team-stats endpoint use different labels. Without this fix, LYON games silently disappear from the model.

### KPIs

| KPI | Definition | Direction |
|---|---|---|
| Win rate | wins / games in window | Higher |
| GD@10 | mean sum of five players' `gxd10` | Higher |
| End-game gold diff | mean final gold difference | Higher |
| Kill differential | mean kills − deaths | Higher |
| Objective composite | mean tower diff + dragon diff + 2 × baron diff | Higher |
| First-blood rate | share of games with first blood | Higher |
| Strength of schedule | mean opponent pre-game 10-game win rate | Context |
| Event objective rates | OE stage aggregates (FB%, FT%, FD%, DRG%, BN%) | Context |

`GD@15` is not exposed by the API. `GD@10` is used as a clearly labeled proxy. Event-level objective rates are stage aggregates, not game-level features; they are never fed into the model.

### Model

- **Unit:** one game between two Worlds teams, 2026 sample.
- **Target:** `team_a_win` (team_a is the blue-side team in the historical feed).
- **Features (primary, 5):** last-10 differences in win rate, GD@10, end-game gold diff, kill differential, objective composite.
- **Sample:** 226 intra-Worlds games; **179** with ≥5 prior games per side and complete features.
- **Split:** chronological. Train = 94 games before 2026-09-01; test = 85 games from 2026-09-02.
- **Estimator:** L2 logistic regression, standardized features, `C=0.5`, **no intercept**.
- **Why no intercept:** every historical `team_a` is blue side, but the target match's side assignment is not confirmed. An intercept would bake the training period's blue-side rate into a match where side is unknown. The model is therefore side-neutral; a separate scenario adds the observed 55.9% blue-side rate as a prior.
- **Best-of-3 conversion:** `P(series) = p² · (3 − 2p)`, assuming independent games with a constant per-game probability. Stated as a simplification.
- **Uncertainty:** 1,000-draw bootstrap of the full 179-game modelling sample.
- **Sensitivity:** 4-feature, 5-feature, and 8-feature specifications; side-prior scenarios; neutralizing each team's edges.

## Key findings

1. **Both teams are 5–5 in their last 10.** The win-rate feature contributes nothing (difference = 0.0).
2. **LYON is slightly better early.** Last-10 GD@10: LYON **−396** vs IG **−488**; first blood 40% vs 20%.
3. **IG is much better late and on objectives.** Last-10 end-game gold: IG **+1,064** vs LYON **−2,127** (a 3,192 swing). Objective composite: IG **+2.0** vs LYON **−1.7**.
4. **Neither team leads on GD@10.** Both are negative, so "early advantage" is relative, not absolute.
5. **LYON has the tougher schedule** (SOS 0.80 vs IG 0.57) and the better top-16 record (17–10 vs 8–9).
6. **There are no LYON vs IG head-to-head games** in the collected 2026 sample.
7. **The refreshed holdout is worse than a coin flip.** AUC 0.477, Brier 0.259 vs 0.250, log loss 0.712 vs 0.693 on 85 games (42 positives). This is the most important finding for decision-making.

## Prediction

| Specification | P(LYON) | P(IG) |
|---|---:|---:|
| Coin flip | 50.0% | 50.0% |
| Win-rate only | 49.8% | 50.2% |
| Core 4 | 42.6% | 57.4% |
| **Core 5 (primary)** | **41.4%** | **58.6%** |
| 8-feature sensitivity | 41.5% | 58.5% |

Primary 90% bootstrap interval for LYON: **33.5%–48.9%**. As a best of 3: **37.2% / 62.8%**.

The model leans IG because IG's end-game gold difference and objective composite outweigh LYON's early gold edge. The coefficient on GD@10 is negative, which is counterintuitive and a symptom of severe collinearity (up to 0.94 among win rate, gold diff, kill diff and objectives). All 90% bootstrap intervals for individual coefficients include zero. Do not read the coefficients causally.

**If LYON is confirmed blue side**, the estimate moves to **47.2% LYON**. **If LYON is red side**, to **35.8%**. Side assignment matters as much as the form signal.

### The rest of the slate

| Start (UTC) | Fixture | Per game | Bo3 series | Read |
|---|---|---:|---:|---|
| 2026-10-28 20:00 | Movistar KOI vs T1 | 50.9% / 49.1% | 51.4% / 48.6% | coin flip |
| 2026-10-28 23:00 | LYON vs IG | 41.4% / 58.6% | 37.2% / 62.8% | marginal IG lean |

## Business recommendation

**Decision recommendation:** treat Wednesday's slate as **close to even**. If a
single directional call is required for LYON vs IG, take **IG**, size the
confidence as low and document the uncertainty. Do not use this model as a
stand-alone betting or selection tool — the holdout evidence (AUC 0.477,
Brier 0.259 vs 0.250) does not support a reliable edge, and no coefficient
should be read causally.

The full decision framing, including what would change the call (confirmed
side assignment, patch-level form update), is in
[`reports/executive_report.md`](reports/executive_report.md).

## Power BI

The `data/powerbi/` folder contains **19 star-schema tables** (`DimTeam`,
`DimGame`, `DimDate`, `DimMetric` and 15 fact tables) that load directly into
Power BI Desktop.

- [`powerbi/dashboard_guide.md`](powerbi/dashboard_guide.md) — import steps, data types, the 9 relationships, and the exact field wells for all four pages: **Executive Summary, Team Performance, Match History, Prediction & Validation**.
- [`powerbi/dax_measures.md`](powerbi/dax_measures.md) — 70+ copy-paste DAX measures, formatting strings and the gotchas that break the report.
- [`powerbi/theme.json`](powerbi/theme.json) — the colour theme (HLE/IG amber `#D97706`, IG blue `#2563EB`, colour-blind safe).

> **No native `.pbix` file is included.** Power BI Desktop was not controlled by this project. The CSVs, theme, DAX and build guide let you assemble the report manually in Power BI Desktop.

## Reports

- [`reports/executive_report.md`](reports/executive_report.md) — decision-oriented summary of the current fixture.
- [`reports/model_card.md`](reports/model_card.md) — intended use, performance, limitations, maintenance plan.
- [`reports/validated_forecast_hle_vs_ig.md`](reports/validated_forecast_hle_vs_ig.md) — the pre-registered forecast, the observed result and the score of the first fixture.
- [`reports/data_quality_log.md`](reports/data_quality_log.md) — sources, target verification, cleaning rules, missingness, defects and their fixes, audit trail.
- [`reports/post_match_validation_plan.md`](reports/post_match_validation_plan.md) — the pre-registered rules for scoring every fixture.
- `data/processed/data_quality_report.json` — the machine-readable twin of the data-quality log, regenerated on every pipeline run.

## Refresh instructions

1. Update `COLLECTION_CUTOFF_UTC`, `TARGET_MATCH_START_UTC`, `TARGET_MATCH_ID`, `TEAM_A`/`TEAM_B` and the `UPCOMING_FIXTURES` list in `src/config.py`.
2. Run `python src\run_pipeline.py --refresh` (requires `OE_API_KEY` in the environment; the cached path needs no key).
3. Rebuild the Power BI report from `data/powerbi/` (or refresh the data source).
4. Register the new forecast in `powerbi/post_match_validation_log.csv` **before** the match, and score it afterwards:
   `python src\score_match.py --winner <código> --side blue|red`.

### API key (never stored in this repository)

The Oracle's Elixir key is read from the environment only — there is no
hard-coded fallback anywhere in the code:

```bat
REM Windows PowerShell
$env:OE_API_KEY = "<your key>"

REM Windows cmd
set OE_API_KEY=<your key>
```

- The default pipeline (`python src\run_pipeline.py`) reproduces everything from the cached raw data and **needs no key at all**.
- Only `--refresh` calls the live API, and it warns loudly when `OE_API_KEY` is missing.
- `.env` and `.env.*` are git-ignored, and `validate_outputs.py` fails the build if a literal key/token/secret appears in the source tree (check 56: *"no hardcoded secrets in source"*).

## Next steps

1. **Score the Wednesday fixture against the pre-registered rules.** The row for `115660540726095065` was registered on 2026-10-27, before the 2026-10-28 23:00 UTC start. Run `python src\score_match.py --winner iG|LYON --side blue|red`, then update `reports/model_card.md`. One series is one observation, not a validation.
2. **Build the Power BI report by hand** from `powerbi/dashboard_guide.md` — the tables, DAX and theme are ready; only the `.pbix` assembly is left, and that needs Power BI Desktop.
3. **Strengthen the model before the next fixture.** The features are collinear (up to 0.94) and the holdout is at or below chance: add side assignment, draft and roster signals, widen the sample beyond the last-50 seeding, and re-tune on a rolling window before trusting any edge.
4. **Re-collect with `--refresh`** for the next match day and keep the cutoff discipline, so every forecast stays pre-registered.

## Limitations

- **Partial sample:** last-50-game seeding, not complete season data.
- **No target side:** blue/red assignment is not confirmed pre-match.
- **No draft, roster, patch-specific, or player-level features.**
- **Weak holdout:** AUC ≈ 0.48; the model is a structured baseline, not a betting model.
- **Collinearity:** the five form features overlap heavily.
- **Small test set:** 85 games, 42 positives; metrics have wide sampling error.
- **Stage aggregates:** event objective rates are not game-level features.
- **Bo3 conversion is a simplification:** independent games, constant per-game probability.
- **Single series:** variance is large; even a good model would be uncertain.
- **No head-to-head:** LYON and IG did not play in the collected sample.

## Artifact checklist

- [x] Raw data + collection manifest
- [x] Cleaned CSVs (fact, dim, form, model dataset, slate)
- [x] Reproducible Python pipeline
- [x] KPI definitions and team/match KPIs
- [x] Chronological model with holdout metrics
- [x] Bootstrap uncertainty, scenario analysis and the full slate
- [x] 10 charts
- [x] Power BI star-schema CSVs (19 tables)
- [x] Executive report, model card, data quality log
- [x] Pre-registered post-match validation plan + scoring script
- [x] Rendered data-quality log (plus the machine-readable JSON twin)
- [x] Power BI build guide, DAX measures and colour theme
- [x] One forecast scored end to end (HLE vs IG, 2026-10-25)
- [x] 71/71 validation checks (including the hardcoded-secret scan)
- [ ] Native `.pbix` (requires Power BI Desktop; not generated)
- [ ] Post-match result for the Wednesday fixture (row is pre-registered and pending)
