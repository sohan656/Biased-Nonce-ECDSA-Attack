#!/usr/bin/env python3
"""
make_plots.py -- turn results/experiments.csv into report-ready figures.

Outputs (results/):
  fig_success_vs_bias.png   success rate vs bias bits l
  fig_success_vs_sigs.png   success rate vs number of signatures t
  fig_runtime_vs_dim.png    LLL runtime vs lattice dimension
  fig_model_comparison.png  recovery rate per bias model
"""
import os, csv
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "results", "experiments.csv")
OUT = os.path.join(ROOT, "results")

KEYBITS = 446
plt.rcParams.update({
    "figure.dpi": 130, "font.size": 11, "axes.grid": True,
    "grid.alpha": 0.25, "axes.spines.top": False, "axes.spines.right": False,
    "font.family": "DejaVu Sans",
})
GREEN, BLUE, AMBER = "#1f9d5a", "#2f7fd1", "#e0a020"


def load():
    rows = []
    with open(CSV) as f:
        for r in csv.DictReader(f):
            for k in ("l", "t", "dim", "trial", "success", "verified"):
                r[k] = int(r[k])
            r["seconds"] = float(r["seconds"])
            rows.append(r)
    return rows


def rate_by(rows, exp, key):
    agg = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["experiment"] == exp:
            agg[r[key]][0] += r["success"]; agg[r[key]][1] += 1
    xs = sorted(agg)
    return xs, [agg[x][0] / agg[x][1] for x in xs], [agg[x][1] for x in xs]


def plot_success_vs_bias(rows):
    xs, ys, ns = rate_by(rows, "vs_bias", "l")
    if not xs:
        return
    t_fixed = next(r["t"] for r in rows if r["experiment"] == "vs_bias")
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.plot(xs, ys, "-o", color=GREEN, lw=2.2, ms=7)
    bound = KEYBITS / t_fixed
    ax.axvline(bound, color="#c0392b", ls="--", lw=1.4)
    ax.text(bound + 0.1, 0.5, f"info-theoretic\nbound  l·t = {KEYBITS}",
            color="#c0392b", fontsize=9, va="center")
    ax.set_xlabel("bias  l   (known/zero bits per nonce)")
    ax.set_ylabel("private-key recovery rate")
    ax.set_ylim(-0.05, 1.08)
    ax.set_title(f"Recovery rate vs nonce bias  (t = {t_fixed} signatures fixed)")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_success_vs_bias.png"))
    plt.close(fig); print("wrote fig_success_vs_bias.png")


def plot_success_vs_sigs(rows):
    xs, ys, ns = rate_by(rows, "vs_sigs", "t")
    if not xs:
        return
    l_fixed = next(r["l"] for r in rows if r["experiment"] == "vs_sigs")
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.plot(xs, ys, "-o", color=BLUE, lw=2.2, ms=7)
    bound = KEYBITS / l_fixed
    ax.axvline(bound, color="#c0392b", ls="--", lw=1.4)
    ax.text(bound + 0.3, 0.5, f"bound\nt = {KEYBITS}/l", color="#c0392b", fontsize=9, va="center")
    ax.set_xlabel("number of signatures  t")
    ax.set_ylabel("private-key recovery rate")
    ax.set_ylim(-0.05, 1.08)
    ax.set_title(f"Recovery rate vs #signatures  (l = {l_fixed} bits fixed)")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_success_vs_sigs.png"))
    plt.close(fig); print("wrote fig_success_vs_sigs.png")


def plot_runtime(rows):
    agg = defaultdict(list)
    for r in rows:
        if r["experiment"] == "runtime":
            agg[r["dim"]].append(r["seconds"])
    if not agg:
        return
    xs = sorted(agg); ys = [sum(agg[x]) / len(agg[x]) for x in xs]
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.plot(xs, ys, "-o", color=AMBER, lw=2.2, ms=7)
    ax.set_xlabel("lattice dimension  (t + 2)")
    ax.set_ylabel("wall-clock time  (s)")
    ax.set_title("Pure-Python LLL runtime vs lattice dimension")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_runtime_vs_dim.png"))
    plt.close(fig); print("wrote fig_runtime_vs_dim.png")


def plot_models(rows):
    agg = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["experiment"] == "models":
            agg[r["model"]][0] += r["success"]; agg[r["model"]][1] += 1
    if not agg:
        return
    order = [m for m in ["zero_msb", "zero_lsb", "known_msb"] if m in agg]
    labels = {"zero_msb": "Zero MSB", "zero_lsb": "Zero LSB", "known_msb": "Known MSB"}
    ys = [agg[m][0] / agg[m][1] for m in order]
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    bars = ax.bar([labels[m] for m in order], ys, color=[GREEN, BLUE, AMBER][:len(order)], width=0.55)
    for b, y in zip(bars, ys):
        ax.text(b.get_x() + b.get_width() / 2, y + 0.02, f"{y*100:.0f}%", ha="center", fontsize=10)
    ax.set_ylabel("recovery rate")
    ax.set_ylim(0, 1.12)
    s = next(r for r in rows if r["experiment"] == "models")
    ax.set_title(f"Bias-model comparison  (l = {s['l']}, t = {s['t']})")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_model_comparison.png"))
    plt.close(fig); print("wrote fig_model_comparison.png")


def main():
    rows = load()
    print(f"loaded {len(rows)} trials")
    plot_success_vs_bias(rows)
    plot_success_vs_sigs(rows)
    plot_runtime(rows)
    plot_models(rows)


if __name__ == "__main__":
    main()
