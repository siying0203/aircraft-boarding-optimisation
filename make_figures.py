"""Draw the figures in results/figures from the CSV files written by
run_experiments.py."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"

SURFACE = "#fcfcfb"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SERIES = {  # fixed categorical order
    "MIP allocation": ("#2a78d6", "o", "-"),
    "Random allocation": ("#eb6834", "s", "--"),
    "Random boarding": ("#1baf7a", "^", ":"),
}

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK_2,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 10,
    }
)


def figure_bags():
    t = pd.read_csv(RESULTS / "experiment_1.csv")
    shares = sorted(t.family_share.unique())
    fig, axes = plt.subplots(1, len(shares), figsize=(11, 3.9), sharey=True)
    cols = {"MIP allocation": "t_mip", "Random allocation": "t_random_allocation", "Random boarding": "t_random_boarding"}
    for ax, share in zip(axes, shares):
        d = t[t.family_share == share]
        x = d.share_two_bags * 100
        for name, col in cols.items():
            color, marker, ls = SERIES[name]
            ax.plot(x, d[col] / 60, color=color, marker=marker, linestyle=ls, lw=2, ms=6, label=name)
        ax.set_title(f"{share:.0%} family passengers", color=INK, fontsize=10.5)
        ax.set_xlabel("Ordinary passengers with 2 bags (%)")
        ax.set_xticks([20, 40, 60, 80, 100])
    axes[0].set_ylabel("Boarding time (minutes)")
    axes[0].set_ylim(0, None)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIGURES / "experiment_1_bags.png", dpi=150)
    plt.close(fig)


def figure_robustness():
    r = pd.read_csv(RESULTS / "robustness_draws.csv")
    gain = (1 - r.t_mip / r.t_random_allocation) * 100
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.hist(gain, bins=40, color=SERIES["MIP allocation"][0], edgecolor=SURFACE, linewidth=1)
    ax.axvline(0, color=INK_2, lw=1)
    ax.axvline(gain.mean(), color=INK, lw=1.2, linestyle="--")
    ax.annotate(f"mean {gain.mean():.1f}%", (gain.mean(), ax.get_ylim()[1] * 0.92), xytext=(6, 0),
                textcoords="offset points", fontsize=9, color=INK)
    ax.set_xlabel("Time saved by the MIP allocation vs. a random allocation (%)")
    ax.set_ylabel("Simulated boardings")
    ax.set_title("Random walking, sitting and stowing times (log-sd 0.3)", color=INK, fontsize=10.5)
    fig.tight_layout()
    fig.savefig(FIGURES / "robustness.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    FIGURES.mkdir(parents=True, exist_ok=True)
    figure_bags()
    figure_robustness()
