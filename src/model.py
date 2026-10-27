"""Chronological match model, uncertainty and target prediction.

Design choices
--------------
* Every feature is a pre-game rolling difference (team_a minus team_b).
* The holdout split is chronological: train before 2026-09-01, test after.
* The primary model is side-neutral (fit_intercept=False). In the collected
  game feed team_a is always the blue side, but the target match's side
  assignment is not confirmed. Fitting an intercept would bake the training
  period's blue-side rate into a match where side is unknown.
* L2 logistic regression with C=0.5, fixed before looking at the holdout.
* Uncertainty comes from a 1,000-draw bootstrap of the full modelling sample.
* The model is small and the holdout signal is weak. Metrics are reported
  against a 50/50 coin-flip baseline, not hidden.
"""

from __future__ import annotations

import json
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import (
    COLLECTION_CUTOFF_UTC,
    PROCESSED_DIR,
    TARGET_MATCH_ID,
    TARGET_MATCH_START_UTC,
    TEAM_A,
    TEAM_A_CODE,
    TEAM_B,
    TEAM_B_CODE,
)

SPLIT_UTC = pd.Timestamp("2026-09-01T00:00:00Z")
RANDOM_STATE = 20261025
N_BOOTSTRAP = 1000
C_FIXED = 0.5

FEATURE_LABELS = {
    "wr_10_diff": "Recent win rate (last 10)",
    "gd10_10_diff": "Gold diff at 10 min (last 10)",
    "gold_diff_10_diff": "End-game gold diff (last 10)",
    "kd_diff_10_diff": "Kill differential (last 10)",
    "obj_10_diff": "Objective composite (last 10)",
    "fb_rate_10_diff": "First-blood rate (last 10)",
    "duration_10_diff": "Average game duration (last 10)",
    "sos_10_diff": "Strength of schedule (last 10)",
}

FEATURE_SETS = {
    "M0_coinflip": [],
    "M1_win_rate": ["wr_10_diff"],
    "M2_core4": [
        "wr_10_diff",
        "gd10_10_diff",
        "gold_diff_10_diff",
        "kd_diff_10_diff",
    ],
    "M3_core5": [
        "wr_10_diff",
        "gd10_10_diff",
        "gold_diff_10_diff",
        "kd_diff_10_diff",
        "obj_10_diff",
    ],
    "M4_sensitivity_8": list(FEATURE_LABELS),
}
PRIMARY = "M3_core5"
ALL_FEATURES = list(FEATURE_LABELS)


def load_model_data() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_DIR / "model_dataset.csv")
    df["date_utc"] = pd.to_datetime(df["date_utc"], utc=True)
    df = df[df["prior_games_min"] >= 5].copy()
    df = df.dropna(subset=ALL_FEATURES).copy()
    return df.sort_values("date_utc").reset_index(drop=True)


def load_target() -> pd.Series:
    target = pd.read_csv(PROCESSED_DIR / "target_model_input.csv").iloc[0]
    return target


def fit_model(frame: pd.DataFrame, features: list[str], c: float = C_FIXED):
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=c,
            max_iter=5000,
            fit_intercept=False,
            random_state=RANDOM_STATE,
        ),
    )
    model.fit(frame[features], frame["team_a_win"])
    return model


def metrics(y: pd.Series, p: np.ndarray) -> dict:
    return {
        "n": int(len(y)),
        "positives": int(y.sum()),
        "accuracy": float(accuracy_score(y, p >= 0.5)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p)),
        "auc": float(roc_auc_score(y, p)),
        "mean_prediction": float(np.mean(p)),
    }


def predict(model, target: pd.Series, features: list[str]) -> float:
    x = pd.DataFrame([{f: float(target[f]) for f in features}])
    return float(model.predict_proba(x)[0, 1])


