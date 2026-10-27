# Project overview & study guide — Worlds 2026 match analytics

**Everything that was built, why it was built that way, and what it actually
found.** This document is the narrative version of the repository: the code is
the evidence, this is the reasoning.

---

## 1. What the project is

A reproducible, end-to-end business-analytics project that:

1. **Collects** public *League of Legends* professional match data from the
   Oracle's Elixir API.
2. **Cleans** it into an analysis-ready star schema.
3. **Defines** a KPI framework for teams and matches.
4. **Builds** a pre-match win-probability model with honest uncertainty
   quantification.
5. **Registers** the forecast before the match, so it cannot be retro-fitted.
6. **Scores** it after the match with pre-registered rules.
7. **Publishes** everything as Power BI-ready tables plus a full written
   decision package (executive report, model card, data-quality log, charts).

The unit of analysis is a **single game between two teams in the same event**;
the deliverable is a **probability**, not a pick.

**The non-objective, stated up front:** this is *not* a betting model. The
model's out-of-sample performance is at or slightly worse than a coin flip,
and that is reported as the headline finding rather than buried.

---

## 2. The three phases of work (and why each happened)

### Phase 1 — Build (Oct 25, pre-match)

The brief was: *verify the match, collect data, build KPIs, model it, produce
Power BI assets, write the reports, and do not stop at planning.*

Key decisions and their reasons:

| Decision | Reason |
|---|---|
| Verify the fixture before assuming anything | The match had to be confirmed as real, upcoming and correctly identified. It was: OE `/matches/upcoming` returned `matchId 115660540726095045`, HLE vs IG, Bo1, Swiss Day 3, `state: unstarted`, cross-checked against Leaguepedia. |
| Freeze a data cutoff **before** modelling | `2026-10-25 16:20 UTC`. Every feature uses only games that started before it. Without a cutoff there is no defensible "pre-match" claim. |
| Exclude the target match by ID | Belt-and-braces: it is filtered at collection *and* re-verified in the automated checks ("target match absent from fact / dimension / model"). |
| Use the OE **API** instead of the bulk CSV | The CSV download was blocked (Google Drive quota exceeded). The API is the same source that powers `oracleselixir.com`; the substitution is recorded in the collection manifest and the data-quality log. |
| Sample 16 Worlds teams × last 50 games | Gives a multi-team, multi-event sample without a full league scrape, and yields both intra-cohort games (the modelling sample) and cross-cohort games (opponent context). |
| Model on **intra-cohort** games only | Predicting a Worlds match from a sample of Worlds-vs-Worlds games keeps the feature distribution close to the prediction target. |
| Standardised L2 logistic regression, `C=0.5`, **no intercept** | See §6 — the no-intercept choice is the single most important modelling decision in the project. |
| Chronological split (train ≤ 2026-08-30, test ≥ 2026-09-02) | Shuffling would leak the future into training through the rolling form. A time split is the only honest way to test a pre-match model. |
| 1,000-draw bootstrap | The point estimate alone would imply a confidence the data does not support. |
| 5-feature core + 4/8-feature sensitivities | To show how much the headline number depends on feature choice, rather than presenting one number as if it were robust. |

### Phase 2 — Security & repository hygiene (Oct 26)

During the build, the OE API key had been written into `src/config.py` as a
literal default and the repository was pushed to a **public** GitHub repo. The
key is the browser-side key that `oracleselixir.com` sends from every visitor,
so its real-world exposure is low — but the pattern was unacceptable.

Actions taken, in order:

1. **Removed the literal** from `src/config.py`; the key is now read *only*
   from the `OE_API_KEY` environment variable, with no fallback.
2. **`collect_data.py`** only attaches the `X-Api-Key` header when the
   environment variable is set, and prints a loud warning otherwise.
3. **Deleted the local `.git`**, so the key is no longer in any local git
   object.
4. **Made the public repo private immediately**, cutting the public exposure
   while the deletion scope was being authorised.
5. **Deleted the GitHub repository** (the `delete_repo` scope required a
   one-time device authorisation) and verified: API returns 404, no forks, and
   a code-search across the whole account returns **0** matches for the key.
6. **Removed the personal path** (`C:\Users\<user>\…`) from the README.
7. **Switched the commit identity** to the GitHub `noreply` address, so the
   author's personal email is not exposed in public commit metadata.
8. **Added a permanent guard**: `validate_outputs.py` now scans every `.py`
   file for a literal key/token/secret assignment and **fails the build** if
   it finds one (check 56). The guard was verified with a deliberately planted
   fake key.
