"""Export Power BI-ready CSV tables.

The processed tables are analysis-friendly; Power BI prefers explicit keys,
date-only columns and stable snake_case names. This script creates a star-schema
folder at data/powerbi/ so the dashboard can be built without reshaping data in
Power Query.

Usage:
    python src/export_powerbi.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    POWERBI_DIR,
    PROCESSED_DIR,
    TARGET_MATCH_START_UTC,
    TEAM_A,
    TEAM_A_CODE,
    TEAM_B,
    TEAM_B_CODE,
    TEAM_REGION,
    WORLDS_TEAMS,
    canonical_team,
)

TARGET_DATE = pd.Timestamp(TARGET_MATCH_START_UTC).date()


def date_key(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series).dt.strftime("%Y%m%d").astype("Int64")


def add_date(df: pd.DataFrame, date_col: str = "date_utc") -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out[date_col], utc=True).dt.date
    out["date_key"] = date_key(out["date"])
    return out.drop(columns=[date_col])


def team_codes(fact: pd.DataFrame) -> dict[str, str]:
    return (
        fact[["team", "team_code"]]
        .dropna()
        .drop_duplicates()
        .set_index("team")["team_code"]
        .to_dict()
    )


def build_dim_date(fact: pd.DataFrame) -> pd.DataFrame:
    dates = pd.to_datetime(fact["date_utc"], utc=True).dt.date
    full = pd.date_range(min(dates), max(max(dates), TARGET_DATE), freq="D")
    df = pd.DataFrame({"date": [d.date() for d in full]})
    df["date_key"] = date_key(df["date"])
    df["year"] = pd.to_datetime(df["date"]).dt.year
    df["quarter"] = "Q" + pd.to_datetime(df["date"]).dt.quarter.astype(str)
    df["month"] = pd.to_datetime(df["date"]).dt.month
    df["month_name"] = pd.to_datetime(df["date"]).dt.strftime("%b")
    df["year_month"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m")
    df["week"] = pd.to_datetime(df["date"]).dt.isocalendar().week.astype(int)
    df["day_of_week"] = pd.to_datetime(df["date"]).dt.day_of_week + 1
    df["day_name"] = pd.to_datetime(df["date"]).dt.strftime("%a")
    df["is_weekend"] = df["day_of_week"].isin([6, 7]).astype(int)
    df["is_target_date"] = (df["date"] == TARGET_DATE).astype(int)
    return df


def build_dim_team(fact: pd.DataFrame) -> pd.DataFrame:
    """Build a complete team dimension.

    The fact table contains opponents outside the 16-team Worlds cohort. A
    dimension that only listed the cohort would leave those foreign keys
    unmatched in Power BI, so every observed team is included and the cohort is
    flagged with ``is_worlds_cohort``.
    """
    rows = []
    teams = sorted(set(fact["team"].dropna()) | set(WORLDS_TEAMS))
    for team in teams:
        d = fact[fact["team"] == team]
        code = d["team_code"].mode().iloc[0] if not d.empty and d["team_code"].notna().any() else ""
        rows.append(
            {
                "team": team,
                "team_code": code,
                "region": TEAM_REGION.get(team, "Unknown"),
                "is_target_team": int(team in {TEAM_A, TEAM_B}),
                "is_hle": int(team == TEAM_A),
                "is_ig": int(team == TEAM_B),
                "is_worlds_cohort": int(team in WORLDS_TEAMS),
                "games_in_sample": int(len(d)),
            }
        )
    return pd.DataFrame(rows)


def build_dim_game(dim: pd.DataFrame) -> pd.DataFrame:
    out = add_date(dim)
    out["winner"] = np.where(out["blue_win"] == 1, out["blue_team"], out["red_team"])
    out["match_id"] = out["match_id"].astype(str)
    out["blue_gold_diff"] = out["blue_gold"] - out["red_gold"]
    out["blue_objective_score"] = (
        (out["blue_towers"] - out["red_towers"])
        + (out["blue_dragons"] - out["red_dragons"])
        + 2 * (out["blue_barons"] - out["red_barons"])
    )
    return out


def build_fact_team_game(fact: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "oe_game_id",
        "date_utc",
        "match_id",
        "tournament",
        "patch",
        "team",
        "team_code",
        "opponent",
        "opponent_code",
        "side",
        "win",
        "duration_min",
        "kills",
        "deaths",
        "assists",
        "gold",
        "opp_gold",
        "gold_diff",
        "gd10",
        "gd10_players",
        "towers",
        "dragons",
        "barons",
        "objective_score",
        "first_blood",
        "gspd",
        "egr",
        "kill_diff",
    ]
    out = add_date(fact[cols])
    out["match_id"] = out["match_id"].astype(str)
    out["is_hle"] = (out["team"] == TEAM_A).astype(int)
    out["is_ig"] = (out["team"] == TEAM_B).astype(int)
    return out


def build_fact_team_form(form: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "oe_game_id",
        "date_utc",
        "team",
        "opponent",
        "win",
        "prior_games",
        "wr_5",
        "wr_10",
        "wr_20",
        "gd10_10",
        "gold_diff_10",
        "kd_diff_10",
        "obj_10",
        "fb_rate_10",
        "duration_10",
        "sos_10",
        "opp_wr_10",
        "rest_days",
    ]
    out = add_date(form[cols])
    return out


def build_event(fact: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_DIR / "team_event_stats.csv")
    codes = team_codes(fact)
    renames = {
        "FB%": "first_blood_pct",
        "FT%": "first_tower_pct",
        "FD%": "first_dragon_pct",
        "F3T%": "first_three_towers_pct",
        "DRG%": "dragon_pct",
        "BN%": "baron_pct",
        "HLD%": "herald_pct",
        "ELD%": "elder_pct",
        "LNE%": "lane_pct",
        "JNG%": "jungle_pct",
        "GSPD": "gold_share_pct_diff",
        "EGR": "egr",
        "MLR": "mlr",
        "CKPM": "ckpm",
        "KD": "kd",
        "GPR": "gpr",
        "WPM": "wpm",
        "CWPM": "cwpm",
        "GP": "games",
        "W": "wins",
        "L": "losses",
        "Event": "event",
    }
    df = df.rename(columns=renames)
    df["team_code"] = df["team"].map(codes)
    df["is_key_event"] = df["event"].isin(
        [
            "Worlds 2026 Main Event",
            "LCK 2026 Season Playoffs",
            "LCK 2026 Rounds 3-4",
            "MSI 2026",
            "LPL 2026 Regional Finals",
            "LPL 2026 Grand Finals",
            "LPL 2026 Split 3",
        ]
    ).astype(int)
    return df.sort_values(["team", "event"]).reset_index(drop=True)


def build_match_kpi() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_DIR / "match_kpis.csv")
    df["match_label"] = f"{TEAM_A_CODE} vs {TEAM_B_CODE}"
    return df


def build_target_feature() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_DIR / "target_match_features.csv")
    return df


def build_team_kpi() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_DIR / "team_kpis.csv")
    return df


def build_prediction() -> pd.DataFrame:
    summary = json.loads((PROCESSED_DIR / "prediction_summary.json").read_text(encoding="utf-8"))
    comparison = pd.read_csv(PROCESSED_DIR / "model_comparison.csv").set_index("model")
    rows = []
    label_map = {
        "M0_coinflip": "Coin flip",
        "M1_win_rate": "Win rate only",
        "M2_core4": "Core 4",
        "M3_core5": "Core 5 (primary)",
        "M4_sensitivity_8": "8-feature sensitivity",
    }
    for model, p in summary["model_range"]["models"].items():
        m = comparison.loc[model] if model in comparison.index else None
        rows.append(
            {
                "model": label_map.get(model, model),
                "model_id": model,
                "p_hle": p,
                "p_ig": 1 - p,
                "is_primary": int(model == "M3_core5"),
                "holdout_accuracy": float(m["accuracy"]) if m is not None else np.nan,
                "holdout_brier": float(m["brier"]) if m is not None else np.nan,
                "holdout_log_loss": float(m["log_loss"]) if m is not None else np.nan,
                "holdout_auc": float(m["auc"]) if m is not None else np.nan,
                "bootstrap_p05": summary["primary_model"]["bootstrap_p05"]
                if model == "M3_core5"
                else np.nan,
                "bootstrap_p50": summary["primary_model"]["bootstrap_p50"]
                if model == "M3_core5"
                else np.nan,
                "bootstrap_p95": summary["primary_model"]["bootstrap_p95"]
                if model == "M3_core5"
                else np.nan,
                "generated_at_utc": summary["generated_at_utc"],
                "match_start_utc": summary["target_match"]["start_utc"],
                "sample_games": summary["sample"]["modelling_games"],
                "train_games": summary["sample"]["train_games"],
                "test_games": summary["sample"]["test_games"],
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    POWERBI_DIR.mkdir(parents=True, exist_ok=True)
    fact = pd.read_csv(PROCESSED_DIR / "fact_team_games.csv", parse_dates=["date_utc"])
    form = pd.read_csv(PROCESSED_DIR / "team_form.csv", parse_dates=["date_utc"])
    dim = pd.read_csv(PROCESSED_DIR / "dim_games.csv", parse_dates=["date_utc"])

    tables = {
        "DimDate.csv": build_dim_date(fact),
        "DimTeam.csv": build_dim_team(fact),
        "DimGame.csv": build_dim_game(dim),
        "FactTeamGame.csv": build_fact_team_game(fact),
        "FactTeamForm.csv": build_fact_team_form(form),
        "FactTeamEventStat.csv": build_event(fact),
        "FactTeamKPI.csv": build_team_kpi(),
        "FactMatchKPI.csv": build_match_kpi(),
        "FactTargetFeature.csv": build_target_feature(),
        "FactModelMetric.csv": pd.read_csv(PROCESSED_DIR / "model_comparison.csv"),
        "FactModelCoefficient.csv": pd.read_csv(PROCESSED_DIR / "model_coefficients.csv"),
        "FactModelCalibration.csv": pd.read_csv(PROCESSED_DIR / "model_calibration.csv"),
        "FactFeatureContribution.csv": pd.read_csv(PROCESSED_DIR / "target_feature_contributions.csv"),
        "FactScenario.csv": pd.read_csv(PROCESSED_DIR / "scenario_analysis.csv"),
        "FactPrediction.csv": build_prediction(),
        "DimMetric.csv": pd.read_csv(PROCESSED_DIR / "kpi_definitions.csv"),
    }
    for filename, df in tables.items():
        df.to_csv(POWERBI_DIR / filename, index=False, encoding="utf-8-sig")
        print(f"wrote {filename}: {len(df):,} rows x {len(df.columns)} cols")


if __name__ == "__main__":
    main()