def bootstrap_prediction(
    frame: pd.DataFrame,
    target: pd.Series,
    features: list[str],
    c: float = C_FIXED,
    n_boot: int = N_BOOTSTRAP,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(RANDOM_STATE)
    preds, coefs = [], []
    for _ in range(n_boot):
        idx = rng.integers(0, len(frame), len(frame))
        sample = frame.iloc[idx]
        if sample["team_a_win"].nunique() < 2:
            continue
        model = fit_model(sample, features, c)
        preds.append(predict(model, target, features))
        coefs.append(model[-1].coef_[0])
    return np.array(preds), np.array(coefs)


def calibration_table(y: pd.Series, p: np.ndarray, sample: str) -> pd.DataFrame:
    bins = [0.0, 0.40, 0.45, 0.50, 0.55, 0.60, 1.0]
    labels = ["<0.40", "0.40-0.45", "0.45-0.50", "0.50-0.55", "0.55-0.60", ">0.60"]
    table = pd.cut(p, bins=bins, labels=labels, include_lowest=True, right=False)
    out = (
        pd.DataFrame({"bin": table, "y": y.values, "p": p})
        .groupby("bin", observed=False)
        .agg(n=("y", "size"), observed=("y", "mean"), mean_pred=("p", "mean"))
        .reset_index()
    )
    out["abs_error"] = (out["observed"] - out["mean_pred"]).abs()
    out.insert(0, "sample", sample)
    return out


def oof_predictions(frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    preds = np.full(len(frame), np.nan)
    splitter = TimeSeriesSplit(n_splits=5)
    for train_idx, test_idx in splitter.split(frame):
        model = fit_model(frame.iloc[train_idx], features)
        x = frame.iloc[test_idx][features]
        preds[test_idx] = model.predict_proba(x)[:, 1]
    return preds


def logit(p: float) -> float:
    return float(np.log(p / (1 - p)))


def expit(x: float) -> float:
    return float(1 / (1 + np.exp(-x)))


def series_probability(p_game: float, best_of: int = 3) -> float:
    """Probability of winning a best-of-N series from a per-game probability.

    P(series win) = P(at least `needed` wins in `best_of` games), which for a
    best-of-3 simplifies to p^2 * (3 - 2p). Assumes the games are independent
    and that the per-game probability is the same in every game (no side or
    draft adaptation). This is a stated simplification, not a model of Bo3
    dynamics.
    """
    p = min(max(p_game, 0.0), 1.0)
    if best_of <= 1:
        return float(p)
    needed = best_of // 2 + 1
    total = 0.0
    for wins in range(needed, best_of + 1):
        total += comb(best_of, wins) * (p**wins) * ((1 - p) ** (best_of - wins))
    return float(total)


def build_fixture_predictions(
    frame: pd.DataFrame,
    features: list[str],
    fixtures: pd.DataFrame,
    n_boot: int = N_BOOTSTRAP,
) -> pd.DataFrame:
    """Predict every upcoming fixture with the primary model.

    Outputs the side-neutral per-game probability, the two side scenarios, the
    derived best-of-3 series probability and a bootstrap interval.
    """
    model = fit_model(frame, features)
    rng = np.random.default_rng(RANDOM_STATE)
    boot_models = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(frame), len(frame))
        sample = frame.iloc[idx]
        if sample["team_a_win"].nunique() < 2:
            continue
        boot_models.append(fit_model(sample, features))

    rows = []
    for _, fixture in fixtures.iterrows():
        x = pd.DataFrame(
            [{f: float(fixture[f]) for f in features}]
        )
        p = float(model.predict_proba(x)[0, 1])
        boot = np.array([float(m.predict_proba(x)[0, 1]) for m in boot_models])
        rows.append(
            {
                "match_id": fixture["match_id"],
                "team_a": fixture["team_a"],
                "team_b": fixture["team_b"],
                "team_a_code": fixture.get("team_a_code", TEAM_A_CODE),
                "team_b_code": fixture.get("team_b_code", TEAM_B_CODE),
                "start_utc": fixture["start_utc"],
                "series_type": fixture["series_type"],
                "block": fixture["block"],
                "p_team_a_game": p,
                "p_team_b_game": 1 - p,
                "bootstrap_p05": float(np.percentile(boot, 5)),
                "bootstrap_p50": float(np.percentile(boot, 50)),
                "bootstrap_p95": float(np.percentile(boot, 95)),
                "p_team_a_bo3": series_probability(p, 3),
                "p_team_b_bo3": series_probability(1 - p, 3),
                "p_team_a_bo3_low": series_probability(float(np.percentile(boot, 5)), 3),
                "p_team_a_bo3_high": series_probability(float(np.percentile(boot, 95)), 3),
                "pick": fixture.get("team_a_code", TEAM_A_CODE)
                if p >= 0.5
                else fixture.get("team_b_code", TEAM_B_CODE),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    df = load_model_data()
    target = load_target()
    train = df[df["date_utc"] < SPLIT_UTC].copy()
    test = df[df["date_utc"] >= SPLIT_UTC].copy()
    if train["team_a_win"].nunique() < 2 or test["team_a_win"].nunique() < 2:
        raise RuntimeError("Chronological split does not contain both classes")

    comparison_rows, coef_rows, prediction_rows = [], [], []
    final = {}

    for name, features in FEATURE_SETS.items():
        if not features:
            p_test = np.full(len(test), 0.5)
            p_target = 0.5
            preds_boot = np.full(N_BOOTSTRAP, 0.5)
            coefs_boot = np.zeros((N_BOOTSTRAP, 0))
            coef = np.array([])
        else:
            model = fit_model(train, features)
            p_test = model.predict_proba(test[features])[:, 1]
            final_model = fit_model(df, features)
            p_target = predict(final_model, target, features)
            coef = final_model[-1].coef_[0]
            preds_boot, coefs_boot = bootstrap_prediction(df, target, features)

        m = metrics(test["team_a_win"], p_test)
        row = {"model": name, "features": len(features), "feature_list": ", ".join(features)}
        row.update(m)
        comparison_rows.append(row)

        for i, f in enumerate(features):
            coef_rows.append(
                {
                    "model": name,
                    "feature": f,
                    "label": FEATURE_LABELS[f],
                    "standardized_coefficient": float(coef[i]),
                    "coef_p05": float(np.percentile(coefs_boot[:, i], 5)),
                    "coef_p50": float(np.percentile(coefs_boot[:, i], 50)),
                    "coef_p95": float(np.percentile(coefs_boot[:, i], 95)),
                }
            )
        for gid, y, p in zip(test["oe_game_id"], test["team_a_win"], p_test):
            prediction_rows.append(
                {
                    "model": name,
                    "oe_game_id": gid,
                    "team_a_win": int(y),
                    "predicted_probability_team_a": float(p),
                }
            )
        final[name] = {
            "p_team_a": p_target,
            "p05": float(np.percentile(preds_boot, 5)),
            "p50": float(np.percentile(preds_boot, 50)),
            "p95": float(np.percentile(preds_boot, 95)),
            "bootstrap_mean": float(np.mean(preds_boot)),
            "test_metrics": m,
        }

    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(
        PROCESSED_DIR / "model_comparison.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(coef_rows).to_csv(
        PROCESSED_DIR / "model_coefficients.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(prediction_rows).to_csv(
        PROCESSED_DIR / "model_predictions_test.csv", index=False, encoding="utf-8-sig"
    )

    # Calibration: out-of-fold time-series predictions and the holdout table.
    calib = []
    for label, features in [("primary_core5", FEATURE_SETS[PRIMARY]), ("sensitivity_8", FEATURE_SETS["M4_sensitivity_8"])]:
        oof = oof_predictions(df, features)
        mask = ~np.isnan(oof)
        calib.append(calibration_table(df.loc[mask, "team_a_win"], oof[mask], f"oof_{label}"))
        holdout = test.copy()
        model = fit_model(train, features)
        p = model.predict_proba(holdout[features])[:, 1]
        calib.append(calibration_table(holdout["team_a_win"], p, f"holdout_{label}"))
    calibration = pd.concat(calib, ignore_index=True)
    calibration.to_csv(
        PROCESSED_DIR / "model_calibration.csv", index=False, encoding="utf-8-sig"
    )

    # Target feature contributions for the primary model.
    primary_model = fit_model(df, FEATURE_SETS[PRIMARY])
    scaler = primary_model[0]
    coef = primary_model[-1].coef_[0]
    x = pd.DataFrame([{f: float(target[f]) for f in FEATURE_SETS[PRIMARY]}])
    z = scaler.transform(x)[0]
    contributions = []
    for f, raw, zz, cc in zip(FEATURE_SETS[PRIMARY], x.iloc[0], z, coef):
        contributions.append(
            {
                "feature": f,
                "label": FEATURE_LABELS[f],
                "raw_diff_team_a_minus_b": float(raw),
                "standardized_value": float(zz),
                "standardized_coefficient": float(cc),
                "log_odds_contribution": float(zz * cc),
                "odds_multiplier": float(np.exp(zz * cc)),
            }
        )
    contrib = pd.DataFrame(contributions).sort_values(
        "log_odds_contribution", ascending=False
    )
    contrib.to_csv(
        PROCESSED_DIR / "target_feature_contributions.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Scenario analysis.
    p_primary = final[PRIMARY]["p_team_a"]
    blue_rate = float(df["team_a_win"].mean())
    scenario_rows = [
        ("coin_flip", 0.5, "No-information baseline"),
        ("primary_core5", p_primary, "Primary side-neutral 5-feature model"),
        ("core4", final["M2_core4"]["p_team_a"], "Core 4 features, no objective composite"),
        ("sensitivity_8", final["M4_sensitivity_8"]["p_team_a"], "8-feature sensitivity model"),
        ("win_rate_only", final["M1_win_rate"]["p_team_a"], "Single-feature win-rate baseline"),
        (
            "primary_if_team_a_blue",
            expit(logit(p_primary) + logit(blue_rate)),
            f"Adds observed sample blue-side rate ({blue_rate:.1%}) as a prior",
        ),
        (
            "primary_if_team_a_red",
            expit(logit(p_primary) + logit(1 - blue_rate)),
            f"Adds observed sample red-side rate ({1-blue_rate:.1%}) as a prior",
        ),
    ]
    # Neutralise the edges of one team at a time, whichever side leads each
    # feature. This keeps the scenarios valid for any fixture.
    neutral_b = target.copy()
    neutral_a = target.copy()
    for feature in FEATURE_SETS[PRIMARY]:
        value = float(target[feature])
        if value < 0:
            neutral_b[feature] = 0.0  # team_b leads this feature
        elif value > 0:
            neutral_a[feature] = 0.0  # team_a leads this feature
    scenario_rows.append(
        (
            "neutralise_team_b_edges",
            predict(primary_model, neutral_b, FEATURE_SETS[PRIMARY]),
            "Sets every feature where team_b leads to zero",
        )
    )
    scenario_rows.append(
        (
            "neutralise_team_a_edges",
            predict(primary_model, neutral_a, FEATURE_SETS[PRIMARY]),
            "Sets every feature where team_a leads to zero",
        )
    )
    scenario = pd.DataFrame(
        [
            {
                "scenario": s,
                "p_team_a": p,
                "p_team_b": 1 - p,
                "note": note,
            }
            for s, p, note in scenario_rows
        ]
    )
    scenario.to_csv(
        PROCESSED_DIR / "scenario_analysis.csv", index=False, encoding="utf-8-sig"
    )

    # Predictions for every fixture on the next match day.
    fixtures = pd.read_csv(PROCESSED_DIR / "fixture_features.csv")
    fixture_predictions = build_fixture_predictions(
        df, FEATURE_SETS[PRIMARY], fixtures
    )
    fixture_predictions.to_csv(
        PROCESSED_DIR / "fixture_predictions.csv", index=False, encoding="utf-8-sig"
    )
    target_row = fixture_predictions[
        fixture_predictions["match_id"].astype(str) == str(TARGET_MATCH_ID)
    ]
    target_bo3 = (
        float(target_row["p_team_a_bo3"].iloc[0]) if len(target_row) else float("nan")
    )

    # Collinearity of the primary features, reported instead of hard-coded.
    corr = df[FEATURE_SETS[PRIMARY]].corr().abs()
    max_corr = float(
        max(
            corr.values[i][j]
            for i in range(len(corr))
            for j in range(i + 1, len(corr))
        )
    )

    summary = {
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "target_match": {
            "team_a": TEAM_A,
            "team_b": TEAM_B,
            "code_a": TEAM_A_CODE,
            "code_b": TEAM_B_CODE,
            "start_utc": TARGET_MATCH_START_UTC,
            "collection_cutoff_utc": COLLECTION_CUTOFF_UTC,
        },
        "sample": {
            "modelling_games": int(len(df)),
            "train_games": int(len(train)),
            "test_games": int(len(test)),
            "train_date_min": str(train["date_utc"].min()),
            "train_date_max": str(train["date_utc"].max()),
            "test_date_min": str(test["date_utc"].min()),
            "test_date_max": str(test["date_utc"].max()),
            "split_utc": str(SPLIT_UTC),
            "train_team_a_win_rate": float(train["team_a_win"].mean()),
            "test_team_a_win_rate": float(test["team_a_win"].mean()),
        },
        "primary_model": {
            "name": PRIMARY,
            "features": FEATURE_SETS[PRIMARY],
            "regularization_C": C_FIXED,
            "fit_intercept": False,
            "p_team_a_win": p_primary,
            "p_team_b_win": 1 - p_primary,
            "bootstrap_p05": final[PRIMARY]["p05"],
            "bootstrap_p50": final[PRIMARY]["p50"],
            "bootstrap_p95": final[PRIMARY]["p95"],
            "holdout_metrics": final[PRIMARY]["test_metrics"],
        },
        "model_range": {
            "min_p_team_a": float(min(v["p_team_a"] for v in final.values())),
            "max_p_team_a": float(max(v["p_team_a"] for v in final.values())),
            "models": {k: round(v["p_team_a"], 4) for k, v in final.items()},
        },
        "baseline": {
            "coinflip_brier": float(brier_score_loss(test["team_a_win"], np.full(len(test), 0.5))),
            "coinflip_log_loss": float(log_loss(test["team_a_win"], np.full(len(test), 0.5))),
        },
        "calibration": {
            "holdout_primary": calibration[calibration["sample"] == "holdout_primary_core5"].to_dict("records"),
            "oof_primary": calibration[calibration["sample"] == "oof_primary_core5"].to_dict("records"),
        },
        "observed_blue_side_win_rate": blue_rate,
        "fixtures": fixture_predictions.to_dict("records"),
        "target_series_probability": {
            "p_team_a_bo3": target_bo3,
            "p_team_b_bo3": 1 - target_bo3,
            "assumption": (
                "Per-game probability converted to a best-of-3 series under the "
                "assumption that games are independent and the per-game "
                "probability is constant (no side or draft adaptation)."
            ),
        },
        "headline": (
            f"{TEAM_A_CODE} {p_primary:.1%} vs {TEAM_B_CODE} {1-p_primary:.1%} "
            "per game under the primary side-neutral model; "
            f"{target_bo3:.1%} / {1-target_bo3:.1%} if the series is played "
            "best-of-3. Holdout discrimination is weak (AUC near 0.50), so "
            "treat the fixture as close to a coin flip."
        ),
        "caveats": [
            f"The model is trained on {len(df)} intra-Worlds games from a partial 2026 sample.",
            f"Features are highly collinear (up to {max_corr:.2f} between win rate, gold diff, kill diff and objectives).",
            "The holdout AUC is near 0.50 and Brier/log loss are not better than a coin flip.",
            "The target side (blue/red) is not confirmed; the primary model is side-neutral.",
            "GD@10 is a proxy for GD@15 because the API does not expose GD@15.",
            "Event-level objective rates are stage aggregates, not game-level features.",
            "Best-of-3 series probabilities assume independent games with a constant per-game probability.",
        ],
    }
    (PROCESSED_DIR / "prediction_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
