"""Build clean, analysis-ready datasets from the raw Oracle's Elixir API data.

Outputs (data/processed):
    fact_team_games.csv      one row per team per game (analysis + Power BI)
    dim_games.csv            one row per game
    team_form.csv            pre-game rolling form for every team-game
    model_dataset.csv        one row per game between Worlds teams, with
                             pre-game difference features and the result
    data_quality_report.json validation results and missingness

All rolling features use only games played before the row's game. The target
match is never included.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    COLLECTION_CUTOFF_UTC,
    PROCESSED_DIR,
    RAW_DIR,
    TARGET_MATCH_ID,
    TEAM_A,
    TEAM_B,
    WORLDS_TEAMS,
    canonical_team,
)


RAW_GAMES = RAW_DIR / "game_details"
TARGET_START = pd.Timestamp("2026-10-25T17:00:00Z")


def load_game_lists() -> pd.DataFrame:
    rows = []
    for path in sorted((RAW_DIR / "team_game_lists").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(data)
    df = pd.DataFrame(rows)
    # One game can appear in two teams' lists; keep the first identical record.
    df = df.drop_duplicates(subset=["oeGameId"], keep="first")
    return df


def load_details() -> list[dict]:
    games = []
    for path in sorted(RAW_GAMES.glob("*.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        if not payload:
            continue
        game = payload[0]
        if game.get("metadata", {}).get("state") != "completed":
            continue
        games.append(game)
    return games


def player_sum(players: dict, field: str) -> float:
    vals = [p.get(field) for p in players.values() if isinstance(p, dict)]
    vals = [v for v in vals if v is not None]
    return float(sum(vals)) if vals else np.nan


def player_count(players: dict, field: str) -> int:
    vals = [p.get(field) for p in players.values() if isinstance(p, dict)]
    return sum(v is not None for v in vals)


def team_row(game: dict, side: str, game_meta: dict) -> dict:
    blue = game["blueTeam"]
    red = game["redTeam"]
    own = blue if side == "blue" else red
    opp = red if side == "blue" else blue
    own_stats = own.get("teamStats", {}) or {}
    opp_stats = opp.get("teamStats", {}) or {}
    own_players = own.get("players", {}) or {}
    opp_players = opp.get("players", {}) or {}
    metadata = game.get("metadata", {})

    gd10 = player_sum(own_players, "gxd10")
    gd10_n = player_count(own_players, "gxd10")
    fb_kills = player_sum(own_players, "firstBloodKill")
    fb_assists = player_sum(own_players, "firstBloodAssist")
    first_blood = int((fb_kills or 0) + (fb_assists or 0) > 0)

    gold = own_stats.get("gold")
    opp_gold = opp_stats.get("gold")
    duration = metadata.get("gameDuration")
    duration_min = round(duration / 60, 2) if duration else np.nan

    return {
        "oe_game_id": game.get("gameId"),
        "match_id": game_meta.get("matchId"),
        "game_in_match": game_meta.get("gameInMatch"),
        "date_utc": metadata.get("gameCreation"),
        "tournament": (metadata.get("tournament") or {}).get("name")
        or game_meta.get("tournament"),
        "patch": metadata.get("patch"),
        "team": canonical_team(own.get("teamName")),
        "team_code": own.get("teamCode"),
        "opponent": canonical_team(opp.get("teamName")),
        "opponent_code": opp.get("teamCode"),
        "side": side,
        "win": int(own_stats.get("result", 0) or 0),
        "duration_min": duration_min,
        "kills": own_stats.get("kills"),
        "deaths": own_stats.get("deaths"),
        "assists": player_sum(own_players, "assists"),
        "gold": gold,
        "opp_gold": opp_gold,
        "gold_diff": (gold - opp_gold) if gold is not None and opp_gold is not None else np.nan,
        "gd10": gd10,
        "gd10_players": gd10_n,
        "towers": own_stats.get("towers"),
        "opp_towers": opp_stats.get("towers"),
        "tower_diff": (own_stats.get("towers") or 0) - (opp_stats.get("towers") or 0),
        "dragons": len(own_stats.get("dragons") or []),
        "opp_dragons": len(opp_stats.get("dragons") or []),
        "dragon_diff": len(own_stats.get("dragons") or [])
        - len(opp_stats.get("dragons") or []),
        "barons": own_stats.get("barons"),
        "opp_barons": opp_stats.get("barons"),
        "baron_diff": (own_stats.get("barons") or 0) - (opp_stats.get("barons") or 0),
        # Composite objective score: towers + dragons + 2 x barons. Barons are
        # weighted twice because they convert most directly into map pressure.
        "objective_score": (
            ((own_stats.get("towers") or 0) - (opp_stats.get("towers") or 0))
            + (len(own_stats.get("dragons") or []) - len(opp_stats.get("dragons") or []))
            + 2 * ((own_stats.get("barons") or 0) - (opp_stats.get("barons") or 0))
        ),
        "inhibitors": own_stats.get("inhibitors"),
        "opp_inhibitors": opp_stats.get("inhibitors"),
        "inhibitor_diff": (own_stats.get("inhibitors") or 0)
        - (opp_stats.get("inhibitors") or 0),
        "first_blood": first_blood,
        "gspd": own_stats.get("gspd"),
        "egr": own_stats.get("egr"),
        "kill_death_ratio": (
            own_stats.get("kills") / own_stats.get("deaths")
            if own_stats.get("deaths")
            else np.nan
        ),
        "kill_diff": (own_stats.get("kills") or 0) - (opp_stats.get("kills") or 0),
    }


def build_fact(games: list[dict], game_lists: pd.DataFrame) -> pd.DataFrame:
    meta = game_lists.set_index("oeGameId").to_dict("index")
    rows = []
    for game in games:
        gid = game.get("gameId")
        gmeta = meta.get(gid, {})
        for side in ("blue", "red"):
            rows.append(team_row(game, side, gmeta))
    df = pd.DataFrame(rows)
    df["date_utc"] = pd.to_datetime(df["date_utc"], utc=True, errors="coerce")
    df = df[df["date_utc"] < TARGET_START].copy()
    df = df[df["match_id"] != TARGET_MATCH_ID].copy()
    df = df.drop_duplicates(subset=["oe_game_id", "team"], keep="first")
    df = df.sort_values(["date_utc", "oe_game_id", "side"]).reset_index(drop=True)
    return df


def build_dim_games(games: list[dict], game_lists: pd.DataFrame) -> pd.DataFrame:
    meta = game_lists.set_index("oeGameId").to_dict("index")
    rows = []
    for game in games:
        gid = game.get("gameId")
        gmeta = meta.get(gid, {})
        blue = game["blueTeam"]
        red = game["redTeam"]
        md = game.get("metadata", {})
        rows.append(
            {
                "oe_game_id": gid,
                "match_id": gmeta.get("matchId"),
                "game_in_match": gmeta.get("gameInMatch"),
                "date_utc": md.get("gameCreation"),
                "tournament": (md.get("tournament") or {}).get("name")
                or gmeta.get("tournament"),
                "patch": md.get("patch"),
                "blue_team": canonical_team(blue.get("teamName")),
                "red_team": canonical_team(red.get("teamName")),
                "blue_win": int((blue.get("teamStats") or {}).get("result", 0) or 0),
                "duration_min": round(md.get("gameDuration", 0) / 60, 2)
                if md.get("gameDuration")
                else np.nan,
                "blue_kills": (blue.get("teamStats") or {}).get("kills"),
                "red_kills": (red.get("teamStats") or {}).get("kills"),
                "blue_gold": (blue.get("teamStats") or {}).get("gold"),
                "red_gold": (red.get("teamStats") or {}).get("gold"),
                "blue_dragons": len((blue.get("teamStats") or {}).get("dragons") or []),
                "red_dragons": len((red.get("teamStats") or {}).get("dragons") or []),
                "blue_barons": (blue.get("teamStats") or {}).get("barons"),
                "red_barons": (red.get("teamStats") or {}).get("barons"),
                "blue_towers": (blue.get("teamStats") or {}).get("towers"),
                "red_towers": (red.get("teamStats") or {}).get("towers"),
                "blue_top": (blue.get("players") or {}).get("top", {}).get("champion"),
                "blue_jng": (blue.get("players") or {}).get("jng", {}).get("champion"),
                "blue_mid": (blue.get("players") or {}).get("mid", {}).get("champion"),
                "blue_bot": (blue.get("players") or {}).get("bot", {}).get("champion"),
                "blue_sup": (blue.get("players") or {}).get("sup", {}).get("champion"),
                "red_top": (red.get("players") or {}).get("top", {}).get("champion"),
                "red_jng": (red.get("players") or {}).get("jng", {}).get("champion"),
                "red_mid": (red.get("players") or {}).get("mid", {}).get("champion"),
                "red_bot": (red.get("players") or {}).get("bot", {}).get("champion"),
                "red_sup": (red.get("players") or {}).get("sup", {}).get("champion"),
            }
        )
    df = pd.DataFrame(rows)
    df["date_utc"] = pd.to_datetime(df["date_utc"], utc=True, errors="coerce")
    df = df[df["date_utc"] < TARGET_START].copy()
    df = df[df["match_id"] != TARGET_MATCH_ID].copy()
    return df.drop_duplicates(subset=["oe_game_id"]).sort_values("date_utc").reset_index(drop=True)


def add_rolling_form(fact: pd.DataFrame) -> pd.DataFrame:
    """Add pre-game rolling form. Sort order guarantees no look-ahead."""
    df = fact.sort_values(["team", "date_utc", "oe_game_id"]).copy()
    grp = df.groupby("team", sort=False)

    def roll_mean(col: str, window: int, min_periods: int) -> pd.Series:
        return (
            grp[col]
            .transform(
                lambda s: s.shift(1).rolling(window, min_periods=min_periods).mean()
            )
        )

    df["prior_games"] = grp.cumcount()
    for w in (5, 10, 20):
        df[f"wr_{w}"] = roll_mean("win", w, min_periods=min(3, w))
        df[f"gd10_{w}"] = roll_mean("gd10", w, min_periods=min(3, w))
        df[f"gold_diff_{w}"] = roll_mean("gold_diff", w, min_periods=min(3, w))
        df[f"kd_diff_{w}"] = roll_mean("kill_diff", w, min_periods=min(3, w))
        df[f"tower_diff_{w}"] = roll_mean("tower_diff", w, min_periods=min(3, w))
        df[f"dragon_diff_{w}"] = roll_mean("dragon_diff", w, min_periods=min(3, w))
        df[f"baron_diff_{w}"] = roll_mean("baron_diff", w, min_periods=min(3, w))
        df[f"fb_rate_{w}"] = roll_mean("first_blood", w, min_periods=min(3, w))
        df[f"duration_{w}"] = roll_mean("duration_min", w, min_periods=min(3, w))
        df[f"obj_{w}"] = roll_mean("objective_score", w, min_periods=min(3, w))

    df["rest_days"] = (
        df.groupby("team")["date_utc"].diff().dt.total_seconds() / 86400
    )

    # Opponent's pre-game 10-game win rate, matched on the same game.
    opp = df[["oe_game_id", "team", "wr_10"]].rename(
        columns={"team": "opponent", "wr_10": "opp_wr_10"}
    )
    df = df.merge(opp, on=["oe_game_id", "opponent"], how="left")

    # Strength of schedule: average pre-game win rate of the previous 10
    # opponents. It is shifted so the current game's opponent is excluded,
    # matching every other pre-game rolling feature on this row.
    df = df.sort_values(["team", "date_utc", "oe_game_id"]).reset_index(drop=True)
    df["sos_10"] = df.groupby("team", sort=False)["opp_wr_10"].transform(
        lambda s: s.shift(1).rolling(10, min_periods=3).mean()
    )
    return df


def build_model_dataset(form: pd.DataFrame) -> pd.DataFrame:
    """One row per game between two Worlds teams, using only pre-game form."""
    df = form[
        form["team"].isin(WORLDS_TEAMS) & form["opponent"].isin(WORLDS_TEAMS)
    ].copy()
    # Blue-side row supplies team_a features; red-side row supplies team_b.
    blue = df[df["side"] == "blue"].set_index("oe_game_id")
    red = df[df["side"] == "red"].set_index("oe_game_id")
    common = blue.index.intersection(red.index)
    blue = blue.loc[common]
    red = red.loc[common]

    out = pd.DataFrame(
        {
            "oe_game_id": common,
            "match_id": blue["match_id"].values,
            "date_utc": blue["date_utc"].values,
            "tournament": blue["tournament"].values,
            "team_a": blue["team"].values,
            "team_b": red["team"].values,
            "team_a_win": blue["win"].values.astype(int),
        }
    )
    features = [
        "wr_5",
        "wr_10",
        "gd10_10",
        "gold_diff_10",
        "kd_diff_10",
        "tower_diff_10",
        "dragon_diff_10",
        "baron_diff_10",
        "fb_rate_10",
        "duration_10",
        "obj_10",
        "sos_10",
    ]
    for f in features:
        out[f"{f}_diff"] = blue[f].values - red[f].values
        out[f"{f}_a"] = blue[f].values
        out[f"{f}_b"] = red[f].values
    out["prior_games_min"] = np.minimum(
        blue["prior_games"].values, red["prior_games"].values
    )
    out["blue_side"] = 1  # team_a is always the blue side in this extract
    return out.sort_values("date_utc").reset_index(drop=True)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    game_lists = load_game_lists()
    details = load_details()
    print(f"Loaded {len(game_lists)} game-list rows and {len(details)} game details")

    fact = build_fact(details, game_lists)
    dim = build_dim_games(details, game_lists)
    form = add_rolling_form(fact)

    # Sanity: one winner per game and mirrored rows.
    checks = {}
    winners = dim.groupby("oe_game_id")["blue_win"].agg(["count", "sum"])
    checks["games_with_invalid_winner_count"] = int((winners["count"] != 1).sum())
    checks["fact_rows"] = int(len(fact))
    checks["dim_rows"] = int(len(dim))
    checks["fact_duplicate_team_game"] = int(
        fact.duplicated(subset=["oe_game_id", "team"]).sum()
    )
    checks["fact_games_without_pair"] = int(
        (fact.groupby("oe_game_id")["team"].nunique() != 2).sum()
    )
    checks["missing_duration"] = int(fact["duration_min"].isna().sum())
    checks["missing_gold"] = int(fact["gold"].isna().sum())
    checks["missing_gd10"] = int(fact["gd10"].isna().sum())
    checks["gd10_with_fewer_than_5_players"] = int((fact["gd10_players"] < 5).sum())
    checks["target_match_present"] = int(
        (fact["match_id"] == TARGET_MATCH_ID).sum() + (dim["match_id"] == TARGET_MATCH_ID).sum()
    )
    checks["max_date_utc"] = str(fact["date_utc"].max())
    checks["min_date_utc"] = str(fact["date_utc"].min())
    checks["target_start_utc"] = str(TARGET_START)
    checks["first_blood_consistency"] = int(
        fact.groupby("oe_game_id")["first_blood"].sum().value_counts().to_dict().get(2, 0)
    )

    model = build_model_dataset(form)

    fact.to_csv(PROCESSED_DIR / "fact_team_games.csv", index=False, encoding="utf-8-sig")
    dim.to_csv(PROCESSED_DIR / "dim_games.csv", index=False, encoding="utf-8-sig")
    form.to_csv(PROCESSED_DIR / "team_form.csv", index=False, encoding="utf-8-sig")
    model.to_csv(PROCESSED_DIR / "model_dataset.csv", index=False, encoding="utf-8-sig")

    report = {
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "source": "Oracle's Elixir public API (see data/raw/collection_manifest.json)",
        "collection_cutoff_utc": COLLECTION_CUTOFF_UTC,
        "checks": checks,
        "missingness_fact": {
            c: round(float(form[c].isna().mean()), 4)
            for c in [                "duration_min",
                "gold",
                "gold_diff",
                "gd10",
                "kills",
                "deaths",
                "towers",
                "dragons",
                "barons",
                "first_blood",
                "opp_wr_10",
            ]
        },
        "model_sample": {
            "games": int(len(model)),
            "teams": sorted(set(model["team_a"]) | set(model["team_b"])),
            "date_min": str(model["date_utc"].min()),
            "date_max": str(model["date_utc"].max()),
            "games_with_min_5_prior": int((model["prior_games_min"] >= 5).sum()),
            "games_with_min_8_prior": int((model["prior_games_min"] >= 8).sum()),
            "games_with_min_10_prior": int((model["prior_games_min"] >= 10).sum()),
        },
        "head_to_head_games": int(
            ((model["team_a"] == TEAM_A) & (model["team_b"] == TEAM_B)).sum()
            + ((model["team_a"] == TEAM_B) & (model["team_b"] == TEAM_A)).sum()
        ),
    }
    (PROCESSED_DIR / "data_quality_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
