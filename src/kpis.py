"""KPI layer: team form, head-to-head comparison and target-match snapshot.

Outputs (data/processed):
    team_kpis.csv             one row per Worlds team, last 5/10/20 form
    match_kpis.csv            long-format HLE vs IG comparison
    target_match_features.csv human-readable target feature snapshot
    target_model_input.csv    wide one-row model input (HLE minus IG)
    team_event_stats.csv      cleaned Oracle's Elixir event aggregates
    target_event_stats.csv    key event aggregates for HLE and IG
    kpi_definitions.csv       metric dictionary with formulas and direction

All rolling KPIs are descriptive: they use games up to the collection cutoff
and are never mixed with the target match.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    PROCESSED_DIR,
    RAW_DIR,
    TARGET_MATCH_START_UTC,
    TEAM_A,
    TEAM_A_CODE,
    TEAM_B,
    TEAM_B_CODE,
    TEAM_REGION,
    UPCOMING_FIXTURES,
    WORLDS_TEAMS,
    canonical_team,
)

TARGET_START = pd.Timestamp(TARGET_MATCH_START_UTC)
WINDOWS = (5, 10, 20)
WINDOW_METRICS = {
    "win_rate": "win",
    "gd10": "gd10",
    "gold_diff": "gold_diff",
    "kd_diff": "kill_diff",
    "objective_score": "objective_score",
    "first_blood_rate": "first_blood",
    "duration_min": "duration_min",
}

KEY_EVENTS = {
    TEAM_A: [
        "Worlds 2026 Main Event",
        "LCK 2026 Season Playoffs",
        "LCK 2026 Rounds 3-4",
        "MSI 2026",
    ],
    TEAM_B: [
        "Worlds 2026 Main Event",
        "LPL 2026 Regional Finals",
        "LPL 2026 Grand Finals",
        "LPL 2026 Split 3",
    ],
}


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fact = pd.read_csv(PROCESSED_DIR / "fact_team_games.csv", parse_dates=["date_utc"])
    form = pd.read_csv(PROCESSED_DIR / "team_form.csv", parse_dates=["date_utc"])
    dim = pd.read_csv(PROCESSED_DIR / "dim_games.csv", parse_dates=["date_utc"])
    fact["team"] = fact["team"].map(canonical_team)
    fact["opponent"] = fact["opponent"].map(canonical_team)
    form["team"] = form["team"].map(canonical_team)
    form["opponent"] = form["opponent"].map(canonical_team)
    dim["blue_team"] = dim["blue_team"].map(canonical_team)
    dim["red_team"] = dim["red_team"].map(canonical_team)
    return fact, form, dim


def pct(value) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "")
    try:
        return float(text)
    except ValueError:
        return np.nan


def load_event_stats() -> pd.DataFrame:
    rows = []
    for path in sorted((RAW_DIR / "team_stats_by_event").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for record in payload:
            row = dict(record)
            row["team"] = canonical_team(
                path.stem.replace("_", " ")
            )  # replaced below with a reliable lookup
            row["_file"] = path.name
            rows.append(row)
    df = pd.DataFrame(rows)
    # Recover exact team names from the game table instead of guessing from
    # filenames (apostrophes and accented characters make slugs ambiguous).
    team_codes = (
        pd.read_csv(PROCESSED_DIR / "fact_team_games.csv")[["team", "team_code"]]
        .drop_duplicates()
        .assign(team=lambda d: d["team"].map(canonical_team))
        .set_index("team_code")["team"]
    )
    # Filename -> canonical team via the same safe_name convention used to
    # collect the files. Build the mapping from the known Worlds team list.
    def safe_name(value: str) -> str:
        return "".join(c if c.isalnum() else "_" for c in value).strip("_")

    file_to_team = {f"{safe_name(t)}.json": t for t in WORLDS_TEAMS}
    df["team"] = df["_file"].map(file_to_team)
    df = df.drop(columns=["_file"])
    for col in [c for c in df.columns if c.endswith("%")]:
        df[col] = df[col].map(pct)
    df["GSPD"] = df["GSPD"].map(pct)
    df["GP"] = pd.to_numeric(df["GP"], errors="coerce")
    df["W"] = pd.to_numeric(df["W"], errors="coerce")
    df["L"] = pd.to_numeric(df["L"], errors="coerce")
    for col in ["EGR", "MLR", "CKPM", "KD", "GPR", "JNG%", "LNE%", "WPM", "CWPM"]:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[df["team"].isin(WORLDS_TEAMS)].copy()
    return df.sort_values(["team", "Event"]).reset_index(drop=True)


def window_stats(team_games: pd.DataFrame, window: int) -> dict:
    d = team_games.sort_values(["date_utc", "oe_game_id"]).tail(window)
    if d.empty:
        return {}
    return {
        "games": int(len(d)),
        "wins": int(d["win"].sum()),
        "losses": int((1 - d["win"]).sum()),
        "win_rate": float(d["win"].mean()),
        "gd10": float(d["gd10"].mean()),
        "gd10_games": int(d["gd10"].notna().sum()),
        "gold_diff": float(d["gold_diff"].mean()),
        "kd_diff": float(d["kill_diff"].mean()),
        "objective_score": float(d["objective_score"].mean()),
        "first_blood_rate": float(d["first_blood"].mean()),
        "duration_min": float(d["duration_min"].mean()),
        "kills": float(d["kills"].mean()),
        "deaths": float(d["deaths"].mean()),
        "towers": float(d["towers"].mean()),
        "dragons": float(d["dragons"].mean()),
        "barons": float(d["barons"].mean()),
        "sos": float(d["opp_wr_10"].mean()) if "opp_wr_10" in d else np.nan,
        "last_game_utc": d["date_utc"].max(),
        "rest_days": float(
            (TARGET_START - d["date_utc"].max()).total_seconds() / 86400
        ),
    }


def build_team_kpis(fact: pd.DataFrame, form: pd.DataFrame) -> pd.DataFrame:
    fact = fact.merge(
        form[["oe_game_id", "team", "opp_wr_10"]],
        on=["oe_game_id", "team"],
        how="left",
    )
    rows = []
    for team in WORLDS_TEAMS:
        d = fact[fact["team"] == team].copy()
        if d.empty:
            continue
        vs_worlds = d[d["opponent"].isin(WORLDS_TEAMS)]
        worlds_2026 = d[d["tournament"].astype(str).str.startswith("Worlds 2026")]
        row = {
            "team": team,
            "team_code": d["team_code"].mode().iloc[0] if d["team_code"].notna().any() else "",
            "region": TEAM_REGION.get(team, "Unknown"),
            "games_in_sample": int(len(d)),
            "first_game_utc": d["date_utc"].min(),
            "last_game_utc": d["date_utc"].max(),
            "wins_all": int(d["win"].sum()),
            "losses_all": int((1 - d["win"]).sum()),
            "win_rate_all": float(d["win"].mean()),
            "games_vs_worlds": int(len(vs_worlds)),
            "wins_vs_worlds": int(vs_worlds["win"].sum()),
            "losses_vs_worlds": int((1 - vs_worlds["win"]).sum()),
            "win_rate_vs_worlds": float(vs_worlds["win"].mean())
            if len(vs_worlds)
            else np.nan,
            "worlds_2026_games": int(len(worlds_2026)),
            "worlds_2026_wins": int(worlds_2026["win"].sum()),
            "worlds_2026_losses": int((1 - worlds_2026["win"]).sum()),
            "worlds_2026_win_rate": float(worlds_2026["win"].mean())
            if len(worlds_2026)
            else np.nan,
        }
        for w in WINDOWS:
            stats = window_stats(d, w)
            for key, value in stats.items():
                if key in {"games", "wins", "losses", "gd10_games"}:
                    row[f"last{w}_{key}"] = value
                elif key in {"last_game_utc", "rest_days"}:
                    row[key if key == "rest_days" else f"last{w}_last_game_utc"] = value
                else:
                    row[f"last{w}_{key}"] = value
        rows.append(row)
    out = pd.DataFrame(rows)
    # Descriptive form index: average z-score across four last-10 metrics.
    components = [
        "last10_win_rate",
        "last10_gold_diff",
        "last10_kd_diff",
        "last10_objective_score",
    ]
    z = out[components].apply(lambda s: (s - s.mean()) / s.std(ddof=0))
    out["form_index_last10"] = z.mean(axis=1)
    out["form_rank_last10"] = out["form_index_last10"].rank(
        ascending=False, method="min"
    ).astype(int)
    return out.sort_values("form_rank_last10").reset_index(drop=True)


def build_match_kpis(team_kpis: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    defs = kpi_definitions().set_index("metric")

    def add(metric, window, hle, ig, definition):
        if pd.isna(hle) and pd.isna(ig):
            return
        diff = hle - ig if pd.notna(hle) and pd.notna(ig) else np.nan
        lower_better = {
            "deaths",
            "duration_min",
            "losses_vs_worlds",
            "worlds_2026_losses",
            "event_losses",
        }
        if pd.isna(diff):
            better = "n/a"
        elif metric in lower_better:
            better = TEAM_A_CODE if diff < 0 else TEAM_B_CODE if diff > 0 else "Tie"
        else:
            better = TEAM_A_CODE if diff > 0 else TEAM_B_CODE if diff < 0 else "Tie"
        rows.append(
            {
                "metric": metric,
                "window": window,
                "hle_value": hle,
                "ig_value": ig,
                "diff_hle_minus_ig": diff,
                "better_team": better,
                "definition": definition,
            }
        )

    hle = team_kpis[team_kpis["team"] == TEAM_A].iloc[0]
    ig = team_kpis[team_kpis["team"] == TEAM_B].iloc[0]
    context = {
        "games_in_sample": "Games available in the collected 2026 sample",
        "wins_vs_worlds": "Wins against the 16 Worlds 2026 teams in sample",
        "losses_vs_worlds": "Losses against the 16 Worlds 2026 teams in sample",
        "win_rate_vs_worlds": "Win rate against the 16 Worlds 2026 teams in sample",
        "worlds_2026_wins": "Wins at Worlds 2026 Main Event / Play-In in sample",
        "worlds_2026_losses": "Losses at Worlds 2026 Main Event / Play-In in sample",
        "worlds_2026_win_rate": "Win rate at Worlds 2026 Main Event / Play-In in sample",
        "rest_days": "Days between last recorded game and target match start",
        "form_index_last10": "Mean z-score of last-10 win rate, gold diff, kill diff and objective score",
    }
    for metric, definition in context.items():
        add(metric, "sample", hle.get(metric, np.nan), ig.get(metric, np.nan), definition)

    for w in WINDOWS:
        for metric in [
            "win_rate",
            "gd10",
            "gold_diff",
            "kd_diff",
            "objective_score",
            "first_blood_rate",
            "duration_min",
            "kills",
            "deaths",
            "towers",
            "dragons",
            "barons",
            "sos",
        ]:
            col = f"last{w}_{metric}"
            add(
                metric,
                f"last{w}",
                hle.get(col, np.nan),
                ig.get(col, np.nan),
                defs.loc[metric, "definition"] if metric in defs.index else "",
            )

    for team, label in [(TEAM_A, TEAM_A_CODE), (TEAM_B, TEAM_B_CODE)]:
        subset = events[(events["team"] == team) & (events["Event"].isin(KEY_EVENTS[team]))]
        for _, r in subset.iterrows():
            # Accumulate into a temporary dict keyed by event so both teams
            # land on the same rows.
            rows.append(
                {
                    "metric": "event_snapshot",
                    "window": r["Event"],
                    "team": label,
                    "event_games": r.get("GP"),
                    "event_wins": r.get("W"),
                    "event_losses": r.get("L"),
                    "event_gspd_pct": r.get("GSPD"),
                    "event_egr": r.get("EGR"),
                    "event_mlr": r.get("MLR"),
                    "event_first_blood_pct": r.get("FB%"),
                    "event_first_tower_pct": r.get("FT%"),
                    "event_first_dragon_pct": r.get("FD%"),
                    "event_dragon_pct": r.get("DRG%"),
                    "event_baron_pct": r.get("BN%"),
                }
            )
    out = pd.DataFrame(rows)
    # Pivot event snapshots into one row per event with HLE/IG values.
    event_rows = out[out["metric"] == "event_snapshot"].copy()
    other = out[out["metric"] != "event_snapshot"].copy()
    event_out = []
    for event in event_rows["window"].drop_duplicates():
        e = event_rows[event_rows["window"] == event]
        h = e[e["team"] == TEAM_A_CODE]
        i = e[e["team"] == TEAM_B_CODE]
        h = h.iloc[0] if len(h) else None
        i = i.iloc[0] if len(i) else None
        for metric in [
            "event_games",
            "event_wins",
            "event_losses",
            "event_gspd_pct",
            "event_egr",
            "event_mlr",
            "event_first_blood_pct",
            "event_first_tower_pct",
            "event_first_dragon_pct",
            "event_dragon_pct",
            "event_baron_pct",
        ]:
            hv = h[metric] if h is not None else np.nan
            iv = i[metric] if i is not None else np.nan
            diff = hv - iv if pd.notna(hv) and pd.notna(iv) else np.nan
            event_out.append(
                {
                    "metric": metric,
                    "window": event,
                    "hle_value": hv,
                    "ig_value": iv,
                    "diff_hle_minus_ig": diff,
                    "better_team": TEAM_A_CODE
                    if pd.notna(diff) and diff > 0
                    else TEAM_B_CODE
                    if pd.notna(diff) and diff < 0
                    else "Tie",
                    "definition": "Oracle's Elixir event aggregate; not a game-level rate",
                }
            )
    return pd.concat([other, pd.DataFrame(event_out)], ignore_index=True)


def target_snapshot(fact: pd.DataFrame, form: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    fact = fact.merge(
        form[["oe_game_id", "team", "opp_wr_10"]],
        on=["oe_game_id", "team"],
        how="left",
    )
    rows = []
    raw = {}
    for team, code in [(TEAM_A, TEAM_A_CODE), (TEAM_B, TEAM_B_CODE)]:
        d = fact[fact["team"] == team].sort_values(["date_utc", "oe_game_id"]).tail(10)
        stats = window_stats(d, 10)
        raw[code] = stats
        for metric, value in stats.items():
            if metric in {"last_game_utc", "games"}:
                continue
            rows.append(
                {
                    "team": team,
                    "team_code": code,
                    "window": "last10",
                    "metric": metric,
                    "value": value,
                    "definition": kpi_definitions()
                    .set_index("metric")
                    .get("definition", pd.Series(dtype=str))
                    .get(metric, ""),
                }
            )
    long = pd.DataFrame(rows)
    # Wide model input: HLE minus IG, plus metadata for auditability.
    mapping = {
        "win_rate": "wr_10_diff",
        "gd10": "gd10_10_diff",
        "gold_diff": "gold_diff_10_diff",
        "kd_diff": "kd_diff_10_diff",
        "objective_score": "obj_10_diff",
        "first_blood_rate": "fb_rate_10_diff",
        "duration_min": "duration_10_diff",
        "sos": "sos_10_diff",
    }
    wide = {v: raw[TEAM_A_CODE][k] - raw[TEAM_B_CODE][k] for k, v in mapping.items()}
    wide.update(
        {
            "team_a_last_game_utc": raw[TEAM_A_CODE]["last_game_utc"].isoformat(),
            "team_b_last_game_utc": raw[TEAM_B_CODE]["last_game_utc"].isoformat(),
            "team_a_rest_days": raw[TEAM_A_CODE]["rest_days"],
            "team_b_rest_days": raw[TEAM_B_CODE]["rest_days"],
            "team_a_gd10_games": raw[TEAM_A_CODE]["gd10_games"],
            "team_b_gd10_games": raw[TEAM_B_CODE]["gd10_games"],
        }
    )
    return long, pd.DataFrame([wide])


def kpi_definitions() -> pd.DataFrame:
    rows = [
        ("win_rate", "Share of games won in the window.", "wins / games", "Higher is better"),
        ("gd10", "Average gold difference at 10 minutes, summed over five players. Proxy for GD@15, which the API does not expose.", "mean(sum(player gxd10))", "Higher is better"),
        ("gold_diff", "Average final gold difference.", "mean(team gold - opponent gold)", "Higher is better"),
        ("kd_diff", "Average kill differential.", "mean(kills - deaths)", "Higher is better"),
        ("objective_score", "Composite objective differential.", "mean(tower_diff + dragon_diff + 2 x baron_diff)", "Higher is better"),
        ("first_blood_rate", "Share of games in which the team secured first blood.", "games with first blood / games", "Higher is better"),
        ("duration_min", "Average game duration in minutes.", "mean(game duration / 60)", "Context only"),
        ("kills", "Average kills per game.", "mean(kills)", "Context only"),
        ("deaths", "Average deaths per game.", "mean(deaths)", "Lower is better"),
        ("towers", "Average towers destroyed per game.", "mean(towers)", "Higher is better"),
        ("dragons", "Average dragons secured per game.", "mean(dragons)", "Higher is better"),
        ("barons", "Average barons secured per game.", "mean(barons)", "Higher is better"),
        ("sos", "Strength of schedule: average pre-game 10-game win rate of the previous 10 opponents.", "mean(opponent pre-game wr_10)", "Higher means tougher schedule"),
        ("rest_days", "Days between the team's last recorded game and the target match start.", "(match_start - last_game) / 1 day", "Context only"),
        ("form_index_last10", "Descriptive composite of last-10 win rate, gold diff, kill diff and objective score.", "mean of z-scores", "Higher is better"),
        ("event_gspd_pct", "Oracle's Elixir gold share percentage difference for the event.", "event GSPD", "Higher is better"),
        ("event_egr", "Oracle's Elixir EGR rating for the event.", "event EGR", "Higher is better"),
        ("event_mlr", "Oracle's Elixir MLR rating for the event.", "event MLR", "Higher is better"),
        ("event_first_blood_pct", "Share of event games with first blood.", "event FB%", "Higher is better"),
        ("event_first_tower_pct", "Share of event games with first tower.", "event FT%", "Higher is better"),
        ("event_first_dragon_pct", "Share of event games with first dragon.", "event FD%", "Higher is better"),
        ("event_dragon_pct", "Event dragon control percentage.", "event DRG%", "Higher is better"),
        ("event_baron_pct", "Event baron control percentage.", "event BN%", "Higher is better"),
    ]
    return pd.DataFrame(rows, columns=["metric", "definition", "formula", "direction"])


def build_fixture_features(fact: pd.DataFrame, form: pd.DataFrame) -> pd.DataFrame:
    """One row per upcoming fixture with the pre-game feature vector.

    The feature convention matches the model: the difference of the two teams'
    last-10 means (team_a minus team_b). Because the fixtures have not been
    played, the "last 10" are the ten most recent games of each team before
    the collection cutoff.
    """
    fact = fact.merge(
        form[["oe_game_id", "team", "opp_wr_10"]],
        on=["oe_game_id", "team"],
        how="left",
    )
    mapping = {
        "win_rate": "wr_10_diff",
        "gd10": "gd10_10_diff",
        "gold_diff": "gold_diff_10_diff",
        "kd_diff": "kd_diff_10_diff",
        "objective_score": "obj_10_diff",
        "first_blood_rate": "fb_rate_10_diff",
        "duration_min": "duration_10_diff",
        "sos": "sos_10_diff",
    }
    rows = []
    codes = (
        fact[["team", "team_code"]]
        .dropna()
        .drop_duplicates("team")
        .set_index("team")["team_code"]
        .to_dict()
    )
    for fixture in UPCOMING_FIXTURES:
        team_a, team_b = fixture["team_a"], fixture["team_b"]
        a = fact[fact["team"] == team_a].sort_values(["date_utc", "oe_game_id"]).tail(10)
        b = fact[fact["team"] == team_b].sort_values(["date_utc", "oe_game_id"]).tail(10)
        stats_a = window_stats(a, 10)
        stats_b = window_stats(b, 10)
        row = {
            "match_id": fixture["match_id"],
            "team_a": team_a,
            "team_b": team_b,
            "team_a_code": codes.get(team_a, ""),
            "team_b_code": codes.get(team_b, ""),
            "start_utc": fixture["start_utc"],
            "series_type": fixture["series_type"],
            "block": fixture.get("block", ""),
            "team_a_games": int(stats_a.get("games", 0)),
            "team_b_games": int(stats_b.get("games", 0)),
            "team_a_win_rate": stats_a.get("win_rate", np.nan),
            "team_b_win_rate": stats_b.get("win_rate", np.nan),
            "team_a_last_game_utc": str(stats_a.get("last_game_utc", "")),
            "team_b_last_game_utc": str(stats_b.get("last_game_utc", "")),
            "team_a_rest_days": stats_a.get("rest_days", np.nan),
            "team_b_rest_days": stats_b.get("rest_days", np.nan),
        }
        for key, feature in mapping.items():
            row[feature] = float(stats_a.get(key, np.nan)) - float(stats_b.get(key, np.nan))
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    fact, form, dim = load_inputs()
    events = load_event_stats()

    team_kpis = build_team_kpis(fact, form)
    match_kpis = build_match_kpis(team_kpis, events)
    target_long, target_wide = target_snapshot(fact, form)
    fixture_features = build_fixture_features(fact, form)

    team_kpis.to_csv(PROCESSED_DIR / "team_kpis.csv", index=False, encoding="utf-8-sig")
    match_kpis.to_csv(PROCESSED_DIR / "match_kpis.csv", index=False, encoding="utf-8-sig")
    target_long.to_csv(
        PROCESSED_DIR / "target_match_features.csv", index=False, encoding="utf-8-sig"
    )
    target_wide.to_csv(
        PROCESSED_DIR / "target_model_input.csv", index=False, encoding="utf-8-sig"
    )
    fixture_features.to_csv(
        PROCESSED_DIR / "fixture_features.csv", index=False, encoding="utf-8-sig"
    )
    events.to_csv(
        PROCESSED_DIR / "team_event_stats.csv", index=False, encoding="utf-8-sig"
    )
    key = events[events.apply(lambda r: r["Event"] in KEY_EVENTS.get(r["team"], []), axis=1)]
    key.to_csv(
        PROCESSED_DIR / "target_event_stats.csv", index=False, encoding="utf-8-sig"
    )
    kpi_definitions().to_csv(
        PROCESSED_DIR / "kpi_definitions.csv", index=False, encoding="utf-8-sig"
    )

    summary = {
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "target_start_utc": TARGET_MATCH_START_UTC,
        "teams": int(len(team_kpis)),
        "target_features": target_wide.iloc[0].to_dict(),
        "team_a_form_rank": int(
            team_kpis.loc[team_kpis["team"] == TEAM_A, "form_rank_last10"].iloc[0]
        ),
        "team_b_form_rank": int(
            team_kpis.loc[team_kpis["team"] == TEAM_B, "form_rank_last10"].iloc[0]
        ),
        "fixtures": fixture_features.to_dict("records"),
    }
    (PROCESSED_DIR / "kpi_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
