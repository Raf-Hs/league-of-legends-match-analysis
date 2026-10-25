# Esports match analytics & win-probability model — HLE vs IG, Worlds 2026

A reproducible, end-to-end business-analytics project for the **Hanwha Life Esports (HLE) vs Invictus Gaming (IG)** best-of-one at **Worlds 2026 Swiss Day 3**.

| Item | Value |
|---|---|
| Match | HLE vs IG |
| Event | Worlds 2026, Swiss Day 3 |
| Format | Best of 1 |
| Scheduled start | **2026-10-25 17:00 UTC** |
| Data cutoff | **2026-10-25 16:20 UTC** |
| Match state at collection | `unstarted` |
| Oracle's Elixir match ID | `115660540726095045` |

## Headline prediction

> **IG 56.1% / HLE 43.9%** under the primary side-neutral model.
> 90% bootstrap interval for HLE: **37.2%–51.6%**.
> The holdout AUC is **0.494** and the Brier score is **0.255** versus a 0.250 coin-flip baseline. **The model does not provide a statistically reliable edge.** The honest match call is close to a coin flip, with a slight lean to IG driven by objective control and end-game gold difference.

This project deliberately reports the weak predictive signal instead of hiding it. The value is in the reproducible pipeline, the KPI framework, the uncertainty quantification, and the post-match validation plan.

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
2. Define a **KPI framework** for two professional teams — **23 documented
   metric definitions** covering win rate, GD@10, end-game gold difference,
   kill differential, objective composite, first-blood rate, strength of
   schedule, rest days, form index and event objective rates.
3. **Quantify the uncertainty** rather than presenting a point estimate, and
   test the model honestly on a chronological holdout.
4. Deliver an **auditable artefact set** — model card, data-quality log,
   executive report, Power BI-ready tables and a pre-registered post-match
   scoring rule — so the forecast can be judged rather than admired.

**Non-objective, stated up front:** this is not a betting model. The holdout
result (AUC ≈ 0.50) is reported as the headline finding, not buried.

## What is in the project

```
league-of-legends-match-analysis/
├── src/
│   ├── config.py              constants, teams, cutoff, paths (no secrets)
│   ├── collect_data.py        Oracle's Elixir API collection
│   ├── build_dataset.py       cleaning, rolling form, model dataset
│   ├── kpis.py                team/match KPIs + target snapshot
│   ├── model.py               chronological model, bootstrap, calibration
│   ├── visualizations.py      10 portfolio charts
│   ├── export_powerbi.py      star-schema CSVs for Power BI
│   ├── validate_outputs.py    56 mechanical checks (incl. secret scan)
│   ├── score_match.py         scores the finished match into the validation log
│   └── run_pipeline.py        one-command orchestration
├── data/
│   ├── raw/                   raw API responses + collection manifest
│   ├── processed/             cleaned analysis tables and model outputs
│   └── powerbi/               16 Power BI-ready star-schema CSV tables
├── figures/                   10 PNG charts (200 dpi)
├── powerbi/
│   ├── dashboard_guide.md     page-by-page build instructions (4 pages)
│   ├── dax_measures.md        copy-paste DAX measures
│   ├── theme.json             Power BI colour theme
│   └── post_match_validation_log.csv   pre-registered prediction + result row
├── reports/
│   ├── executive_report.md
│   ├── model_card.md
│   ├── data_quality_log.md
│   └── post_match_validation_plan.md
├── requirements.txt
└── README.md
```

The 16 star-schema CSVs in `data/powerbi/` load directly into Power BI
Desktop; `powerbi/dashboard_guide.md` specifies the relationships, the four
report pages and the field wells of every visual.

## Quick start

Windows PowerShell / Command Prompt:

```bat
cd C:\ruta\a\league-of-legends-match-analysis
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

REM Reproduce from the cached raw data (recommended)
python src\run_pipeline.py

REM Or re-fetch from Oracle's Elixir first (needs OE_API_KEY in the environment)
python src\run_pipeline.py --refresh
```

Copy `.env.example` if you prefer a file-based setup — the key is never
committed (`.env` is git-ignored, and the pipeline fails if a literal secret
appears in the source).

The pipeline runs:

1. `build_dataset.py` — cleans 1,272 team-game rows, adds pre-game rolling form, builds the 222-game intra-Worlds model table.
2. `kpis.py` — computes last-5/10/20 KPIs, event aggregates, and the target-match feature snapshot.
3. `model.py` — fits the chronological model, bootstraps uncertainty, writes calibration and scenario outputs.
4. `visualizations.py` — writes the 10 charts in `figures/`.
5. `export_powerbi.py` — writes the star-schema tables in `data/powerbi/`.
6. `validate_outputs.py` — runs 56 checks including target-match leakage and a hardcoded-secret scan.

Expected final validation: **56/56 checks passed**.

### API key (never stored in this repository)

