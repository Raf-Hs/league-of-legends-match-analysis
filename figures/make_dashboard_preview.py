"""Generate a static dark-theme preview of the Power BI dashboard.

This is a portfolio preview/mockup rendered with matplotlib — it is NOT the
interactive Power BI report. The real report is built in Power BI Desktop from
the 19 CSVs in data/powerbi/ using powerbi/dashboard_guide.md.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "dashboard_preview.png"

# --- palette (matches powerbi/theme.json) ---
BG = "#1A1A1D"
PANEL = "#252529"
BORDER = "#3A3A3F"
ORANGE = "#FF6B35"
BLUE = "#2D7FF9"
GREEN = "#00C9A7"
RED = "#EF4444"
PURPLE = "#8B5CF6"
MUTED = "#9CA3AF"
TEXT = "#F5F5F7"
DIM = "#6B7280"

d = json.loads((ROOT / "data" / "processed" / "prediction_summary.json").read_text())
m = d["primary_model"]
mc = pd.read_csv(ROOT / "data" / "processed" / "model_comparison.csv")
contrib = pd.read_csv(ROOT / "data" / "processed" / "target_feature_contributions.csv").sort_values(
    "log_odds_contribution"
)
team = pd.read_csv(ROOT / "data" / "processed" / "team_kpis.csv")
fixtures = pd.read_csv(ROOT / "data" / "processed" / "fixture_predictions.csv")
fact = pd.read_csv(ROOT / "data" / "processed" / "fact_team_games.csv")

n_matches = fact["oe_game_id"].nunique()
n_teams = fact["team"].nunique()
n_stages = fact["tournament"].nunique()
holdout = m["holdout_metrics"]

fig = plt.figure(figsize=(16, 9), dpi=110, facecolor=BG)
gs = fig.add_gridspec(
    4, 4, height_ratios=[0.7, 1.6, 1.6, 1.6],
    hspace=0.35, wspace=0.25,
    left=0.04, right=0.98, top=0.93, bottom=0.06,
)

# ---------------- title bar ----------------
title_ax = fig.add_axes([0.04, 0.945, 0.94, 0.04])
title_ax.set_facecolor(BG)
title_ax.axis("off")
title_ax.text(0, 0.5, "League of Legends — Match Prediction & Analytics Dashboard",
              color=TEXT, fontsize=18, fontweight="bold", va="center")
title_ax.text(0.0, -0.4, "Worlds 2026 · Data cutoff 2026-10-27 00:00 UTC · Holdout evaluation, not a betting model",
              color=MUTED, fontsize=10, va="center")
title_ax.text(1.0, 0.5, "DARK THEME PREVIEW (mockup)", color=MUTED, fontsize=9,
              va="center", ha="right", style="italic")

# ---------------- KPI cards (top) ----------------
kpis = [
    ("Total Matches", f"{n_matches:,}", ORANGE),
    ("Unique Teams", f"{n_teams}", BLUE),
    ("Competition Stages", f"{n_stages}", ORANGE),
    ("Test Matches", f"{holdout['n']}", BLUE),
    ("ROC-AUC", f"{holdout['auc']:.3f}", ORANGE),
    ("Brier Score", f"{holdout['brier']:.3f}", BLUE),
]
for i, (label, value, color) in enumerate(kpis):
    ax = fig.add_subplot(gs[0, i % 3 if i < 3 else (i - 3)])
    # actually use a 6-cell row manually
    pass

# lay out 6 cards across the top row using a dedicated gridspec
kpi_gs = fig.add_gridspec(1, 6, left=0.04, right=0.98, top=0.92, bottom=0.80, wspace=0.08)
for i, (label, value, color) in enumerate(kpis):
    ax = fig.add_subplot(kpi_gs[0, i])
    ax.set_facecolor(PANEL)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.text(0.5, 0.72, value, transform=ax.transAxes, color=color,
            fontsize=22, fontweight="bold", ha="center", va="center")
    ax.text(0.5, 0.30, label, transform=ax.transAxes, color=MUTED,
            fontsize=9, ha="center", va="center")
    ax.text(0.5, 0.12, "pipeline output", transform=ax.transAxes, color=DIM,
            fontsize=7, ha="center", va="center")

# ---------------- main charts (middle) ----------------
# 1. Model comparison (bar)
ax1 = fig.add_subplot(gs[1, :2])
ax1.set_facecolor(PANEL)
for spine in ax1.spines.values():
    spine.set_color(BORDER)
names = mc["model"].tolist()
auc = mc["auc"].tolist()
brier = mc["brier"].tolist()
x = np.arange(len(names))
w = 0.38
ax1.bar(x - w / 2, auc, w, color=ORANGE, label="ROC-AUC")
ax1.bar(x + w / 2, brier, w, color=BLUE, label="Brier")
ax1.axhline(0.5, color=MUTED, linestyle="--", linewidth=1, alpha=0.6)
ax1.set_xticks(x)
ax1.set_xticklabels(names, rotation=25, ha="right", fontsize=8, color=TEXT)
ax1.set_title("Model comparison (chronological holdout, n=85)", color=TEXT, fontsize=11, fontweight="bold", pad=8)
ax1.tick_params(colors=MUTED)
ax1.set_ylim(0, 0.8)
ax1.legend(fontsize=8, loc="upper right", facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT)
ax1.grid(axis="y", alpha=0.15, color=BORDER)

# 2. Feature contributions
ax2 = fig.add_subplot(gs[1, 2:])
ax2.set_facecolor(PANEL)
for spine in ax2.spines.values():
    spine.set_color(BORDER)
contrib_sorted = contrib.sort_values("log_odds_contribution")
colors = [RED if v < 0 else GREEN for v in contrib_sorted["log_odds_contribution"]]
ax2.barh(contrib_sorted["label"], contrib_sorted["log_odds_contribution"], color=colors, height=0.6)
ax2.axvline(0, color=MUTED, linewidth=1)
ax2.set_title("What moves the primary model (log-odds)", color=TEXT, fontsize=11, fontweight="bold", pad=8)
ax2.tick_params(colors=TEXT, labelsize=9)
ax2.grid(axis="x", alpha=0.15, color=BORDER)
net = contrib["log_odds_contribution"].sum()
ax2.text(0.98, 0.05, f"Net = {net:+.3f}  ->  P(LYON) = 41.4%",
         transform=ax2.transAxes, color=TEXT, fontsize=9, ha="right",
         bbox=dict(boxstyle="round,pad=0.3", facecolor=BG, edgecolor=BORDER))

# 3. Team performance comparison
ax3 = fig.add_subplot(gs[2, :2])
ax3.set_facecolor(PANEL)
for spine in ax3.spines.values():
    spine.set_color(BORDER)
teams = ["LYON", "IG"]
gd10 = [-395.8, -487.5]
gold = [-2127.4, 1064.4]
obj = [-1.7, 2.0]
fb = [0.4, 0.2]
x = np.arange(len(teams))
w = 0.2
ax3.bar(x - 1.5 * w, gd10, w, color=ORANGE, label="GD@10")
ax3.bar(x - 0.5 * w, gold, w, color=BLUE, label="End-game gold")
ax3.bar(x + 0.5 * w, [o * 1000 for o in obj], w, color=GREEN, label="Objective x1000")
ax3.bar(x + 1.5 * w, [f * 1000 for f in fb], w, color=PURPLE, label="First blood x1000")
ax3.set_xticks(x)
ax3.set_xticklabels(teams, color=TEXT, fontsize=10)
ax3.set_title("LYON vs IG — last-10 profile", color=TEXT, fontsize=11, fontweight="bold", pad=8)
ax3.tick_params(colors=MUTED)
ax3.legend(fontsize=7, loc="lower right", facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT)
ax3.grid(axis="y", alpha=0.15, color=BORDER)
ax3.axhline(0, color=MUTED, linewidth=0.8)

# 4. Prediction probability distribution (holdout)
ax4 = fig.add_subplot(gs[2, 2:])
ax4.set_facecolor(PANEL)
for spine in ax4.spines.values():
    spine.set_color(BORDER)
preds = pd.read_csv(ROOT / "data" / "processed" / "model_predictions_test.csv")
primary = preds[preds["model"] == "M3_core5"]["predicted_probability_team_a"]
ax4.hist(primary, bins=12, color=ORANGE, alpha=0.85, edgecolor=BG)
ax4.axvline(0.5, color=BLUE, linestyle="--", linewidth=1.5, label="0.50 (no edge)")
ax4.set_title("Holdout prediction distribution (primary model)", color=TEXT, fontsize=11, fontweight="bold", pad=8)
ax4.set_xlabel("P(team A wins)", color=MUTED, fontsize=9)
ax4.set_ylabel("Games", color=MUTED, fontsize=9)
ax4.tick_params(colors=MUTED)
ax4.legend(fontsize=8, facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT)
ax4.grid(axis="y", alpha=0.15, color=BORDER)

# ---------------- side panel: key findings ----------------
side = fig.add_axes([0.04, 0.06, 0.23, 0.22])
side.set_facecolor(PANEL)
for spine in side.spines.values():
    spine.set_color(BORDER)
side.axis("off")
side.text(0.05, 0.95, "Key findings", color=TEXT, fontsize=12, fontweight="bold", va="top")
findings = [
    "IG 58.6% / LYON 41.4% per game (Bo3: 62.8% / 37.2%)",
    "90% CI for LYON: 33.5% – 48.9% (contains 50%)",
    "Holdout AUC 0.477, Brier 0.259 vs 0.250 coin flip",
    "Every specification is at/below the coin flip",
    "IG leads end-game gold (+3,192) and objectives (+3.7)",
    "LYON leads early (GD@10 +92) and first blood (40% vs 20%)",
    "Both teams 5-5 in their last 10 games",
    "No head-to-head in the collected sample",
]
y = 0.82
for f in findings:
    side.text(0.05, y, "• " + f, color=TEXT, fontsize=8.5, va="top", wrap=True)
    y -= 0.105

# ---------------- bottom: slate table ----------------
slate = fig.add_axes([0.29, 0.06, 0.69, 0.22])
slate.set_facecolor(PANEL)
for spine in slate.spines.values():
    spine.set_color(BORDER)
slate.axis("off")
slate.text(0.02, 0.92, "Wednesday slate (pre-registered)", color=TEXT, fontsize=12, fontweight="bold", va="top")
slate.text(0.02, 0.78, "Start (UTC)", color=MUTED, fontsize=9, va="top")
slate.text(0.16, 0.78, "Fixture", color=MUTED, fontsize=9, va="top")
slate.text(0.34, 0.78, "Per game", color=MUTED, fontsize=9, va="top")
slate.text(0.48, 0.78, "Bo3 series", color=MUTED, fontsize=9, va="top")
slate.text(0.62, 0.78, "90% CI", color=MUTED, fontsize=9, va="top")
slate.text(0.78, 0.78, "Read", color=MUTED, fontsize=9, va="top")
rows = [
    ("2026-10-28 20:00", "MKOI vs T1", "50.9% / 49.1%", "51.4% / 48.6%", "41.6% – 60.1%", "Coin flip"),
    ("2026-10-28 23:00", "LYON vs IG", "41.4% / 58.6%", "37.2% / 62.8%", "33.5% – 48.9%", "Marginal IG lean"),
]
y = 0.62
for r in rows:
    for col, val in zip([0.02, 0.16, 0.34, 0.48, 0.62, 0.78], r):
        slate.text(col, y, val, color=TEXT, fontsize=9, va="top")
    y -= 0.16
slate.text(0.02, 0.22, "Model: L2 logistic regression, C=0.5, no intercept, 5 features · 179 modelling games · 94 train / 85 test · AUC 0.477 · Brier 0.259",
           color=MUTED, fontsize=8, va="top", style="italic")
slate.text(0.02, 0.12, "MOCKUP / PORTFOLIO PREVIEW — the real interactive dashboard is built in Power BI Desktop from data/powerbi/*.csv (see powerbi/dashboard_guide.md).",
           color=DIM, fontsize=7.5, va="top", style="italic")

fig.savefig(OUT, dpi=100, facecolor=BG, bbox_inches="tight")
plt.close(fig)
print("wrote", OUT, "(", os.path.getsize(OUT), "bytes )")
