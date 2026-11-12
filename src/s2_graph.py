"""Stage S2: build the co-star graph and the per-film baskets used by rule mining."""
from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict
from itertools import combinations

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common import INTERIM, OUT

ACTING = {"actor", "actress"}


def load_titles() -> dict:
    path = os.path.join(INTERIM, "hk_titles.csv")
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            year = int(row["start_year"]) if row["start_year"] else None
            genres = [g for g in row["genres"].split(",") if g]
            out[row["tconst"]] = {"type": row["title_type"], "year": year, "genres": genres}
    return out


def group_cast(top_k: int = 8, keep_titles=None) -> dict:
    """Return {tconst: [nconst, ...]} ordered by billing, truncated to top_k acting credits.

    `keep_titles` restricts the graph to the typed working set (movie / tvMovie / short)
    written by S1; without it, credits attached to other title types would enter the
    network and the node count would not reconcile with the reported working set.
    """
    path = os.path.join(INTERIM, "hk_principals.csv")
    cast: dict[str, list[tuple[int, str]]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["category"] not in ACTING:
                continue
            if keep_titles is not None and row["tconst"] not in keep_titles:
                continue
            try:
                order = int(row["ordering"])
            except ValueError:
                order = 999
            cast[row["tconst"]].append((order, row["nconst"]))
    out = {}
    for tid, credits in cast.items():
        credits.sort()
        seen = []
        for _, person in credits:
            if person not in seen:
                seen.append(person)
            if len(seen) >= top_k:
                break
        out[tid] = seen
    return out


def build_edges(cast: dict, titles: dict, min_year=None) -> dict:
    """Weighted undirected co-star edges with the span of collaboration years."""
    edges: dict[tuple[str, str], list] = {}
    for tid, people in cast.items():
        if len(people) < 2:
            continue
        year = titles.get(tid, {}).get("year")
        if min_year is not None and (year is None or year < min_year):
            continue
        for a, b in combinations(sorted(people), 2):
            rec = edges.get((a, b))
            if rec is None:
                edges[(a, b)] = [1, year, year]
            else:
                rec[0] += 1
                if year is not None:
                    rec[1] = year if rec[1] is None else min(rec[1], year)
                    rec[2] = year if rec[2] is None else max(rec[2], year)
    return edges


def write_edges(edges: dict, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["u", "v", "weight", "first_year", "last_year"])
        for (a, b), (wgt, y0, y1) in edges.items():
            w.writerow([a, b, wgt, "" if y0 is None else y0, "" if y1 is None else y1])


def main(top_k: int = 8) -> dict:
    titles = load_titles()
    cast = group_cast(top_k=top_k, keep_titles=set(titles))
    edges = build_edges(cast, titles)

    nodes = defaultdict(lambda: [0, 0])
    for (a, b), (wgt, _, _) in edges.items():
        nodes[a][0] += 1
        nodes[a][1] += wgt
        nodes[b][0] += 1
        nodes[b][1] += wgt

    edge_path = os.path.join(OUT, f"edges_top{top_k}.csv")
    write_edges(edges, edge_path)
    node_path = os.path.join(OUT, f"nodes_top{top_k}.csv")
    with open(node_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["nconst", "degree", "weighted_degree"])
        for nid, (deg, wdeg) in nodes.items():
            w.writerow([nid, deg, wdeg])

    # cast size distribution for the report
    sizes = [len(v) for v in cast.values()]
    summary = {
        "top_k": top_k,
        "titles_with_cast": len(cast),
        "titles_with_edge": sum(1 for v in cast.values() if len(v) >= 2),
        "nodes": len(nodes),
        "edges": len(edges),
        "total_weight": sum(w for w, _, _ in edges.values()),
        "mean_cast_size": round(sum(sizes) / len(sizes), 2) if sizes else 0,
    }
    return summary, cast, titles


if __name__ == "__main__":
    import json

    out = {}
    for k in (3, 8):
        s, _, _ = main(top_k=k)
        out[f"top{k}"] = s
        print(json.dumps(s, indent=2))
    path = os.path.join(os.path.dirname(INTERIM), "..", "results", "s2_summary.json")
    with open(os.path.abspath(path), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("wrote", os.path.abspath(path))