9. Added `.env.example` (tracked, empty) + `.gitignore` rules for `.env`.

The repo was then re-created **from scratch**, audited, and pushed. Before
every push the tree is scanned for secret patterns; the audit log is in the
commit history.

### Phase 3 — Score, refresh, re-target (Oct 27)

With the match played and the request to "review the matches up to now and
compute Wednesday's probabilities":

1. **Scored the 25 Oct match** with the pre-registered rules (§7).
2. **Re-collected the data** with a new cutoff (`2026-10-27 00:00 UTC`),
   fetching 630 games and the new match-day fixtures.
3. **Re-pointed the pipeline** at the next fixture: LYON vs IG, Worlds 2026
   Swiss Day 5, best of 3, 2026-10-28 23:00 UTC.
4. **Generalised the code** so the target lives in `config.py` (plus a
   `UPCOMING_FIXTURES` list) and the pipeline publishes the **whole slate**,
   not a single match.
5. **Added best-of-3 conversion** with the assumption stated explicitly.
6. **Rewrote the reports** against the new numbers, and added a dedicated
   write-up of the validated case study.

---

## 3. Data: sources, collection, quality

### 3.1 Sources

| Source | Endpoint | Volume |
|---|---|---|
| Upcoming matches | `GET /matches/upcoming` | 6 records (25 Oct) |
| Team game lists | `GET /teams/gameDetails/{team}?beforeTime=…` | 16 teams × 50 games |
| Game details | `GET /games/singleGame/{oe_game_id}` | 630 games (gzipped JSON) |
| Event aggregates | `GET /teams/statsBySplit/{team}` | 16 teams, 800 rows |

Everything is logged in `data/raw/collection_manifest.json`: endpoint, record
count, cache-vs-remote, collection timestamps and the target-match record with
its state.

### 3.2 Final sample (27 Oct refresh)

| Layer | Rows | Notes |
|---|---:|---|
| Unique completed games | 630 | deduplicated by `oeGameId`, all before the cutoff |
| Fact: team-game | 1,260 | exactly two mirrored rows per game |
| Dimension: game | 630 | one row per game |
| Distinct teams in the fact | 57 | the 16-team Worlds cohort + 41 opponents |
| Model dataset (intra-cohort) | 226 | both sides are Worlds participants |
| Modelling sample | 179 | ≥5 prior games per side **and** complete features |
| Train / test (chronological) | 94 / 85 | split at 2026-09-01 00:00 UTC |

### 3.3 Cleaning rules and why

| Rule | Why |
|---|---|
| One row per team per game, mirrored blue/red | The fact table is the unit of analysis for every downstream feature |
| Exactly one winner per game; unpaired games rejected | A game with two winners or one side missing would corrupt win-rate and gold-diff features |
| Timestamps parsed as UTC | The feed mixes timezones; the cutoff comparison must be unambiguous |
| Strict `gameCreation < cutoff` | Enforces the pre-registration claim |
| Target match excluded by ID at collection **and** in checks | Defence in depth against leakage |
| **Team-name canonicalisation** (`LYON` → `LYON (2024 American Team)`) | OE uses two labels for the same team in two endpoints. Uncorrected, LYON's games split across two identities and **silently vanish** from the model: fixing it moved the model sample from 195 → 226 games |
| Rolling windows shifted one game back | A feature computed *including* the current game is leakage |
| Stale raw payloads ignored | The last-50-game window slides, so old payloads linger on disk; `build_dataset` now only uses games referenced by the current team lists, keeping the fact table consistent with the manifest |
| No imputation of `gd10` | 81 rows lack per-player `gxd10`; filling with 0 or carry-forward would fabricate early-game information |

### 3.4 Missingness

| Field | Missing | Handling |
|---|---:|---|
| duration, gold, kills, deaths, towers, dragons, barons, first blood | 0% | — |
| `gd10` | 81 rows (6.4%) | dropped from the modelling frame, never imputed |
| `opp_wr_10` (strength of schedule) | 163 rows (12.9%) | only used by the 8-feature sensitivity model |

The modelling frame requires **all eight** candidate features for every game,
so 47 games are dropped (226 → 179). That is deliberately conservative: it
guarantees the 4-, 5- and 8-feature specifications are compared on an
identical sample.

---

## 4. KPI framework

23 documented metrics in `kpi_definitions.csv`, each with definition, formula
and direction. The load-bearing ones:

| KPI | Definition | Direction | Role |
|---|---|---|---|
| Win rate | wins / games in window | Higher | Feature (form) |
| GD@10 | mean Σ of five players' `gxd10` | Higher | Feature — **proxy for GD@15**, which the API does not expose |
| End-game gold diff | mean final gold difference | Higher | Feature (conversion) |
| Kill differential | mean kills − deaths | Higher | Feature (fighting) |
| Objective composite | tower diff + dragon diff + **2 × baron diff** | Higher | Feature (map control; barons weighted double because they are the strongest swing) |
| First-blood rate | share of games with first blood | Higher | Feature (sensitivity only) |
| Strength of schedule | mean opponent pre-game 10-game win rate | Context | Feature (sensitivity only) |
| Rest days | days since last game | Context | Report only |
| Form index | mean z-score of last-10 win rate, gold diff, kill diff, objective score | Higher | Descriptive ranking only |
| Event objective rates (FB%, FT%, FD%, DRG%, BN%) | OE stage aggregates | Context | **Never** a model input |

Two design rules matter: (a) `GD@10` is labelled a proxy everywhere it
appears, because calling it GD@15 would be a factual error; (b) event
aggregates are *stage* averages, not game-level facts, so they inform the
narrative and never the model.

---

## 5. Feature engineering (and the leakage traps avoided)

For every game, each team's **pre-game last-10 means** are computed, and the
model feature is the **difference** (team_a − team_b):

`wr_10_diff`, `gd10_10_diff`, `gold_diff_10_diff`, `kd_diff_10_diff`,
`obj_10_diff` (primary five), plus `fb_rate_10_diff`, `duration_10_diff`,
`sos_10_diff` (sensitivity only).

Three traps avoided:

1. **Look-ahead**: the rolling mean for a game is computed over the *previous*
   10 games only (`shift(1).rolling(10)`).
2. **Opponent leakage in SOS**: the current game's opponent is excluded from
   the team's own strength-of-schedule average.
3. **Unplayed fixtures**: for a future fixture there is no "game row", so the
   feature vector is built from each team's ten most recent games before the
   cutoff (`fixture_features.csv`).

---

## 6. Model design and the reasoning behind each choice

### 6.1 Why logistic regression at all

The target is a binary outcome (team_a wins). A calibrated probability is
required, not a ranking. Logistic regression gives a probability directly,
is inspectable feature-by-feature, regularises well with few features, and
can be refit in seconds as new match days arrive. Gradient boosting would
have fitted the 179-game sample harder and produced less honest uncertainty.

### 6.2 Why the features are *differences*

A model that uses each team's absolute form would have to learn a per-team
intercept from 16 teams with very different baselines. Differencing removes
the team effect entirely: the model only has to learn "when team A's recent
profile is better than team B's, how likely is A to win". That is also what
makes the same model applicable to *any* pairing in the cohort.

### 6.3 Why there is no intercept (the key decision)

In the historical feed, `team_a` is **always** the blue side. Blue side wins
**55.9%** of the time in the sample. A fitted intercept would silently encode
"the a-side wins ~56% of the time" — but for a *new* fixture the side
assignment is unknown. That would import the training period's side bias
into a match where the side is not yet decided.

Removing the intercept makes the model **side-neutral**: it expresses only
"given the form difference, which side of the ledger is favoured". Side is
then handled explicitly as a scenario (blue prior / red prior) instead of
being smuggled in as a constant. This is the difference between a model that
is *honest about what it knows* and one that quietly assumes something.

### 6.4 Regularisation and the sensitivity checks

`C=0.5` (L2) was fixed **before** looking at the holdout, so the holdout stays
a fair test. Four specifications are reported side by side (coin flip, win
rate only, core 4, core 5, 8 features) plus scenarios that neutralise one
team's edges and the two side priors. The point is to show how fragile the
headline number is: the 8-feature model moves the target probability by less
than a point, and every specification is compared against the coin flip.

### 6.5 Uncertainty

A 1,000-draw bootstrap of the full modelling sample gives a 90% interval for
the target probability. For the current fixture: **33.5%–48.9%** for LYON.
Because the interval contains 50%, the correct statement is "no reliable
edge", and the report says exactly that.

### 6.6 Calibration

Predictions are binned and compared with observed frequencies, both on the
holdout and on out-of-fold time-series cross-validated predictions. The
holdout is **overconfident above 0.50** and **underconfident in the 0.40–0.50
band** — a concrete, reportable defect rather than a vague caveat.

