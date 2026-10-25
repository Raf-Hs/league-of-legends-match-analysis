"""Score the pre-match prediction after the match is final.

The script updates the manually maintained validation log in
``powerbi/post_match_validation_log.csv``. It never changes the original
prediction; it only fills in the result fields and computes the scoring rules
documented in ``reports/post_match_validation_plan.md``.

Usage:
    python src/score_match.py --winner IG
    python src/score_match.py --winner HLE --side blue --patch 16.20 --source "OE match page"
    python src/score_match.py --winner IG --dry-run
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import PROJECT_ROOT, TARGET_MATCH_ID

LOG_PATH = PROJECT_ROOT / "powerbi" / "post_match_validation_log.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--winner", required=True, choices=["HLE", "IG"], help="Actual winner")
    parser.add_argument(
        "--side",
        choices=["blue", "red"],
        help="HLE's side in the game, if confirmed",
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


def main() -> None:
    args = parse_args()
    path = args.path if args.path.is_absolute() else PROJECT_ROOT / args.path
    if not path.exists():
        raise SystemExit(f"Validation log not found: {path}")

    log = pd.read_csv(path, dtype={"match_id": str})
    # Result columns are blank in the pending row, so pandas infers float64.
    # Cast them to object before filling mixed text/number values.
    mutable_columns = [
        "actual_winner",
        "actual_hle_win",
        "hle_side",
        "patch",
        "duration_min",
        "brier_score",
        "log_loss",
        "correct_pick",
        "result_source",
        "scored_at_utc",
        "notes",
    ]
    for column in mutable_columns:
        if column in log.columns:
            log[column] = log[column].astype("object")

    mask = log["match_id"].astype(str) == str(TARGET_MATCH_ID)
    if not mask.any():
        raise SystemExit(f"Target match {TARGET_MATCH_ID} is not in {path}")

    idx = log.index[mask][0]
    row = log.loc[idx]
    p_hle = float(row["predicted_p_hle"])
    p_ig = float(row["predicted_p_ig"])
    if not (0.0 <= p_hle <= 1.0 and 0.0 <= p_ig <= 1.0):
        raise SystemExit("Predicted probabilities are outside [0, 1]")
    if abs(p_hle + p_ig - 1.0) > 1e-6:
        raise SystemExit("Predicted probabilities do not sum to 1")

    actual_hle_win = 1 if args.winner == "HLE" else 0
    brier = (p_hle - actual_hle_win) ** 2
    p_actual = p_hle if actual_hle_win == 1 else p_ig
    log_loss = -math.log(max(min(p_actual, 1 - 1e-15), 1e-15))
    pick = "HLE" if p_hle >= 0.5 else "IG"
    correct = "Yes" if pick == args.winner else "No"
    scored_at = datetime.now(timezone.utc).isoformat()

    print(f"Prediction : HLE {p_hle:.2%} / IG {p_ig:.2%}")
    print(f"Result     : {args.winner} win")
    print(f"Brier      : {brier:.4f}  (coin flip 0.2500; lower is better)")
    print(f"Log loss   : {log_loss:.4f}  (coin flip 0.6931; lower is better)")
    print(f"Pick       : {pick} - {correct}")

    if args.dry_run:
        print("Dry run: log not written.")
        return

    log.loc[idx, "actual_winner"] = args.winner
    log.loc[idx, "actual_hle_win"] = actual_hle_win
    log.loc[idx, "brier_score"] = round(brier, 6)
    log.loc[idx, "log_loss"] = round(log_loss, 6)
    log.loc[idx, "correct_pick"] = correct
    log.loc[idx, "scored_at_utc"] = scored_at
    if args.side:
        log.loc[idx, "hle_side"] = args.side
    if args.patch:
        log.loc[idx, "patch"] = args.patch
    if args.duration is not None:
        log.loc[idx, "duration_min"] = args.duration
    if args.source:
        log.loc[idx, "result_source"] = args.source
    if args.notes:
        previous = log.loc[idx, "notes"]
        note = args.notes if pd.isna(previous) or not str(previous).strip() else f"{previous} | {args.notes}"
        log.loc[idx, "notes"] = note

    log.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"Updated {path}")


if __name__ == "__main__":
    main()
