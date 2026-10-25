"""Validate the outputs of the pipeline.

Usage:
    python src/validate_outputs.py

The checks are intentionally mechanical: row counts, key uniqueness, leakage,
probability sanity and presence of every promised artifact. They are not a
substitute for reading the reports.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

from config import (
    FIGURES_DIR,
    POWERBI_DIR,
    PROCESSED_DIR,
    PROJECT_ROOT,
    TARGET_MATCH_ID,
    TEAM_A,
    TEAM_B,
)

REQUIRED_PROCESSED = [
    "fact_team_games.csv",
    "dim_games.csv",
    "team_form.csv",
    "model_dataset.csv",
    "data_quality_report.json",
    "team_kpis.csv",
    "match_kpis.csv",
    "target_match_features.csv",
    "target_model_input.csv",
    "team_event_stats.csv",
    "kpi_definitions.csv",
    "model_comparison.csv",
    "model_coefficients.csv",
    "model_calibration.csv",
    "model_predictions_test.csv",
    "prediction_summary.json",
    "scenario_analysis.csv",
    "target_feature_contributions.csv",
]

REQUIRED_FIGURES = [
    "01_form_summary.png",
    "02_gd10_rolling.png",
    "03_objectives.png",
    "04_match_history.png",
    "05_model_comparison.png",
    "06_coefficients.png",
    "07_calibration.png",
    "08_prediction.png",
    "09_feature_contributions.png",
    "10_form_ranking.png",
]

REQUIRED_POWERBI = [
    "DimDate.csv",
    "DimTeam.csv",
    "DimGame.csv",
    "FactTeamGame.csv",
    "FactTeamForm.csv",
    "FactTeamEventStat.csv",
    "FactTeamKPI.csv",
    "FactMatchKPI.csv",
    "FactTargetFeature.csv",
    "FactModelMetric.csv",
    "FactModelCoefficient.csv",
    "FactModelCalibration.csv",
    "FactFeatureContribution.csv",
    "FactScenario.csv",
    "FactPrediction.csv",
    "DimMetric.csv",
]

# Any assignment of a literal to a key/token/secret name is a leak risk.
# Secrets must come from the environment (see src/config.py).
SECRET_PATTERN = re.compile(
    r"""(?ix)
    (api[_-]?key|access[_-]?token|secret|password)
    \s*[:=]\s*
    ["'][^"'\s]{8,}["']
    """
)


def scan_for_secrets() -> list[str]:
    """Return human-readable findings for hardcoded secrets in the source tree."""
    findings: list[str] = []
    for path in sorted(PROJECT_ROOT.rglob("*.py")):
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if SECRET_PATTERN.search(line):
                findings.append(f"{path.relative_to(PROJECT_ROOT)}:{number}")
    return findings


def main() -> None:
    failures: list[str] = []
    checks: list[tuple[str, bool, str]] = []

    for name in REQUIRED_PROCESSED:
        path = PROCESSED_DIR / name
        checks.append((f"exists: {name}", path.exists(), str(path)))
        if not path.exists():
            failures.append(f"missing processed file: {name}")

    for name in REQUIRED_FIGURES:
        path = FIGURES_DIR / name
        checks.append((f"exists: {name}", path.exists(), str(path)))
        if not path.exists():
            failures.append(f"missing figure: {name}")

    for name in REQUIRED_POWERBI:
        path = POWERBI_DIR / name
        checks.append((f"exists: {name}", path.exists(), str(path)))
        if not path.exists():
            failures.append(f"missing Power BI file: {name}")

    fact = pd.read_csv(PROCESSED_DIR / "fact_team_games.csv")
    dim = pd.read_csv(PROCESSED_DIR / "dim_games.csv")
    model = pd.read_csv(PROCESSED_DIR / "model_dataset.csv")
    pred = json.loads((PROCESSED_DIR / "prediction_summary.json").read_text(encoding="utf-8"))
    target = pd.read_csv(PROCESSED_DIR / "target_model_input.csv").iloc[0]

    checks.append(("fact has two rows per game", len(fact) == 2 * len(dim), f"{len(fact)} vs {2*len(dim)}"))
    checks.append(("no duplicate team-game", not fact.duplicated(["oe_game_id", "team"]).any(), ""))
    checks.append(("no unpaired games", (fact.groupby("oe_game_id")["team"].nunique() == 2).all(), ""))
    checks.append(("target match absent from fact", (fact["match_id"].astype(str) != str(TARGET_MATCH_ID)).all(), ""))
    checks.append(("target match absent from model", (model["match_id"].astype(str) != str(TARGET_MATCH_ID)).all(), ""))
    checks.append(("model target match absent", not ((model["team_a"] == TEAM_A) & (model["team_b"] == TEAM_B)).any(), ""))
    checks.append(("target features not NaN", not pd.isna(target["wr_10_diff"]), ""))
    p_hle = float(pred["primary_model"]["p_hle_win"])
    p_ig = float(pred["primary_model"]["p_ig_win"])
    checks.append(("probabilities sum to 1", abs(p_hle + p_ig - 1) < 1e-9, f"{p_hle:.6f} + {p_ig:.6f}"))
    checks.append(("probability in [0,1]", 0 <= p_hle <= 1 and 0 <= p_ig <= 1, ""))
    checks.append(("bootstrap interval ordered", pred["primary_model"]["bootstrap_p05"] <= pred["primary_model"]["bootstrap_p95"], ""))
    checks.append(("model sample >= 100", pred["sample"]["modelling_games"] >= 100, str(pred["sample"]["modelling_games"])))

    secrets = scan_for_secrets()
    checks.append(
        (
            "no hardcoded secrets in source",
            not secrets,
            ", ".join(secrets) if secrets else "none found",
        )
    )

    print("\nVALIDATION")
    print("-" * 78)
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{status:4s}  {name:42s} {detail}")
        if not ok:
            failures.append(name)

    report = {
        "checks_total": int(len(checks)),
        "checks_passed": int(sum(ok for _, ok, _ in checks)),
        "failures": failures,
    }
    (PROCESSED_DIR / "validation_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print("-" * 78)
    print(json.dumps(report, indent=2))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