### 6.7 Best-of-3 conversion (new in phase 3)

The Wednesday fixtures are best of three, so the per-game probability needs a
series interpretation:

```
P(win series) = P(at least 2 wins in 3 games) = 3p²(1−p) + p³ = p²(3 − 2p)
```

This assumes games are **independent** and the per-game probability is
**constant** (no side rotation effects, no draft adaptation). It is labelled as
a simplification everywhere it appears, and the per-game number remains the
model's native output. At p = 0.414 the series probability is 0.372.

---

## 7. The pre-registration and scoring discipline

This is the methodological core of the project, and the thing that makes the
result meaningful.

**The protocol**

1. Before a match, the probability (not just the pick) is written into
   `powerbi/post_match_validation_log.csv` with the data cutoff, the model id
   and the holdout metrics.
2. After the match, `src/score_match.py` fills **only** the empty result
   columns, computing:
   - **Brier score** = `(p_team_a − actual_team_a_win)²` — coin flip = 0.2500
   - **Log loss** = `−ln(p of the actual winner)` — coin flip = 0.6931
   - **Correct pick** — the model's direction vs the actual winner
   - plus context (side, patch, duration) and the source of the result
3. The decision rule is fixed in advance: Brier ≤ 0.2500 **and** log loss ≤
   0.6931 → beat the coin flip on that match; otherwise not. And in either
   case, **one match does not validate the model**.

**Why the probability and not the pick**: a directionally correct 51%
prediction is worth less than a 90% one. Logging only the pick would let a
model claim credit it did not earn.

**Why this matters for a portfolio**: it converts a forecasting exercise into
a falsifiable claim. The project does not merely assert the model works; it
writes down, in advance, exactly what would count as being right.

---

## 8. The validated case study — HLE vs IG, 2026-10-25

| | |
|---|---|
| Pre-registered (16:47 UTC, 13 min before start) | HLE **43.9%** / IG **56.1%**, CI 37.2%–51.6%, pick **IG** |
| Actual | **IG won** (blue side), 29–9 kills, +9,252 gold, 28.6 min, patch 16.20 |
| Brier | **0.1924** vs 0.2500 coin flip |
| Log loss | **0.5774** vs 0.6931 coin flip |
| Correct pick | **Yes** |

**The honest reading.** The forecast beat both coin-flip baselines on that
match and the direction was right. It is still **one observation**: the
chronological holdout (85 games, 42 positives) remains at chance
(AUC 0.477, Brier 0.259, log loss 0.712). The realised game *did* match the
model's reasoning (IG won on objectives, 7–3 towers and 4–0 dragons, and on
a +9,252 gold swing), but a single game cannot separate a 51% model from a
60% one. The write-up in `reports/validated_forecast_hle_vs_ig.md` says all of
this explicitly.

---

## 9. The current forecast — Wednesday 28 October

| Fixture | Start (UTC) | Format | Per game | 90% CI (team 1) | Best of 3 | Read |
|---|---|---|---:|---:|---:|---|
| MKOI vs T1 | 20:00 | Bo3 | 50.9% / 49.1% | 41.6%–60.1% | 51.4% / 48.6% | coin flip |
| **LYON vs IG** | **23:00** | **Bo3** | **41.4% / 58.6%** | **33.5%–48.9%** | **37.2% / 62.8%** | marginal IG lean |

### 9.1 The evidence behind the IG lean

| Last-10 metric | LYON | IG | Edge |
|---|---:|---:|---|
| GD@10 | **−396** | **−488** | LYON +92 (both negative!) |
| First-blood rate | **40%** | **20%** | LYON +20 pp |
| End-game gold diff | **−2,127** | **+1,064** | **IG +3,192** |
| Kill differential | −1.2 | −0.1 | IG +1.1 |
| Objective composite | −1.7 | **+2.0** | **IG +3.7** |
| Strength of schedule | 0.80 | 0.57 | LYON faced harder opposition |
| Form index rank | 14/16 | 9/16 | IG |
| vs Worlds teams | 17–10 (63.0%) | 8–9 (47.1%) | LYON |
| Rest | 3.0 d | 3.2 d | ~equal |

**Read:** both teams are *negative* on GD@10 — "better early" is relative, not
absolute. The separation is at the other end of the map: IG closes games with
more gold and more objectives. LYON's early edge is real but small, and it
does not reach its end-game numbers: the profile of a team that wins
skirmishes and loses the map. LYON also arrives having lost 1–2 to Gen.G in a
Bo3 three days earlier, while IG comes off a win over HLE.

