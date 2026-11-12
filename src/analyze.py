"""Substantive analysis: communities, temporal flux, rules, career clusters.

Produces everything the figures and the report need, as JSON plus small CSVs.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
from scipy import sparse
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import s3_analytics as s3
from src import s4_rules as s4
from src.common import INTERIM, OUT, RESULTS, dump_json

DECADES = ["<1980", "1980s", "1990s", "2000s", "2010s+"]


def decade_of(year: int | None) -> str:
    if year is None:
        return "unknown"
    if year < 1980:
        return "<1980"
    if year < 1990:
        return "1980s"
    if year < 2000:
        return "1990s"
    if year < 2010:
        return "2000s"
    return "2010s+"


def load_titles() -> dict:
    out = {}
    with open(os.path.join(INTERIM, "hk_titles.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[r["tconst"]] = {
                "year": int(r["start_year"]) if r["start_year"] else None,
                "genres": [g for g in r["genres"].split(",") if g],
            }
    return out


def load_people() -> dict:
    out = {}
    with open(os.path.join(INTERIM, "people.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[r["nconst"]] = {
                "name": r["primary_name"],
                "birth": int(r["birth_year"]) if r["birth_year"] else None,
                "professions": [p for p in r["professions"].split(",") if p],
            }
    return out


def person_activity(titles: dict) -> tuple[dict, dict]:
    """person -> Counter(decade), and person -> credit count."""
    decades: dict[str, Counter] = defaultdict(Counter)
    credits: dict[str, int] = Counter()
    with open(os.path.join(INTERIM, "hk_principals.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = titles.get(r["tconst"])
            if not t:
                continue
            d = decade_of(t["year"])
            decades[r["nconst"]][d] += 1
            credits[r["nconst"]] += 1
    return decades, credits


def career_features(decades: dict, credits: dict, titles: dict) -> tuple[list[str], np.ndarray]:
    """Features: career length, credits/year, decade breadth, peak decade share."""
    ids, rows = [], []
    for pid, dec in decades.items():
        years = [y for y in (titles.get(t, {}).get("year") for t in []) if y]
        total = sum(dec.values())
        if total < 3:
            continue
        active = [d for d in DECADES if dec.get(d, 0) > 0]
        span = len(active)
        peak = max(dec.values()) / total if total else 0.0
        ids.append(pid)
        rows.append([total, span, peak, len(dec), dec.get("2010s+", 0) / total])
    return ids, np.asarray(rows, dtype=float)


def community_summary(labels: np.ndarray, nodes: list[str], pr: np.ndarray, people: dict, top: int = 12):
    order = np.argsort(-pr)
    groups: dict[int, list[int]] = defaultdict(list)
    for i in order:
        groups[int(labels[i])].append(int(i))
    out = []
    for cid, members in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:top]:
        top_members = [(people.get(nodes[i], {}).get("name", nodes[i]), float(pr[i])) for i in members[:5]]
        out.append(
            {
                "community": cid,
                "size": len(members),
                "top_members": top_members,
                "share": round(len(members) / len(nodes), 4),
            }
        )
    return out


def temporal_flux(labels: np.ndarray, nodes: list[str], decades: dict, communities: list[dict]):
    """For each major community, the share of its members active in each decade."""
    idx = {n: i for i, n in enumerate(nodes)}
    rows = []
    for c in communities:
        cid = c["community"]
        members = [nodes[i] for i in range(len(nodes)) if int(labels[i]) == cid]
        counts = Counter()
        for m in members:
            for d, k in decades.get(m, {}).items():
                if d in DECADES:
                    counts[d] += k
        total = sum(counts.values()) or 1
        rows.append({d: round(counts.get(d, 0) / total, 4) for d in DECADES})
    return rows


def main(top_k: int = 8, workers: int = 8) -> dict:
    titles = load_titles()
    people = load_people()
    decades, credits = person_activity(titles)

    nodes, index, A, _ = s3.load_graph(top_k)
    PT = s3.transition(A).T.tocsr()
    pr, per_iter = s3.pagerank_serial(PT)
    bt = s3.betweenness_sampled(A, k=64, workers=workers)
    deg = np.asarray(A.sum(axis=1)).ravel()

    # community structure: Louvain (quality) with a seed-stability check,
    # plus label propagation as the cheap alternative
    labels, k_comm, lv_secs = s3.louvain_partition(A, resolution=1.0, seed=1)
    alt, _, _ = s3.louvain_partition(A, resolution=1.0, seed=2)
    stability = s3.nmi(labels, alt)
    q_louvain = s3.modularity(A, labels)

    lpa_labels, lpa_per = s3.label_propagation(A, workers=workers)
    q_lpa = s3.modularity(A, lpa_labels)
    lpa_comm = int(len(np.unique(lpa_labels)))

    sweep = []
    for res in (0.25, 0.5, 1.0):
        lab_r, k_r, secs_r = s3.louvain_partition(A, resolution=res, seed=1)
        u, c = np.unique(lab_r, return_counts=True)
        sweep.append(
            {
                "resolution": res,
                "communities": int(k_r),
                "q": round(s3.modularity(A, lab_r), 4),
                "largest": int(c.max()),
                "largest_share": round(float(c.max() / len(lab_r)), 4),
                "seconds": round(secs_r, 2),
            }
        )

    comms = community_summary(labels, nodes, pr, people)
    flux = temporal_flux(labels, nodes, decades, comms)

    # decade distribution of films
    per_decade = Counter(decade_of(t["year"]) for t in titles.values())

    # career clustering
    ids, X = career_features(decades, credits, titles)
    if len(X) > 50:
        Xs = StandardScaler().fit_transform(X)
        best_k, best_s = 4, -1.0
        for k in range(2, 9):
            km = KMeans(n_clusters=k, n_init=10, random_state=3).fit(Xs)
            s = silhouette_score(Xs, km.labels_, sample_size=min(5000, len(Xs)), random_state=3)
            if s > best_s:
                best_k, best_s = k, s
        km = KMeans(n_clusters=best_k, n_init=10, random_state=3).fit(Xs)
        pcs = PCA(n_components=2, random_state=3).fit_transform(Xs)
        cluster_sizes = [int(v) for v in np.bincount(km.labels_)]
        sample = np.random.default_rng(5).choice(len(ids), size=min(4000, len(ids)), replace=False)
        cluster_payload = {
            "k": best_k,
            "silhouette": round(float(best_s), 4),
            "sizes": cluster_sizes,
            "points": [[float(pcs[i, 0]), float(pcs[i, 1]), int(km.labels_[i])] for i in sample],
        }
    else:
        cluster_payload = {"k": 0, "silhouette": 0, "sizes": [], "points": []}

    # rules
    tx, names = s4.build_baskets()
    mined = s4.mine(tx, 0.01, workers=workers, max_k=3)
    rules = s4.rules_from_itemsets(mined["itemsets"], mined["transactions"], names)
    for r in rules:
        r["support"] = round(r["support"], 5)
        r["confidence"] = round(r["confidence"], 4)
        r["lift"] = round(r["lift"], 4)

    # graph sample for the network figure
    top_nodes = np.argsort(-pr)[:500]
    sub = A[top_nodes][:, top_nodes].tocoo()
    node_payload = [
        {"id": nodes[i], "name": people.get(nodes[i], {}).get("name", nodes[i]), "pr": float(pr[i]),
         "deg": int(deg[i]), "comm": int(labels[i])}
        for i in top_nodes
    ]
    edge_payload = [[int(r), int(c), float(w)] for r, c, w in zip(sub.row, sub.col, sub.data) if r < c]

    payload = {
        "top_k": top_k,
        "graph": {"nodes": len(nodes), "edges": int(A.nnz // 2), "density": float(A.nnz / (len(nodes) ** 2))},
        "pagerank": {"iterations": len(per_iter), "seconds": round(float(np.sum(per_iter)), 3)},
        "community": {
            "method": "louvain",
            "resolution": 1.0,
            "n": k_comm,
            "q": round(float(q_louvain), 4),
            "seconds": round(lv_secs, 2),
            "stability_nmi": round(stability, 4),
            "lpa": {"n": lpa_comm, "q": round(float(q_lpa), 4), "iters": len(lpa_per)},
            "sweep": sweep,
        },
        "modularity_lpa": round(float(q_lpa), 4),
        "n_communities": int(k_comm),
        "degree_pagerank_spearman": s3._spearman(deg, pr),
        "titles": len(titles),
        "per_decade": {d: per_decade.get(d, 0) for d in DECADES + ["unknown"]},
        "communities": comms,
        "flux": flux,
        "rules": rules[:40],
        "n_rules": len(rules),
        "clusters": cluster_payload,
        "network": {"nodes": node_payload, "edges": edge_payload},
        "degree_hist": np.histogram(deg, bins=np.logspace(0, np.log10(max(2, deg.max()) + 1), 28))[0].tolist(),
        "degree_bins": np.logspace(0, np.log10(max(2, deg.max()) + 1), 28).tolist(),
        "spearman": s3._spearman(deg, pr),
    }
    dump_json("analysis.json", payload)
    return payload


if __name__ == "__main__":
    p = main(top_k=int(sys.argv[1]) if len(sys.argv) > 1 else 8)
    print(json.dumps({k: p[k] for k in ("graph", "modularity_lpa", "n_communities", "titles", "per_decade", "n_rules")}, indent=2))
    print("top communities:")
    for c in p["communities"][:6]:
        print(f"  #{c['community']} size={c['size']:5d} :: " + ", ".join(m[0] for m in c["top_members"]))
