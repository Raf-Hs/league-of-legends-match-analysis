"""Generate portfolio-quality charts from the processed tables.

Usage:
    python src/visualizations.py

All figures are written to figures/ as 200-dpi PNGs. The charts are descriptive
and intentionally show uncertainty; none of them imply a causal claim.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from config import FIGURES_DIR, PROCESSED_DIR, TEAM_A, TEAM_A_CODE, TEAM_B, TEAM_B_CODE

AMBER = "#F2A33A"
CRIMSON = "#C8102E"
INK = "#1F2933"
MUTED = "#7B8794"
GRID = "#D9E2EC"
BLUE = "#3E7CB1"
GREEN = "#2A9D8F"
RED = "#C8102E"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "axes.edgecolor": GRID,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.7,
        "grid.alpha": 0.8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "legend.frameon": False,
    }
)


def load() -> dict[str, pd.DataFrame]:
    return {
        "fact": pd.read_csv(PROCESSED_DIR / "fact_team_games.csv", parse_dates=["date_utc"]),
        "form": pd.read_csv(PROCESSED_DIR / "team_form.csv", parse_dates=["date_utc"]),
        "team": pd.read_csv(PROCESSED_DIR / "team_kpis.csv"),
        "match": pd.read_csv(PROCESSED_DIR / "match_kpis.csv"),
        "comparison": pd.read_csv(PROCESSED_DIR / "model_comparison.csv"),
        "coef": pd.read_csv(PROCESSED_DIR / "model_coefficients.csv"),
        "calib": pd.read_csv(PROCESSED_DIR / "model_calibration.csv"),
        "contrib": pd.read_csv(PROCESSED_DIR / "target_feature_contributions.csv"),
        "scenario": pd.read_csv(PROCESSED_DIR / "scenario_analysis.csv"),
    }


def save(fig, name: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / name, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


def team_games(fact: pd.DataFrame, team: str) -> pd.DataFrame:
    return fact[fact["team"] == team].sort_values(["date_utc", "oe_game_id"])


def fig_form(data: dict) -> None:
    t = data["team"].set_index("team")
    windows = ["last5", "last10", "last20"]
    labels = ["Last 5", "Last 10", "Last 20"]
    x = np.arange(len(windows))
    w = 0.36
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for ax, metric, title, fmt in [
        (axes[0], "win_rate", "Win rate by window", "{:.0%}"),
        (axes[1], "gold_diff", "Average end-game gold difference", "{:+.0f}"),
    ]:
        h = [t.loc[TEAM_A, f"{win}_{metric}"] for win in windows]
        i = [t.loc[TEAM_B, f"{win}_{metric}"] for win in windows]
        b1 = ax.bar(x - w / 2, h, w, color=AMBER, label=TEAM_A_CODE)
        b2 = ax.bar(x + w / 2, i, w, color=CRIMSON, label=TEAM_B_CODE)
        ax.set_xticks(x, labels)
        ax.set_title(title)
        ax.axhline(0, color=INK, linewidth=0.8)
        if metric == "win_rate":
            ax.set_ylim(0, 0.75)
            ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
        else:
            ax.yaxis.set_major_formatter(lambda v, _: f"{v:+,.0f}")
            ax.legend(loc="upper left", ncol=2)
        for bars in (b1, b2):
            for bar in bars:
                height = bar.get_height()
                ax.annotate(
                    fmt.format(height),
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3 if height >= 0 else -12),
                    textcoords="offset points",
                    ha="center",
                    va="bottom" if height >= 0 else "top",
                    fontsize=8,
                    color=INK,
                )
    fig.suptitle(
        f"Recent form on wins, and the end-game gold edge of {TEAM_B_CODE}",
        fontsize=14,
        fontweight="bold",
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.01,
        "Source: Oracle's Elixir public API. Windows end at the 2026-10-25 collection cutoff. "
        "Gold difference is final gold, not gold at 15.",
        fontsize=8,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    save(fig, "01_form_summary.png")


def fig_gd10(data: dict) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.8))
    for team, color, label in [(TEAM_A, AMBER, TEAM_A_CODE), (TEAM_B, CRIMSON, TEAM_B_CODE)]:
        d = team_games(data["fact"], team).tail(20).reset_index(drop=True)
        ax.plot(
            d.index + 1,
            d["gd10"],
            marker="o",
            markersize=4,
            linewidth=1.2,
            color=color,
            alpha=0.45,
            label=f"{label} per game",
        )
        rolling = d["gd10"].rolling(5, min_periods=1).mean()
        ax.plot(d.index + 1, rolling, linewidth=2.6, color=color, label=f"{label} 5-game mean")
    ax.axhline(0, color=INK, linewidth=0.9)
    ax.set_xticks(range(1, 21))
    ax.set_xlabel("Most recent 20 games (oldest to newest)")
    ax.set_ylabel("Gold difference at 10 min")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:+,.0f}")
    ax.set_title(f"Early-game gold (GD@10): {TEAM_A_CODE} vs {TEAM_B_CODE}, last 20 games")
    ax.legend(loc="upper left", ncol=2)
    fig.text(
        0.01,
        0.01,
        "GD@10 is the sum of five players' gxd10. It is a proxy for GD@15, which the API does not expose. "
        "Missing games are gaps, not zeros.",
        fontsize=8,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "02_gd10_rolling.png")


def fig_objectives(data: dict) -> None:
    t = data["team"].set_index("team")
    metrics = [
        ("last10_objective_score", "Objective composite\n(towers + dragons + 2x barons)", "{:+.1f}"),
        ("last10_first_blood_rate", "First-blood rate", "{:.0%}"),
        ("last10_towers", "Towers per game", "{:.1f}"),
        ("last10_dragons", "Dragons per game", "{:.1f}"),
        ("last10_barons", "Barons per game", "{:.1f}"),
    ]
    fig, axes = plt.subplots(1, len(metrics), figsize=(15, 4.1))
    for ax, (metric, title, fmt) in zip(axes, metrics):
        vals = [t.loc[TEAM_A, metric], t.loc[TEAM_B, metric]]
        bars = ax.bar([TEAM_A_CODE, TEAM_B_CODE], vals, color=[AMBER, CRIMSON], width=0.62)
        ax.set_title(title, fontsize=10)
        ax.axhline(0, color=INK, linewidth=0.8)
        for bar, v in zip(bars, vals):
            ax.annotate(
                fmt.format(v),
                xy=(bar.get_x() + bar.get_width() / 2, v),
                xytext=(0, 3 if v >= 0 else -12),
                textcoords="offset points",
                ha="center",
                va="bottom" if v >= 0 else "top",
                fontsize=9,
                fontweight="bold",
            )
        ax.tick_params(axis="x", labelsize=9)
    fig.suptitle(
        f"Objective control: composite, dragons, barons and first blood for {TEAM_A_CODE} vs {TEAM_B_CODE}",
        fontsize=14,
        fontweight="bold",
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.01,
        "Last 10 games before the cutoff. Objective composite = tower diff + dragon diff + 2 x baron diff.",
        fontsize=8,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    save(fig, "03_objectives.png")


def fig_history(data: dict) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 6.4), sharex=False)
    for ax, team, color in [
        (axes[0], TEAM_A, AMBER),
        (axes[1], TEAM_B, CRIMSON),
    ]:
        d = team_games(data["fact"], team).tail(20).reset_index(drop=True)
        colors = [GREEN if w == 1 else RED for w in d["win"]]
        ax.bar(d.index + 1, [1] * len(d), color=colors, width=0.72, alpha=0.9)
        ax.set_yticks([])
        ax.set_ylim(0, 1.9)
        cum = d["win"].expanding().mean()
        ax2 = ax.twinx()
        ax2.plot(d.index + 1, cum, color=color, marker="o", markersize=3.5, linewidth=2)
        ax2.set_ylim(0, 1)
        ax2.set_ylabel("Cumulative win rate", color=color)
        ax2.tick_params(axis="y", colors=color)
        ax2.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
        ax2.grid(False)
        ax.set_title(f"{team} - last 20 games (oldest to newest)", loc="left")
        for i, (_, row) in enumerate(d.iterrows(), start=1):
            ax.annotate(
                "W" if row["win"] == 1 else "L",
                xy=(i, 1.02),
                ha="center",
                va="bottom",
                fontsize=8,
                color=INK,
            )
            ax.annotate(
                str(row["opponent_code"]),
                xy=(i, -0.08),
                xycoords=("data", "axes fraction"),
                ha="center",
                va="top",
                fontsize=6.5,
                color=MUTED,
                rotation=90,
            )
    handles = [Patch(color=GREEN, label="Win"), Patch(color=RED, label="Loss")]
    axes[0].legend(handles=handles, loc="upper left", ncol=2)
    fig.suptitle(
        "Match history: both teams are 5-5 in their last 10, with different loss profiles",
        fontsize=14,
        fontweight="bold",
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.01,
        "Bars are individual games; the line is the cumulative win rate within the 20-game window. "
        "Opponent codes are shown under each game.",
        fontsize=8,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    save(fig, "04_match_history.png")


def fig_model_comparison(data: dict) -> None:
    c = data["comparison"].copy()
    names = ["M0_coinflip", "M1_win_rate", "M2_core4", "M3_core5", "M4_sensitivity_8"]
    labels = ["Coin flip", "Win rate", "Core 4", "Core 5\n(primary)", "8-feature"]
    c = c.set_index("model").loc[names]
    x = np.arange(len(c))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, metric, title, baseline in [
        (axes[0], "auc", "Holdout AUC (higher is better)", 0.5),
        (axes[1], "brier", "Holdout Brier score (lower is better)", 0.25),
    ]:
        bars = ax.bar(x, c[metric], color=[MUTED] + [BLUE] * 4, width=0.62)
        bars[3].set_color(AMBER)
        ax.axhline(baseline, color=RED, linestyle="--", linewidth=1.4, label="Coin-flip baseline")
        ax.set_xticks(x, labels)
        ax.set_title(title)
        ax.legend(loc="best")
        lo = min(c[metric].min(), baseline) * 0.92
        hi = max(c[metric].max(), baseline) * 1.06
        ax.set_ylim(lo, hi)
        for bar, v in zip(bars, c[metric]):
            ax.annotate(
                f"{v:.3f}",
                xy=(bar.get_x() + bar.get_width() / 2, v),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                fontsize=8.5,
            )
    fig.suptitle(
        "The holdout does not support a strong predictive claim: AUC is near 0.50 and Brier is at the coin-flip level",
        fontsize=13,
        fontweight="bold",
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.01,
        "Train: games before 2026-09-01. Test: 72 games from 2026-09-02 to 2026-10-25. "
        "The primary model is side-neutral (no intercept).",
        fontsize=8,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    save(fig, "05_model_comparison.png")


def fig_coefficients(data: dict) -> None:
    c = data["coef"].query("model == 'M3_core5'").copy()
    c = c.sort_values("standardized_coefficient")
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    y = np.arange(len(c))
    ax.errorbar(
        c["standardized_coefficient"],
        y,
        xerr=[
            c["standardized_coefficient"] - c["coef_p05"],
            c["coef_p95"] - c["standardized_coefficient"],
        ],
        fmt="o",
        color=INK,
        ecolor=MUTED,
        elinewidth=2,
        capsize=5,
        markersize=7,
    )
    ax.axvline(0, color=RED, linestyle="--", linewidth=1.2)
    ax.set_yticks(y, c["label"])
    ax.set_xlabel("Standardized coefficient (change in log-odds per 1 SD)")
    ax.set_title("Primary-model coefficients: all 90% bootstrap intervals include zero")
    for yi, (_, row) in zip(y, c.iterrows()):
        ax.annotate(
            f"{row['standardized_coefficient']:+.2f}",
            xy=(row["standardized_coefficient"], yi),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=INK,
        )
    fig.text(
        0.01,
        0.01,
        "Bootstrap: 1,000 resamples of the full 174-game modelling sample. "
        "Features are collinear, so individual signs should not be read causally.",
        fontsize=8,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "06_coefficients.png")


def fig_calibration(data: dict) -> None:
    c = data["calib"].copy()
    fig, ax = plt.subplots(figsize=(7.4, 6.2))
    ax.plot([0, 1], [0, 1], color=MUTED, linestyle="--", linewidth=1.2, label="Perfect calibration")
    styles = {
        "oof_primary_core5": (BLUE, "o", "Out-of-fold (time-series CV)"),
        "holdout_primary_core5": (AMBER, "s", "Holdout (85 games)"),
    }
    for sample, (color, marker, label) in styles.items():
        d = c[(c["sample"] == sample) & (c["n"] > 0)].sort_values("mean_pred")
        if d.empty:
            continue
        ax.plot(d["mean_pred"], d["observed"], marker=marker, color=color, linewidth=2, label=label)
        for _, row in d.iterrows():
            ax.annotate(
                f"n={int(row['n'])}",
                xy=(row["mean_pred"], row["observed"]),
                xytext=(4, -10),
                textcoords="offset points",
                fontsize=7,
                color=MUTED,
            )
    ax.set_xlim(0.25, 0.8)
    ax.set_ylim(0.2, 0.85)
    ax.set_xlabel("Mean predicted probability (team_a win)")
    ax.set_ylabel("Observed win rate")
    ax.set_title("Calibration is noisy and the holdout is overconfident at the high end")
    ax.legend(loc="upper left")
    fig.text(
        0.01,
        0.01,
        "Bins are fixed probability bands. Small bins mean the curve is indicative, not a precise calibration estimate.",
        fontsize=8,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "07_calibration.png")


def fig_prediction(data: dict) -> None:
    s = json.loads((PROCESSED_DIR / "prediction_summary.json").read_text(encoding="utf-8"))
    p = s["primary_model"]["p_team_a_win"]
    lo, hi = s["primary_model"]["bootstrap_p05"], s["primary_model"]["bootstrap_p95"]
    fig, ax = plt.subplots(figsize=(9.6, 3.2))
    ax.barh([0], [p], color=AMBER, height=0.5, label=f"{TEAM_A_CODE} {p:.1%}")
    ax.barh([0], [1 - p], left=[p], color=CRIMSON, height=0.5, label=f"{TEAM_B_CODE} {1-p:.1%}")
    ax.errorbar(
        [p],
        [0],
        xerr=[[p - lo], [hi - p]],
        fmt="none",
        ecolor=INK,
        elinewidth=2,
        capsize=6,
    )
    ax.axvline(0.5, color=INK, linestyle="--", linewidth=1)
    ax.set_xlim(0, 1)
    ax.set_yticks([])
    ax.set_xlabel("Probability of winning the Bo1")
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_title(
        f"Pre-match call: {TEAM_A_CODE} {p:.0%} / {TEAM_B_CODE} {1-p:.0%}; 90% bootstrap interval {lo:.0%}-{hi:.0%}"
    )
    ax.legend(loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.62))
    ax.text(
        p / 2,
        0,
        f"{p:.1%}",
        ha="center",
        va="center",
        color="white",
        fontweight="bold",
        fontsize=13,
    )
    ax.text(
        p + (1 - p) / 2,
        0,
        f"{1-p:.1%}",
        ha="center",
        va="center",
        color="white",
        fontweight="bold",
        fontsize=13,
    )
    fig.text(
        0.01,
        0.01,
        "Side-neutral primary model (no intercept) fit on 174 games. The interval is a 1,000-draw bootstrap. "
        "Holdout AUC is 0.49, so the call is not statistically distinguishable from a coin flip.",
        fontsize=8,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    save(fig, "08_prediction.png")


def fig_contributions(data: dict) -> None:
    c = data["contrib"].copy().sort_values("log_odds_contribution")
    fig, ax = plt.subplots(figsize=(9.6, 4.6))
    colors = [RED if v < 0 else GREEN for v in c["log_odds_contribution"]]
    bars = ax.barh(c["label"], c["log_odds_contribution"], color=colors, height=0.6)
    ax.axvline(0, color=INK, linewidth=0.9)
    ax.set_xlabel(f"Contribution to the log-odds of {TEAM_A_CODE} winning")
    ax.set_title(f"What moves the primary model for {TEAM_A_CODE} vs {TEAM_B_CODE}")
    for bar, v in zip(bars, c["log_odds_contribution"]):
        ax.annotate(
            f"{v:+.3f}",
            xy=(v, bar.get_y() + bar.get_height() / 2),
            xytext=(6 if v >= 0 else -6, 0),
            textcoords="offset points",
            ha="left" if v >= 0 else "right",
            va="center",
            fontsize=9,
        )
    fig.text(
        0.01,
        0.01,
        f"Contribution = standardized target difference x standardized coefficient. Red pushes {TEAM_A_CODE} down; green pushes {TEAM_A_CODE} up. "
        "The intercept is zero by design.",
        fontsize=8,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, "09_feature_contributions.png")


def fig_ranking(data: dict) -> None:
    t = data["team"].sort_values("form_index_last10", ascending=True).copy()
    colors = [AMBER if x == TEAM_A else CRIMSON if x == TEAM_B else MUTED for x in t["team"]]
    fig, ax = plt.subplots(figsize=(9.8, 7.2))
    bars = ax.barh(t["team"], t["form_index_last10"], color=colors, height=0.65)
    ax.axvline(0, color=INK, linewidth=0.9)
    ax.set_xlabel("Form index (mean z-score of last-10 win rate, gold diff, kill diff, objective score)")
    ax.set_title(f"Descriptive last-10 form index: {TEAM_A_CODE} and {TEAM_B_CODE} among the cohort")
    for bar, v in zip(bars, t["form_index_last10"]):
        ax.annotate(
            f"{v:+.2f}",
            xy=(v, bar.get_y() + bar.get_height() / 2),
            xytext=(5 if v >= 0 else -5, 0),
            textcoords="offset points",
            ha="left" if v >= 0 else "right",
            va="center",
            fontsize=8,
        )
    fig.text(
        0.01,
        0.01,
        "The index is descriptive, not a prediction: it ignores schedule context and opponent quality beyond the SOS column in team_kpis.csv. "
        f"{TEAM_A_CODE} and {TEAM_B_CODE} are ranked inside the cohort of {len(t)} teams.",
        fontsize=8,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "10_form_ranking.png")


def main() -> None:
    data = load()
    fig_form(data)
    fig_gd10(data)
    fig_objectives(data)
    fig_history(data)
    fig_model_comparison(data)
    fig_coefficients(data)
    fig_calibration(data)
    fig_prediction(data)
    fig_contributions(data)
    fig_ranking(data)


if __name__ == "__main__":
    main()