### 9.2 Feature contributions (log-odds, primary model)

| Feature | LYON − IG | Standardised | Coefficient | Contribution |
|---|---:|---:|---:|---:|
| End-game gold diff | −3,192 | −0.67 | +0.400 | **−0.269** |
| Objective composite | −3.7 | −0.80 | +0.143 | **−0.114** |
| Kill differential | −1.1 | −0.31 | +0.026 | −0.008 |
| GD@10 | +92 | +0.04 | −0.145 | −0.005 |
| Recent win rate | 0.0 | −0.14 | −0.349 | +0.048 |
| **Net** | | | | **−0.348 → 41.4%** |

### 9.3 Scenarios

| Scenario | P(LYON) | P(IG) |
|---|---:|---:|
| Coin flip | 50.0% | 50.0% |
| Primary (core 5) | 41.4% | 58.6% |
| Core 4 | 42.6% | 57.4% |
| 8-feature | 41.5% | 58.5% |
| Win-rate only | 49.8% | 50.2% |
| **LYON blue-side prior** | **47.2%** | 52.8% |
| **LYON red-side prior** | **35.8%** | 64.2% |
| Neutralise IG's edges | 49.3% | 50.7% |
| Neutralise LYON's edges | 41.6% | 58.4% |

**Side assignment is as important as the form signal** — and it is not
published pre-match. The match record's `team1 = LYON` must not be assumed to
mean blue.

---

## 10. The most important finding: a negative result

On the 85-game chronological holdout, **every specification is at or worse
than the coin flip**:

| Model | Features | AUC | Brier | Log loss | Accuracy |
|---|---:|---:|---:|---:|---:|
| **Coin flip** | 0 | 0.500 | **0.250** | **0.693** | **49.4%** |
| Win rate only | 1 | 0.476 | 0.257 | 0.707 | 47.1% |
| Core 4 | 4 | 0.478 | 0.259 | 0.712 | 42.4% |
| **Core 5 (primary)** | 5 | **0.477** | **0.259** | **0.712** | **42.4%** |
| 8-feature | 8 | 0.458 | 0.262 | 0.717 | 40.0% |

Version 1.0 (data to 25 Oct, 72-game holdout) scored AUC 0.494 / Brier 0.255;
the refit with 13 more games moved it *slightly down*. That is what an honest
refit looks like — the model was never carrying skill, and more data
confirmed it rather than rescuing it.

**Why this is valuable, not embarrassing.** A project that reports a negative
result, with the method pre-registered and the code reproducible, demonstrates
exactly what a reviewer wants to see: that the analyst can build a pipeline,
not fool themselves, and report what the data says. A portfolio that claims
60% accuracy on a 179-game form model would be *less* credible than this one.

**What would change it** (in rough order of expected impact): confirmed side
as a feature; draft data; roster/player-level signals; a complete-season
sample instead of a 50-game window; market-implied probabilities as a
benchmark; and gradient boosting with proper nested validation — each of
which needs a bigger sample than exists today.

---

## 11. Repository map and what each file is for

```
league-of-legends-match-analysis/
├── src/                        pipeline (10 modules, ~2,000 lines)
│   ├── config.py               target, cutoff, team list, alias map, fixtures — no secrets
│   ├── collect_data.py         OE API collection with retry/backoff + manifest
│   ├── build_dataset.py        cleaning, rolling form, model dataset, DQ report
│   ├── kpis.py                 team/match KPIs, target snapshot, slate features
│   ├── model.py                chronological model, bootstrap, calibration, slate, Bo3
│   ├── visualizations.py        10 charts (200 dpi)
│   ├── export_powerbi.py       19 star-schema CSVs
│   ├── validate_outputs.py     71 mechanical checks (incl. secret scan)
│   ├── score_match.py          scores a finished match into the validation log
│   └── run_pipeline.py         one-command orchestration (--refresh, --skip-viz)
├── data/
│   ├── raw/                    630 gzipped payloads + manifest (immutable)
│   ├── processed/              23 analysis tables + JSON summaries
│   └── powerbi/                19 star-schema tables ready to load
├── figures/                    10 PNG charts
├── powerbi/
│   ├── dashboard_guide.md      import → relationships → 4 pages → refresh
│   ├── dax_measures.md         70+ measures, formats, gotchas
│   ├── theme.json              colour theme (accessible, colour-blind safe)
│   └── post_match_validation_log.csv   pre-registered predictions + results
├── reports/                    5 written deliverables
├── requirements.txt            5 pinned dependencies
├── .gitignore / .gitattributes / .env.example
└── README.md                   the front door
```

