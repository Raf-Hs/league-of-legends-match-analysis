"""Score a pre-registered prediction after the match is final.

The script updates the manually maintained validation log in
``powerbi/post_match_validation_log.csv``. It never changes the original
prediction; it only fills in the result fields and computes the scoring rules
documented in ``reports/post_match_validation_plan.md``.

Usage:
    python src/score_match.py --winner iG
    python src/score_match.py --match-id 115660540726095065 --winner LYON --side blue
    python src/score_match.py --winner iG --dry-run
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import PROJECT_ROOT, TARGET_MATCH_ID

LOG_PATH = PROJECT_ROOT / "powerbi" / "post_match_validation_log.csv"

MUTABLE_COLUMNS = [
    "actual_winner",
    "actual_team_a_win",
    "team_a_side",
    "patch",
    "duration_min",
    "brier_score",
    "log_loss",
    "correct_pick",
    "result_source",
    "scored_at_utc",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--winner",
        required=True,
        help="Actual winner: team code (HLE, IG, iG, LYON, T1...) or full name",
    )
    parser.add_argument(
        "--match-id",
        default=str(TARGET_MATCH_ID),
        help="Match id to score (default: the configured target fixture)",
    )
    parser.add_argument(
        "--side",
        choices=["blue", "red"],
        help="Side played by team_a, if confirmed",
    )
    parser.add_argument("--patch", help="Patch actually played, e.g. 16.20")
    parser.add_argument("--duration", type=float, help="Game duration in minutes")
    parser.add_argument("--source", help="Where the result was confirmed")
    parser.add_argument("--notes", help="Free-text note appended to the log row")
    parser.add_argument(
        "--path",
        type=Path,
        default=LOG_PATH,
        help="Validation log path (default: powerbi/post_match_validation_log.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the score without writing the log",
    )
    return parser.parse_args()


def identify_winner(winner: str, row: pd.Series) -> str:
    """Map the user-supplied winner to 'a' or 'b' for the logged fixture."""
    wanted = winner.strip().casefold()
    candidates = {
        "a": [
            str(row["team_a"]),
            str(row.get("team_a_code", "")),
        ],
        "b": [
            str(row["team_b"]),
            str(row.get("team_b_code", "")),
        ],
    }
    for side, names in candidates.items():
        for name in names:
            if name and name.strip().casefold() == wanted:
                return side
    raise SystemExit(
        f"'{winner}' does not match the logged fixture "
        f"({row['team_a']} vs {row['team_b']})"
    )


def main() -> None:
    args = parse_args()
    path = args.path if args.path.is_absolute() else PROJECT_ROOT / args.path
    if not path.exists():
        raise SystemExit(f"Validation log not found: {path}")

    log = pd.read_csv(path, dtype={"match_id": str, "team_a_code": str, "team_b_code": str})
    # Result columns are blank in a pending row, so pandas infers float64.
    # Cast them to object before filling mixed text/number values.
    for column in MUTABLE_COLUMNS:
        if column in log.columns:
            log[column] = log[column].astype("object")

    mask = log["match_id"].astype(str) == str(args.match_id)
    if not mask.any():
        raise SystemExit(f"Match {args.match_id} is not in {path}")

    idx = log.index[mask][0]
    row = log.loc[idx]
    p_a = float(row["predicted_p_team_a"])
    p_b = float(row["predicted_p_team_b"])
    if not (0.0 <= p_a <= 1.0 and 0.0 <= p_b <= 1.0):
        raise SystemExit("Predicted probabilities are outside [0, 1]")
    if abs(p_a + p_b - 1.0) > 1e-6:
        raise SystemExit("Predicted probabilities do not sum to 1")

    side = identify_winner(args.winner, row)
    actual_a_win = 1 if side == "a" else 0
    brier = (p_a - actual_a_win) ** 2
    p_actual = p_a if actual_a_win == 1 else p_b
    log_loss = -math.log(max(min(p_actual, 1 - 1e-15), 1e-15))
    pick = row["team_a_code"] if p_a >= 0.5 else row["team_b_code"]
    correct = "Yes" if pick.strip().casefold() == args.winner.strip().casefold() else "No"
    scored_at = datetime.now(timezone.utc).isoformat()

    print(f"Fixture    : {row['team_a']} vs {row['team_b']} ({row.get('series_type','')})")
    print(f"Prediction : {row['team_a_code']} {p_a:.2%} / {row['team_b_code']} {p_b:.2%} (per game)")
    if row.get("predicted_p_team_a_series") is not None:
        print(f"Series     : {float(row['predicted_p_team_a_series']):.2%} / {1-float(row['predicted_p_team_a_series']):.2%}")
    print(f"Result     : {args.winner} win")
    print(f"Brier      : {brier:.4f}  (coin flip 0.2500; lower is better)")
    print(f"Log loss   : {log_loss:.4f}  (coin flip 0.6931; lower is better)")
    print(f"Pick       : {pick} - {correct}")

    if args.dry_run:
        print("Dry run: log not written.")
        return

    log.loc[idx, "actual_winner"] = args.winner
    log.loc[idx, "actual_team_a_win"] = actual_a_win
    log.loc[idx, "brier_score"] = round(brier, 6)
    log.loc[idx, "log_loss"] = round(log_loss, 6)
    log.loc[idx, "correct_pick"] = correct
    log.loc[idx, "scored_at_utc"] = scored_at
    if args.side:
        log.loc[idx, "team_a_side"] = args.side
    if args.patch:
        log.loc[idx, "patch"] = args.patch
    if args.duration is not None:
        log.loc[idx, "duration_min"] = args.duration
    if args.source:
        log.loc[idx, "result_source"] = args.source
    if args.notes:
        previous = log.loc[idx, "notes"]
        note = (
            args.notes
            if pd.isna(previous) or not str(previous).strip()
            else f"{previous} | {args.notes}"
        )
        log.loc[idx, "notes"] = note

    log.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"Updated {path}")


if __name__ == "__main__":
    main()