The Oracle's Elixir key is read from the environment only. There is no
hard-coded fallback anywhere in the code:

```bat
REM Windows PowerShell
$env:OE_API_KEY = "<your key>"

REM Windows cmd
set OE_API_KEY=<your key>
```

- The default pipeline (`python src\run_pipeline.py`) reproduces everything
  from the cached raw data and **needs no key at all**.
- Only `--refresh` calls the live API, and it warns loudly when
  `OE_API_KEY` is missing.
- `.env` and `.env.*` are git-ignored, and `validate_outputs.py` fails the
  build if any literal key/token/secret is found in the source tree
  (check 56: *"no hardcoded secrets in source"*).

## Data

**Primary source:** the public Oracle's Elixir API that powers `oracleselixir.com`.
**Why not the CSV?** The Oracle's Elixir downloadable CSV was unavailable during collection because the Google Drive quota was exceeded. The API fallback is documented in `data/raw/collection_manifest.json` and `reports/data_quality_log.md`.

**Collection:**

- 16 Worlds 2026 teams, up to 50 recent games per team.
- 636 unique completed games, 1,272 team-game rows.
- Game details, team event aggregates, and the upcoming-match record.
- Every game used in a feature starts before **2026-10-25 16:20 UTC**.
- The target match `115660540726095045` is explicitly excluded and validated as absent.

**Important sampling caveat:** team histories are not complete season data. They are seeded with each team's last 50 games and expanded by opponents' lists (which is why HLE has 65 games in the union and IG has 50). This is sufficient for last-5/10/20 form, but it is not a complete league-wide game graph.

## Methodology

### Cleaning

- One row per team per game, with mirrored blue/red rows.
- Winner validation, duplicate checks, unpaired-game checks.
- Timezone-aware UTC timestamps.
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
- **Split:** chronological. Train = games before 2026-09-01 (102 games); test = 2026-09-02 onward (72 games).
- **Estimator:** L2 logistic regression, standardized features, `C=0.5`, **no intercept**.
- **Why no intercept:** every historical `team_a` is blue side, but the target match's side assignment is not confirmed. An intercept would bake the training period's blue-side rate into a match where side is unknown. The model is therefore side-neutral; a separate scenario adds the observed 54.6% blue-side rate as a prior.
- **Uncertainty:** 1,000-draw bootstrap of the full 174-game modelling sample.
- **Sensitivity:** 4-feature, 5-feature, and 8-feature specifications; C sensitivity; side-prior scenarios; neutralizing each team's main edge.

## Key findings

1. **Both teams are 5–5 in their last 10.** HLE is 10–10 in its last 20; IG is 12–8.
2. **HLE has the better early game.** Last-10 GD@10: HLE **+202** vs IG **−544**. HLE also has a 70% first-blood rate vs IG's 10%.
3. **IG has the better end-game and objective profile.** Last-10 end-game gold diff: IG **+757** vs HLE **−898**. Objective composite: IG **+2.6** vs HLE **+0.6**.
4. **HLE has the stronger top-16 résumé.** Against the 16 Worlds teams in the sample, HLE is **34–22 (60.7%)**; IG is **7–9 (43.8%)**. This is not in the primary model, which uses last-10 form only.
5. **Both teams sit in the bottom third of the descriptive last-10 form index.** HLE is 14th of 16; IG is 12th.
6. **There are no HLE vs IG head-to-head games** in the collected 2026 sample.
7. **The model's holdout performance is not better than a coin flip.** AUC 0.494, Brier 0.255 vs 0.250, log loss 0.703 vs 0.693. This is the most important finding for decision-making.

## Prediction

| Specification | P(HLE) | P(IG) |
|---|---:|---:|
| Coin flip | 50.0% | 50.0% |
| Win-rate only | 49.7% | 50.3% |
| Core 4 | 45.6% | 54.4% |
| **Core 5 (primary)** | **43.9%** | **56.1%** |
| 8-feature sensitivity | 44.6% | 55.4% |

Primary 90% bootstrap interval for HLE: **37.2%–51.6%**.

The model leans IG because IG's objective composite and end-game gold difference outweigh HLE's early gold edge. However, the coefficient on GD@10 is negative, which is counterintuitive and a symptom of severe collinearity (0.83–0.94 among win rate, gold diff, kill diff, and objectives). All 90% bootstrap intervals for individual coefficients include zero. Do not read the coefficients causally.

**If HLE is confirmed blue side**, adding the observed 54.6% blue-side rate as a prior moves the estimate to **48.4% HLE**. **If HLE is red side**, it moves to **39.4% HLE**. Side assignment matters more than the form signal.

## Business recommendation

**Decision recommendation:** treat this as a **coin-flip match with a marginal
IG edge**. If a decision requires a single directional call, take **IG**, but
size the confidence as low and document the uncertainty. Do not use this model
as a stand-alone betting or selection tool — the holdout evidence
(AUC 0.494, Brier 0.255 vs 0.250) does not support a reliable edge, and no
coefficient should be read causally.

