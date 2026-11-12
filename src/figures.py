"""Generate every figure in the report from the measured artefacts."""
from __future__ import annotations

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.patches import FancyArrowPatch

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common import FIGURES, RESULTS

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.labelsize": 9,
        "axes.linewidth": 0.7,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "figure.dpi": 170,
        "savefig.dpi": 170,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "lines.linewidth": 1.4,
    }
)

INK = "#1d1d1b"
ACC = ["#2f5d8c", "#b4542a", "#3f7d5c", "#7a5c9e", "#9a8b2f", "#a04a63"]
GRID = dict(color="#d9d9d4", linewidth=0.6)


def save(fig, name: str) -> None:
    path = os.path.join(FIGURES, name)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  ", name)


def load_json(name: str, default=None):
    path = os.path.join(RESULTS, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_jsonl(name: str) -> list[dict]:
    path = os.path.join(RESULTS, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# ------------------------------------------------------------------ fig 1
def fig_pipeline():
    fig, ax = plt.subplots(figsize=(7.0, 2.55))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.2)
    ax.axis("off")

    stages = [
        ("S0\nIngest", "5 gz dumps\n1.78 GB", "serial\ngunzip"),
        ("S1\nFilter+join", "168 M rows\nscanned", "chunk map-reduce\nprocess pool"),
        ("S2\nGraph build", "478 k edges\n62 k nodes", "partitioned\nby title"),
        ("S3\nGraph analytics", "PageRank\nLouvain", "row-block\n+ barrier"),
        ("S4\nRule mining", "10 k baskets\nitemsets", "sharded count\nno locks"),
    ]
    w, h, y = 1.62, 1.45, 2.05
    for i, (title, sub, par) in enumerate(stages):
        x = 0.25 + i * 1.95
        face = "#eef2f7" if i in (1, 3, 4) else "#f4f1ec"
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.08",
                                             linewidth=0.8, edgecolor="#6b6b66", facecolor=face))
        ax.text(x + w / 2, y + h - 0.26, title, ha="center", va="center", fontsize=8.6, weight="bold", color=INK)
        ax.text(x + w / 2, y + h / 2 - 0.16, sub, ha="center", va="center", fontsize=7.4, color="#3c3c3a")
        ax.text(x + w / 2, y + 0.20, par, ha="center", va="center", fontsize=6.8, color="#2f5d8c", style="italic")
        if i:
            ax.add_patch(FancyArrowPatch((x - 0.30, y + h / 2), (x - 0.02, y + h / 2),
                                         arrowstyle="-|>", mutation_scale=9, linewidth=0.8, color="#6b6b66"))
    ax.text(0.25, 1.10, "parallel tiers", fontsize=7.2, color="#3c3c3a")
    rows = [("tier 1   chunk map-reduce over byte ranges  (S1)", 0.72),
            ("tier 2   blocked sparse matvec, barrier per iteration  (S3)", 0.40),
            ("tier 3   sharded candidate counting, no locks  (S4)", 0.08)]
    for label, ypos in rows:
        ax.add_patch(mpatches.Rectangle((0.30, ypos - 0.05), 0.16, 0.16,
                                        color="#eef2f7", ec="#6b6b66", lw=0.6))
        ax.text(0.58, ypos + 0.03, label, fontsize=7.2, va="center")
    save(fig, "fig01_pipeline.png")


# ------------------------------------------------------------------ fig 2
def fig_dataflow():
    files = [
        ("title.principals", 90.3, "cast and crew credits"),
        ("title.akas", 51.2, "regional release titles"),
        ("name.basics", 14.6, "personal records"),
        ("title.basics", 11.9, "title metadata"),
        ("title.ratings", 1.5, "ratings"),
    ]
    fig, ax = plt.subplots(figsize=(6.4, 2.4))
    names = [f[0] for f in files][::-1]
    rows = [f[1] for f in files][::-1]
    desc = [f[2] for f in files][::-1]
    bars = ax.barh(names, rows, color=ACC[0], height=0.58)
    ax.set_xscale("log")
    ax.set_xlabel("rows in the release (millions, log scale)")
    for b, r, d in zip(bars, rows, desc):
        ax.text(r * 1.12, b.get_y() + b.get_height() / 2, f"{r:.1f} M  ·  {d}",
                va="center", fontsize=7.4, color="#3c3c3a")
    ax.set_xlim(1, 900)
    ax.xaxis.grid(True, **GRID)
    ax.set_axisbelow(True)
    save(fig, "fig02_dataflow.png")