**Why a star schema for Power BI.** The processed tables are analysis-friendly
(long, ad-hoc names). Power BI wants explicit keys, date-only columns and
stable snake_case. `export_powerbi.py` re-shapes once, on the Python side, so
the report needs no Power Query gymnastics and the CSVs are the single source
of truth.

**The 19 tables**: 4 dimensions (`DimDate`, `DimTeam`, `DimGame`, `DimMetric`)
+ 15 facts, of which 9 form the connected star (game, form, team game, team
event stat, team KPI, match KPI, target feature) and 6 are presentation
tables used per page (prediction, fixture prediction, fixture feature,
validation log, model metric/coefficient/calibration, scenario, feature
contribution).

**The four report pages**: Executive Summary · Team Performance · Match
History · Prediction & Validation — each specified with exact field wells in
the build guide.

---

## 12. Validation of the pipeline itself

`validate_outputs.py` runs **71 checks** (all passing) in three families:

- **Existence**: 23 processed tables, 10 figures, 19 Power BI tables.
- **Structure**: fact = 2 × dimension, no duplicate team-game rows, no
  unpaired games, exactly one winner per game, no first-blood conflicts.
- **Leakage & sanity**: target match absent from fact/dimension/model, target
  feature vector complete, probabilities sum to 1 and lie in [0,1], bootstrap
  interval ordered, modelling sample ≥ 100, slate probabilities consistent,
  validation-log rows consistent, target fixture pre-registered, and **no
  hardcoded secrets in the source tree**.

The separation of concerns is deliberate: `build_dataset.py` writes a
*diagnostic* quality report (14 structural checks, missingness, sample
composition), while `validate_outputs.py` writes a *pass/fail* verification of
the whole artefact set. One diagnoses, the other gates.

---

## 13. Reproducibility

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src\run_pipeline.py            # from cached raw data, no API key needed
python src\run_pipeline.py --refresh  # re-fetch from the OE API (needs OE_API_KEY)
```

Determinism: fixed random seed (`20261025`) for the estimator and the
bootstrap, so the forecast is bit-for-bit reproducible. The 27 Oct run was
verified by cloning the published repo and re-running the pipeline from the
clone: 71/71 checks and identical probabilities.

---

## 14. What a reviewer should take away

1. **The pipeline is the product.** The probability is one number; the
   auditable process around it is the asset.
2. **Pre-registration converts a forecast into a testable claim.**
3. **Side neutrality is a modelling decision, not a footnote.**
4. **A negative result, reported properly, is a stronger signal of competence
   than an unsupported positive one.**
5. **Secrets belong in the environment, and the guard against them should be
   automated** — a check that fails the build beats a promise in a README.

---

## 15. Glossary

| Term | Meaning in this project |
|---|---|
| **AD / blue side** | The side of the map chosen by the first team in the draft; historically favoured (55.9% wins here) |
| **GD@10 / GD@15** | Gold difference at 10 / 15 minutes. Only GD@10 is available via the API, so it is used as a labelled proxy |
| **Objective composite** | `towers diff + dragons diff + 2 × barons diff` — a single map-control number |
| **GSPD** | Gold share percentage difference (Oracle's Elixir) |
| **EGR / MLR** | OE's efficiency and match-win ratings for a stage |
| **Feature vector (differences)** | The five last-10 statistics, each taken as team_a − team_b |
| **Chronological split** | Train on the past, test on the future — the only honest split for pre-match prediction |
| **Bootstrap interval** | Resampling the sample 1,000 times to get an honest interval on the predicted probability |
| **Brier score** | Mean squared error of a probability forecast; 0.25 for a 50/50 forecast |
| **Log loss** | Penalises confident wrong forecasts severely; 0.693 for a 50/50 forecast |
| **AUC** | Ranking ability of the model; 0.5 = random, 1.0 = perfect |
| **Calibration** | Whether predicted probabilities match observed frequencies |
| **OOF (out-of-fold)** | Predictions from time-series cross-validation, used as a second calibration view |
| **Side-neutral** | A model with no intercept, so it expresses only the *difference* in form and never assumes a side advantage |
| **Pre-registration** | Writing the prediction down before the event, with fixed scoring rules |