The full decision framing, including what would change the call (confirmed
side assignment, a patch-level form update), is in
[`reports/executive_report.md`](reports/executive_report.md).

## Power BI

The `data/powerbi/` folder contains **16 star-schema tables** (`DimTeam`,
`DimGame`, `DimDate`, `DimMetric` and 12 fact tables) that load directly into
Power BI Desktop.

- [`powerbi/dashboard_guide.md`](powerbi/dashboard_guide.md) — import steps, data types, the 9 relationships, and the exact field wells for all four pages: **Executive Summary, Team Performance, Match History, Prediction & Validation**.
- [`powerbi/dax_measures.md`](powerbi/dax_measures.md) — 60+ copy-paste DAX measures, formatting strings and the gotchas that break the report.
- [`powerbi/theme.json`](powerbi/theme.json) — the colour theme (HLE amber `#D97706`, IG blue `#2563EB`, colour-blind safe).

> **No native `.pbix` file is included.** Power BI Desktop was not controlled
> by this project. The CSVs, theme, DAX and build guide let you assemble the
> report manually in Power BI Desktop.

## Reports

- [`reports/executive_report.md`](reports/executive_report.md) — decision-oriented summary.
- [`reports/model_card.md`](reports/model_card.md) — intended use, performance, limitations.
- [`reports/post_match_validation_plan.md`](reports/post_match_validation_plan.md) — the pre-registered rules for scoring the finished match.
- [`reports/data_quality_log.md`](reports/data_quality_log.md) — sources, target verification, cleaning rules, missingness, the LYON defect and its fix, and the audit trail.
- `data/processed/data_quality_report.json` — generated data-quality log: 14 collection checks, field-level missingness, model sample composition and the head-to-head count.

## Refresh instructions

1. Update `COLLECTION_CUTOFF_UTC` and `TARGET_MATCH_START_UTC` in `src/config.py`.
2. Run `python src\run_pipeline.py --refresh` (requires `OE_API_KEY` in the environment; the cached path needs no key).
3. Rebuild the Power BI report from `data/powerbi/` (or refresh the data source).
4. Update the post-match validation log with the actual result: `python src\score_match.py --winner HLE|IG --side blue|red`.

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

1. **Score the match against the pre-registered rules.** The match started
   2026-10-25 17:00 UTC, after the 16:20 UTC data cutoff, so the result is not
   in this repository yet. Run
   `python src/score_match.py --winner HLE|IG --side blue|red` to write the
   Brier score, log loss and correct pick into
   `powerbi/post_match_validation_log.csv`, then update
   `reports/model_card.md`. One match cannot validate the model — report the
   result as one observation.
2. **Build the Power BI report by hand** from `powerbi/dashboard_guide.md` — the 16 CSVs, the DAX measures and the theme are ready; only the `.pbix` assembly is left, and that needs Power BI Desktop.
3. **Strengthen the model before the next fixture.** The features are
   collinear (0.83–0.94) and the holdout is small (72 games, 33 positives):
   add roster/patch-level features, widen the season sample beyond the last-50
   seeding, and re-tune on a rolling window before trusting any edge.
4. **Re-collect with `--refresh`** for the next match and keep the cutoff
   discipline, so every forecast stays pre-registered.

## Limitations

- **Partial sample:** last-50-game seeding, not complete season data.
- **No target side:** blue/red assignment is not confirmed pre-match.
- **No draft, roster, patch-specific, or player-level features.**
- **Weak holdout signal:** AUC ≈ 0.50; the model is a structured baseline, not a betting model.
- **Collinearity:** the five form features overlap heavily.
- **Small test set:** 72 games, 33 positives; metrics have wide sampling error.
- **Stage aggregates:** event objective rates are not game-level features.
- **Single Bo1:** variance is large; even a good model would be uncertain.
- **No head-to-head:** HLE and IG did not play in the collected sample.

## Artifact checklist

- [x] Raw data + collection manifest
- [x] Cleaned CSVs (fact, dim, form, model dataset)
- [x] Reproducible Python pipeline
- [x] KPI definitions and team/match KPIs
- [x] Chronological model with holdout metrics
- [x] Bootstrap uncertainty and scenario analysis
- [x] 10 charts
- [x] Power BI star-schema CSVs
- [x] Executive report, model card
- [x] Pre-registered post-match validation plan + scoring script
- [x] Rendered data-quality log (plus the machine-readable JSON twin)
- [x] Power BI build guide, DAX measures and colour theme
- [x] 56/56 validation checks (including the hardcoded-secret scan)
- [ ] Native `.pbix` (requires Power BI Desktop; not generated)
- [ ] Post-match result (the match started after the data cutoff; the log row is still pending)
