"""Project configuration.

Oracle's Elixir (OE) requires an API key on every request. The key is NEVER
stored in this repository. Provide it through the environment instead:

    Windows (PowerShell):
        $env:OE_API_KEY = "<your key>"
    Windows (cmd):
        set OE_API_KEY=<your key>
    macOS / Linux:
        export OE_API_KEY="<your key>"

The pipeline reproduces fully from the cached raw data in ``data/raw`` without
any key. Only ``python src/run_pipeline.py --refresh`` needs the key, because
that path calls the live OE API.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
POWERBI_DIR = PROJECT_ROOT / "data" / "powerbi"
REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = PROJECT_ROOT / "figures"

OE_API_BASE = "https://api.oracleselixir.com"

# Read from the environment only. There is intentionally no hard-coded
# fallback: a key committed to git is a leaked key.
OE_API_KEY = (os.getenv("OE_API_KEY") or "").strip()
OE_WEB_ORIGIN = "https://oracleselixir.com"

# Data collection cutoff. Every game used as a feature must have started
# before this timestamp. The forecast is registered before the target match.
COLLECTION_CUTOFF_UTC = "2026-10-27T00:00:00Z"

# Current target fixture: Worlds 2026, Swiss Day 5 (best of 3).
TARGET_MATCH_START_UTC = "2026-10-28T23:00:00Z"
TARGET_MATCH_ID = "115660540726095065"

TEAM_A = "LYON (2024 American Team)"
TEAM_A_CODE = "LYON"
TEAM_B = "Invictus Gaming"
TEAM_B_CODE = "IG"

# Every fixture on the next match day, so the report can publish a full slate
# instead of a single match. `match_id` comes from the Oracle's Elixir
# /matches/upcoming feed.
UPCOMING_FIXTURES = [
    {
        "match_id": "115660540726095061",
        "team_a": "Movistar KOI",
        "team_b": "T1",
        "start_utc": "2026-10-28T20:00:00Z",
        "series_type": "bestOf3",
        "block": "Swiss, Day 5",
    },
    {
        "match_id": "115660540726095065",
        "team_a": "LYON (2024 American Team)",
        "team_b": "Invictus Gaming",
        "start_utc": "2026-10-28T23:00:00Z",
        "series_type": "bestOf3",
        "block": "Swiss, Day 5",
    },
]

# Oracle's Elixir uses different display names in different endpoints. The
# game-detail feed calls this team "LYON"; the team-stats endpoint uses the
# longer 2024 roster label. Normalise to the team-stats label so the same team
# is not split into two entities.
TEAM_NAME_MAP = {"LYON": "LYON (2024 American Team)"}


def canonical_team(name: str | None) -> str | None:
    """Return the canonical team name used across processed tables."""
    if name is None:
        return None
    return TEAM_NAME_MAP.get(name, name)

# The 16 teams in the Worlds 2026 Swiss stage. Used to define the modelling
# sample (games between Worlds participants) and opponent-strength features.
WORLDS_TEAMS = [
    "Hanwha Life Esports",
    "Gen.G",
    "T1",
    "Dplus Kia",
    "Anyone's Legend",
    "Bilibili Gaming",
    "Top Esports",
    "Invictus Gaming",
    "Team Liquid",
    "LYON (2024 American Team)",
    "G2 Esports",
    "Movistar KOI",
    "Team Secret Whales",
    "CTBC Flying Oyster",
    "Karmine Corp",
    "LØS",
]

TEAM_REGION = {
    "Hanwha Life Esports": "LCK",
    "Gen.G": "LCK",
    "T1": "LCK",
    "Dplus Kia": "LCK",
    "Anyone's Legend": "LPL",
    "Bilibili Gaming": "LPL",
    "Top Esports": "LPL",
    "Invictus Gaming": "LPL",
    "Team Liquid": "LCS",
    "LYON (2024 American Team)": "LCS",
    "G2 Esports": "LEC",
    "Movistar KOI": "LEC",
    "Team Secret Whales": "LCP",
    "CTBC Flying Oyster": "LCP",
    "Karmine Corp": "LEC",
    "LØS": "CBLOL",
}
