"""Stage S3: parallel graph analytics on the co-star network.

Three parallel workloads live here:
  * PageRank          - iterative sparse matvec, row-block decomposition, barrier per iteration
  * label propagation - iterative label updates over adjacency blocks
  * betweenness       - sampled Brandes, embarrassingly parallel over pivot sources
Each has a serial reference implementation so that speedup can be measured on
identical work.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy import sparse

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common import INTERIM, OUT


# ---------------------------------------------------------------- graph loading
def load_graph(top_k: int = 8):
    """Load the edge list and return (nodes, index, csr adjacency, weights)."""
    path = os.path.join(OUT, f"edges_top{top_k}.csv")
    nodes: list[str] = []
    index: dict[str, int] = {}
    rows, cols, wts = [], [], []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            for key in (r["u"], r["v"]):
                if key not in index:
                    index[key] = len(nodes)
                    nodes.append(key)
            rows.append(index[r["u"]])
            cols.append(index[r["v"]])
            wts.append(float(r["weight"]))
    n = len(nodes)
    r = np.asarray(rows, dtype=np.int64)
    c = np.asarray(cols, dtype=np.int64)
    w = np.asarray(wts, dtype=np.float64)
    A = sparse.coo_matrix((w, (r, c)), shape=(n, n)).tocsr()
    A = A + A.T - sparse.diags(A.diagonal())
    return nodes, index, A, w


def transition(A: sparse.csr_matrix) -> sparse.csr_matrix:
    """Row-stochastic transition matrix for the undirected weighted graph."""
    deg = np.asarray(A.sum(axis=1)).ravel()
    deg[deg == 0] = 1.0
    return sparse.diags(1.0 / deg) @ A


# ---------------------------------------------------------------- PageRank
def pagerank_serial(PT: sparse.csr_matrix, alpha: float = 0.85, tol: float = 1e-10, max_iter: int = 200):
    n = PT.shape[0]
    x = np.full(n, 1.0 / n)
    teleport = (1.0 - alpha) / n
    per_iter = []
    for _ in range(max_iter):
        t0 = time.perf_counter()
        y = PT.dot(x)
        y = alpha * y + teleport
        delta = np.abs(y - x).sum()
        x = y
        per_iter.append(time.perf_counter() - t0)
        if delta < tol:
            break
    return x, per_iter


def _block_bounds(n: int, workers: int) -> list[tuple[int, int]]:
    edges = np.linspace(0, n, workers + 1).astype(int)
    return [(int(edges[i]), int(edges[i + 1])) for i in range(workers)]


def pagerank_blocked(
    PT: sparse.csr_matrix,
    workers: int,
    blocks: int | None = None,
    alpha: float = 0.85,
    tol: float = 1e-10,
    max_iter: int = 200,
):
    """Owner-computes row-block matvec; one barrier (pool join) per iteration."""
    n = PT.shape[0]
    n_blocks = blocks or workers
    bounds = _block_bounds(n, n_blocks)
    mats = [PT[s:e] for s, e in bounds]          # sliced once, reused every iteration
    x = np.full(n, 1.0 / n)
    teleport = (1.0 - alpha) / n
    y = np.empty(n)
    per_iter = []

    def work(i: int) -> None:
        s, e = bounds[i]
        np.dot(alpha, mats[i].dot(x), out=y[s:e])
        y[s:e] += teleport

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in range(max_iter):
            t0 = time.perf_counter()
            list(pool.map(work, range(n_blocks)))
            delta = np.abs(y - x).sum()
            x, y = y, x
            per_iter.append(time.perf_counter() - t0)
            if delta < tol:
                break
    return x, per_iter


# ---------------------------------------------------------------- label propagation
def label_propagation(A: sparse.csr_matrix, workers: int = 1, max_iter: int = 30, seed: int = 7):
    """Asynchronous label propagation with randomised sweep order.

    workers=1 gives the serial reference. With workers>1 the row blocks are
    updated concurrently and read each other's freshly written labels, which is
    the asynchronous variant: races are inherent to the algorithm and only affect
    the tie-breaking, not correctness of convergence. One barrier per sweep.
    """
    rng = np.random.default_rng(seed)
    n = A.shape[0]
    indptr, indices, data = A.indptr, A.indices, A.data
    labels = np.arange(n)
    order = np.arange(n)
    per_iter = []
    blocks = _block_bounds(n, workers)
    changed_box = [0]

    def update(lo: int, hi: int) -> None:
        changed = 0
        for v in order[lo:hi]:
            s, e = indptr[v], indptr[v + 1]
            if e == s:
                continue
            uniq, inv = np.unique(labels[indices[s:e]], return_inverse=True)
            scores = np.bincount(inv, weights=data[s:e])
            best_idx = np.flatnonzero(scores == scores.max())
            best = uniq[best_idx[rng.integers(len(best_idx))]] if len(best_idx) > 1 else uniq[0]
            if best != labels[v]:
                labels[v] = best
                changed += 1
        changed_box[0] = changed

    for _ in range(max_iter):
        t0 = time.perf_counter()
        rng.shuffle(order)
        if workers == 1:
            update(0, n)
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(lambda b: update(*b), blocks))
        per_iter.append(time.perf_counter() - t0)
        if changed_box[0] < max(1, n * 1e-4):
            break
    _, labels = np.unique(labels, return_inverse=True)
    return labels, per_iter


# ---------------------------------------------------------------- modularity
def modularity(A: sparse.csr_matrix, labels: np.ndarray) -> float:
    m2 = A.sum()
    if m2 == 0:
        return 0.0
    deg = np.asarray(A.sum(axis=1)).ravel()
    uniq, inv = np.unique(labels, return_inverse=True)
    inside = np.zeros(len(uniq))
    vol = np.zeros(len(uniq))
    coo = A.tocoo()
    same = inv[coo.row] == inv[coo.col]
    np.add.at(inside, inv[coo.row[same]], coo.data[same])
    np.add.at(vol, inv, deg)
    inside /= m2
    vol = vol / m2
    return float(np.sum(inside - vol ** 2))


# ---------------------------------------------------------------- Louvain
def louvain_partition(A: sparse.csr_matrix, resolution: float = 1.0, seed: int = 1):
    """Louvain modularity optimisation (networkx reference implementation)."""
    import networkx as nx

    G = nx.from_scipy_sparse_array(A)
    t0 = time.perf_counter()
    comms = nx.community.louvain_communities(G, weight="weight", resolution=resolution, seed=seed)
    secs = time.perf_counter() - t0
    labels = np.zeros(A.shape[0], dtype=np.int64)
    for i, block in enumerate(comms):
        labels[list(block)] = i
    return labels, len(comms), secs


def nmi(a: np.ndarray, b: np.ndarray) -> float:
    """Normalised mutual information between two labellings (arithmetic mean)."""
    from sklearn.metrics import normalized_mutual_info_score

    return float(normalized_mutual_info_score(a, b, average_method="arithmetic"))


# ---------------------------------------------------------------- betweenness
def betweenness_sampled(A: sparse.csr_matrix, k: int = 64, seed: int = 11, workers: int = 1):
    """Brandes betweenness with k pivot sources, parallel over sources."""
    rng = np.random.default_rng(seed)
    n = A.shape[0]
    sources = rng.choice(n, size=min(k, n), replace=False)
    indptr, indices = A.indptr, A.indices

    def bfs(src: int):
        order = []
        stack = [src]
        pred: list[list[int]] = [[] for _ in range(n)]
        sigma = np.zeros(n)
        sigma[src] = 1.0
        dist = np.full(n, -1, dtype=np.int32)
        dist[src] = 0
        while stack:
            v = stack.pop()
            order.append(v)
            for w in indices[indptr[v]:indptr[v + 1]]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    stack.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = np.zeros(n)
        for v in reversed(order):
            for p in pred[v]:
                if sigma[v] > 0:
                    delta[p] += sigma[p] / sigma[v] * (1.0 + delta[v])
            if v != src:
                delta[v] += 0  # endpoints excluded
        return delta

    if workers == 1:
        total = np.zeros(n)
        for s in sources:
            total += bfs(int(s))
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            parts = list(pool.map(lambda s: bfs(int(s)), sources))
        total = np.sum(parts, axis=0)
    if k < n:
        total *= n / k
    return total / 2.0


# ---------------------------------------------------------------- main analysis
def main(top_k: int = 8, workers: int = 1) -> dict:
    nodes, index, A, _ = load_graph(top_k)
    PT = transition(A).T.tocsr()
    n = A.shape[0]

    t0 = time.perf_counter()
    pr, _ = pagerank_serial(PT)
    pr_secs = time.perf_counter() - t0

    t0 = time.perf_counter()
    labels, _ = label_propagation(A, workers=workers)
    lpa_secs = time.perf_counter() - t0

    t0 = time.perf_counter()
    bt = betweenness_sampled(A, k=64, workers=workers)
    bt_secs = time.perf_counter() - t0

    deg = np.asarray(A.sum(axis=1)).ravel()
    res = {
        "top_k": top_k,
        "nodes": int(n),
        "edges": int(A.nnz // 2),
        "pagerank_seconds": round(pr_secs, 3),
        "lpa_seconds": round(lpa_secs, 3),
        "betweenness_seconds": round(bt_secs, 3),
        "modularity_lpa": round(modularity(A, labels), 4),
        "communities": int(len(np.unique(labels))),
        "degree_pagerank_spearman": _spearman(deg, pr),
    }
    _dump_nodes(nodes, deg, pr, bt, labels, top_k)
    return res


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    denom = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / denom) if denom else 0.0


def _dump_nodes(nodes, deg, pr, bt, labels, top_k: int) -> None:
    path = os.path.join(OUT, f"nodes_scored_top{top_k}.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["nconst", "degree", "pagerank", "betweenness", "community"])
        for i, nid in enumerate(nodes):
            w.writerow([nid, int(deg[i]), f"{pr[i]:.10f}", f"{bt[i]:.6f}", int(labels[i])])


if __name__ == "__main__":
    print(json.dumps(main(top_k=int(sys.argv[1]) if len(sys.argv) > 1 else 8), indent=2))