# ------------------------------------------------------------------ fig 3
def fig_decades(a):
    labels = ["<1980", "1980s", "1990s", "2000s", "2010s+"]
    vals = [a["per_decade"].get(k, 0) for k in labels]
    fig, ax = plt.subplots(figsize=(5.4, 2.3))
    bars = ax.bar(labels, vals, color=[ACC[0]] * 5, width=0.62)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + max(vals) * 0.02, str(v), ha="center", fontsize=7.4)
    ax.set_ylabel("films in the working set")
    ax.yaxis.grid(True, **GRID)
    ax.set_axisbelow(True)
    save(fig, "fig03_decades.png")


# ------------------------------------------------------------------ fig 4
def fig_degree(a):
    bins = np.asarray(a["degree_bins"])
    hist = np.asarray(a["degree_hist"], dtype=float)
    centers = (bins[:-1] + bins[1:]) / 2
    width = (bins[1:] - bins[:-1])
    dens = hist / (hist.sum() * width)
    ok = dens > 0
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    ax.scatter(centers[ok], dens[ok], s=9, color=ACC[0], zorder=3, label="empirical")
    # least squares fit on the log-log tail
    tail = ok & (centers > 4)
    if tail.sum() > 3:
        lx, ly = np.log10(centers[tail]), np.log10(dens[tail])
        k, b = np.polyfit(lx, ly, 1)
        ax.plot(centers[tail], 10 ** (k * np.log10(centers[tail]) + b), color=ACC[1], lw=1.1,
                label=f"power-law fit  $\\gamma$ = {-k:.2f}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("degree $k$")
    ax.set_ylabel("$P(k)$")
    ax.legend(frameon=False, loc="lower left")
    ax.grid(True, **GRID)
    ax.set_axisbelow(True)
    save(fig, "fig04_degree.png")


# ------------------------------------------------------------------ fig 5
def fig_pr_degree():
    path = os.path.join(RESULTS, "..", "data", "out", "nodes_scored_top8.csv")
    import csv as _csv

    deg, pr, name = [], [], []
    people = {}
    with open(os.path.join(RESULTS, "..", "data", "interim", "people.csv"), newline="", encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            people[r["nconst"]] = r["primary_name"]
    with open(path, newline="", encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            deg.append(int(r["degree"]))
            pr.append(float(r["pagerank"]))
            name.append(people.get(r["nconst"], r["nconst"]))
    deg = np.asarray(deg)
    pr = np.asarray(pr)
    fig, ax = plt.subplots(figsize=(4.8, 3.3))
    ax.scatter(deg, pr, s=3, alpha=0.25, color=ACC[0], linewidths=0)
    top = np.argsort(-pr)[:6]
    # the six highest-ranked people sit within a few pixels of each other, so the
    # labels are stacked in the empty right margin and connected by leaders
    label_x = deg.max() * 2.4
    label_y = np.geomspace(pr.max() * 1.05, pr.max() * 0.10, len(top))
    for k, i in enumerate(top):
        ax.annotate(name[i], (deg[i], pr[i]), fontsize=6.6, color=ACC[1],
                    xytext=(label_x, label_y[k]), textcoords="data",
                    va="center", ha="left",
                    arrowprops=dict(arrowstyle="-", lw=0.4, color="#9a9a94",
                                    shrinkA=0, shrinkB=1.5))
    ax.set_xlim(0.8, deg.max() * 9)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("degree")
    ax.set_ylabel("PageRank")
    ax.grid(True, **GRID)
    ax.set_axisbelow(True)
    save(fig, "fig05_pr_vs_degree.png")


# ------------------------------------------------------------------ fig 6
def fig_network(a):
    """Community-level block model: the blocs and the collaboration weight between them."""
    import csv as _csv

    lab_path = os.path.join(RESULTS, "..", "data", "out", "node_labels_top8.csv")
    if not os.path.exists(lab_path):
        return
    comm_of, name_of, pr_of = {}, {}, {}
    with open(lab_path, newline="", encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            comm_of[r["nconst"]] = int(r["community"])
            name_of[r["nconst"]] = r["name"]
            pr_of[r["nconst"]] = float(r["pagerank"])

    sizes: dict[int, int] = {}
    for c in comm_of.values():
        sizes[c] = sizes.get(c, 0) + 1
    keep = [c for c, _ in sorted(sizes.items(), key=lambda kv: -kv[1])[:9]]
    remap = {c: i for i, c in enumerate(keep)}
    other = len(keep)

    top_names: dict[int, list[str]] = {c: [] for c in keep}
    for nid, c in comm_of.items():
        if c in remap:
            top_names[c].append((pr_of[nid], name_of[nid]))
    for c in keep:
        top_names[c] = [n for _, n in sorted(top_names[c], reverse=True)[:3]]

    weights: dict[tuple[int, int], float] = {}
    with open(os.path.join(RESULTS, "..", "data", "out", "edges_top8.csv"), newline="", encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            a_i = remap.get(comm_of.get(r["u"], -1), other)
            b_i = remap.get(comm_of.get(r["v"], -1), other)
            if a_i == b_i:
                continue
            key = (min(a_i, b_i), max(a_i, b_i))
            weights[key] = weights.get(key, 0.0) + float(r["weight"])

    n = len(keep) + 1
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False) + 0.35
    pos = {i: (np.cos(t), np.sin(t)) for i, t in enumerate(ang)}
    total = sum(sizes.values())
    counts = [sizes[c] for c in keep] + [total - sum(sizes[c] for c in keep)]

    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    wmax = max(weights.values()) if weights else 1.0
    for (i, j), w in sorted(weights.items(), key=lambda kv: kv[1]):
        if w < wmax * 0.01:
            continue
        x0, y0 = pos[i]
        x1, y1 = pos[j]
        ax.plot([x0, x1], [y0, y1], color="#8a8a84", lw=0.35 + 3.2 * (w / wmax) ** 0.55,
                alpha=0.30 + 0.45 * (w / wmax), zorder=1, solid_capstyle="round")

    for i in range(n):
        r = 0.040 + 0.145 * (counts[i] / total) ** 0.5
        colour = "#b9b9b2" if i == other else ACC[i % len(ACC)]
        ax.add_patch(plt.Circle(pos[i], r, color=colour, alpha=0.30, zorder=2, linewidth=0))
        ax.add_patch(plt.Circle(pos[i], r, fill=False, edgecolor=colour, lw=1.2, zorder=3))
        if i == other:
            label = f"other\n(n={counts[i]:,})"
        else:
            label = "#%d  n=%s\n%s" % (keep[i], f"{counts[i]:,}", ", ".join(top_names[keep[i]][:2]))
        outer = 1.34
        lx, ly = pos[i][0] * outer, pos[i][1] * outer
        if lx > 0.2:
            ha = "left"
        elif lx < -0.2:
            ha = "right"
        else:
            ha = "center"
            ly += 0.10 if pos[i][1] > 0 else -0.10
        ax.text(lx, ly, label, ha=ha, va="center",
                fontsize=6.5, color="#2c2c2a", zorder=4, linespacing=1.35)

    ax.set_xlim(-1.85, 1.85)
    ax.set_ylim(-1.62, 1.62)
    ax.set_aspect("equal")
    ax.axis("off")
    save(fig, "fig06_network.png")


# ------------------------------------------------------------------ fig 8
def fig_flux(a):
    labels = ["<1980", "1980s", "1990s", "2000s", "2010s+"]
    top = a["communities"][:6]
    fig, ax = plt.subplots(figsize=(5.6, 2.9))
    x = np.arange(len(labels))
    for i, (c, row) in enumerate(zip(top, a["flux"][:6])):
        ys = [row[d] for d in labels]
        ax.plot(x, ys, marker="o", ms=3.4, color=ACC[i % len(ACC)],
                label=f"#{c['community']} (n={c['size']})")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("share of community credits")
    ax.set_xlabel("decade")
    ax.legend(frameon=False, ncol=2, fontsize=7)
    ax.grid(True, **GRID)
    ax.set_axisbelow(True)
    save(fig, "fig08_flux.png")


# ------------------------------------------------------------------ fig 9
def fig_rules(a):
    rules = a["rules"]
    if not rules:
        return
    sup = np.array([r["support"] for r in rules])
    lift = np.array([r["lift"] for r in rules])
    conf = np.array([r["confidence"] for r in rules])
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    sc = ax.scatter(sup, lift, c=conf, s=16, cmap="viridis", linewidths=0.3, edgecolors="white")
    cb = fig.colorbar(sc, ax=ax)
    cb.set_label("confidence", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    seen = set()
    placed = 0
    for r in rules:
        key = (r["consequent"], round(r["support"], 3))
        if key in seen:
            continue
        seen.add(key)
        dy = 6 if placed % 2 == 0 else -10
        ax.annotate(f"{r['antecedent']} → {r['consequent']}", (r["support"], r["lift"]),
                    fontsize=5.9, xytext=(5, dy), textcoords="offset points", color="#3c3c3a",
                    arrowprops=dict(arrowstyle="-", lw=0.35, color="#9a9a94", shrinkA=0, shrinkB=2))
        placed += 1
        if placed >= 4:
            break
    ax.set_xlabel("support")
    ax.set_ylabel("lift")
    ax.grid(True, **GRID)
    ax.set_axisbelow(True)
    save(fig, "fig09_rules.png")


# ------------------------------------------------------------------ fig 10-11
def fig_scaling():
    series = {}
    for tag, fname in (("E1", "bench_e1.jsonl"), ("E3", "bench_e3.jsonl"), ("E4", "bench_e4.jsonl")):
        rows = load_jsonl(fname)
        if rows:
            series[tag] = {r["workers"]: r["seconds"] for r in rows}
    if not series:
        return
    fig, ax = plt.subplots(figsize=(5.2, 3.3))
    p_ideal = [1, 2, 4, 8, 16]
    ax.plot(p_ideal, p_ideal, "--", color="#9a9a94", lw=0.9, label="ideal")
    marks = {"E1": "o-", "E3": "s-", "E4": "^-"}
    names = {"E1": "E1 scan and join", "E3": "E3 PageRank", "E4": "E4 rule mining"}
    for i, (tag, data) in enumerate(series.items()):
        ps = sorted(data)
        t1 = data[ps[0]]
        ax.plot(ps, [t1 / data[p] for p in ps], marks[tag], color=ACC[i], ms=4, label=names[tag])
    ax.set_xscale("log", base=2)
    ax.set_yscale("log", base=2)
    ax.set_xticks(p_ideal)
    ax.set_xticklabels(p_ideal)
    ax.set_xlabel("workers $p$")
    ax.set_ylabel("speedup $S(p)$")
    ax.legend(frameon=False)
    ax.grid(True, which="both", **GRID)
    ax.set_axisbelow(True)
    save(fig, "fig10_scaling.png")

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    for i, (tag, data) in enumerate(series.items()):
        ps = sorted(data)
        t1 = data[ps[0]]
        ax.plot(ps, [100 * t1 / data[p] / p for p in ps], marks[tag], color=ACC[i], ms=4, label=names[tag])
    ax.set_xticks(p_ideal)
    ax.set_xticklabels(p_ideal)
    ax.set_ylim(0, 110)
    ax.set_xlabel("workers $p$")
    ax.set_ylabel("parallel efficiency (%)")
    ax.legend(frameon=False)
    ax.grid(True, **GRID)
    ax.set_axisbelow(True)
    save(fig, "fig11_efficiency.png")


# ------------------------------------------------------------------ fig 12
def fig_sweeps():
    e1b = load_jsonl("bench_e1b.jsonl")
    e3b = load_jsonl("bench_e3b.jsonl")
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))
    if e1b:
        xs = [r["chunk_mb"] for r in e1b]
        ys = [r["seconds"] for r in e1b]
        axes[0].plot(xs, ys, "o-", color=ACC[0], ms=4)
        axes[0].set_xscale("log", base=2)
        axes[0].set_xlabel("chunk size (MB)")
        axes[0].set_ylabel("scan time (s)")
        axes[0].set_title("(a) E1b chunk-size sweep, 16 workers", loc="left")
    if e3b:
        xs = [r["blocks"] for r in e3b]
        ys = [r["seconds"] for r in e3b]
        axes[1].plot(xs, ys, "s-", color=ACC[1], ms=4)
        axes[1].set_xscale("log", base=2)
        axes[1].set_xlabel("row blocks")
        axes[1].set_ylabel("PageRank time (s)")
        axes[1].set_title("(b) E3b block-count sweep, 8 threads", loc="left")
    for ax in axes:
        ax.grid(True, **GRID)
        ax.set_axisbelow(True)
    fig.tight_layout(pad=0.6)
    save(fig, "fig12_sweeps.png")


# ------------------------------------------------------------------ fig 13
def fig_memory():
    e1 = load_jsonl("bench_e1.jsonl")
    e4 = load_jsonl("bench_e4.jsonl")
    if not (e1 or e4):
        return
    fig, ax = plt.subplots(figsize=(4.8, 3.0))
    if e1:
        ps = [r["workers"] for r in e1]
        ax.plot(ps, [r.get("peak_mb", 0) for r in e1], "o-", color=ACC[0], ms=4, label="E1 scan")
    if e4:
        ps = [r["workers"] for r in e4]
        ax.plot(ps, [r.get("peak_mb", 0) for r in e4], "^-", color=ACC[2], ms=4, label="E4 rules")
    ax.set_xscale("log", base=2)
    ax.set_xticks([1, 2, 4, 8, 16])
    ax.set_xticklabels([1, 2, 4, 8, 16])
    ax.set_xlabel("workers $p$")
    ax.set_ylabel("peak RSS (MB)")
    ax.legend(frameon=False)
    ax.grid(True, **GRID)
    ax.set_axisbelow(True)
    save(fig, "fig13_memory.png")


# ------------------------------------------------------------------ fig 14
def fig_clusters(a):
    cl = a["clusters"]
    if not cl.get("points"):
        return
    pts = np.asarray(cl["points"])
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    for c in np.unique(pts[:, 2]).astype(int):
        sel = pts[:, 2].astype(int) == c
        ax.scatter(pts[sel, 0], pts[sel, 1], s=3, alpha=0.45, color=ACC[c % len(ACC)],
                   label=f"cluster {c} (n={cl['sizes'][c]})", linewidths=0)
    ax.set_xlabel("PC 1")
    ax.set_ylabel("PC 2")
    ax.legend(frameon=False, markerscale=2.4, fontsize=6.6, loc="best")
    ax.grid(True, **GRID)
    ax.set_axisbelow(True)
    save(fig, "fig14_clusters.png")


def main():
    a = load_json("analysis.json")
    print("figures ->", FIGURES)
    fig_pipeline()
    fig_dataflow()
    if a:
        fig_decades(a)
        fig_degree(a)
        fig_pr_degree()
        fig_network(a)
        fig_flux(a)
        fig_rules(a)
        fig_clusters(a)
    fig_scaling()
    fig_sweeps()
    fig_memory()


if __name__ == "__main__":
    main()
