"""Benchmark harness: E1-E4 plus the cross-cutting scaling study.

Every experiment runs the serial reference and the parallel version over the same
data, so S(p) = T(1)/T(p) compares identical work. Peak RSS is sampled per run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import s1_scan as s1
from src import s2_graph, s3_analytics as s3, s4_rules as s4
from src.common import INTERIM, RESULTS, MemorySampler, append_jsonl, dump_json
from src.pipeline import run_s1

WORKERS = [1, 2, 4, 8, 16]


def _warm_page_cache() -> None:
    """Read the uncompressed dumps once so every configuration sees the same I/O state.

    Without this the single-worker baseline runs first and pays the cold-cache penalty
    while every parallel run behind it reads from RAM, which inflates the speedup by
    about 35% on this machine.
    """
    from src.pipeline import paths

    total = 0
    for name, path in paths().items():
        if not os.path.exists(path):
            continue
        with open(path, "rb") as fh:
            while True:
                block = fh.read(1 << 24)
                if not block:
                    break
                total += len(block)
    print(f"  warmed {total / 1e9:.1f} GB of page cache", flush=True)


def e1_scan(workers=WORKERS):
    print("== E1 scan/filter/join ==", flush=True)
    _warm_page_cache()
    rows = []
    for p in workers:
        with MemorySampler() as mem:
            res = run_s1(workers=p, chunk_mb=8, persist=False)
        rec = {
            "experiment": "E1",
            "workers": p,
            "seconds": res["total_seconds"],
            "peak_mb": round(mem.peak_mb, 1),
            "per_file": {k: v["seconds"] for k, v in res["files"].items()},
            "counts": res["counts"],
        }
        rows.append(rec)
        append_jsonl("bench_e1.jsonl", rec)
        print(f"  p={p:2d}  {res['total_seconds']:7.2f}s  titles={res['counts']['titles_kept']}", flush=True)
    _summarise(rows, "E1")
    return rows


def e1b_chunk_sweep(workers=16, sizes=(1, 2, 4, 8, 16, 32, 64, 128)):
    print("== E1b chunk sweep ==", flush=True)
    path = os.path.join(INTERIM, "title.principals.tsv")
    hk = s1.scan(os.path.join(INTERIM, "title.akas.tsv"), "akas", None, workers, 8, merge="set")
    rows = []
    for mb in sizes:
        rec_ref, timing = None, None
        t0 = time.perf_counter()
        out = s1.scan(path, "principals", hk, workers, mb, merge="list")
        secs = time.perf_counter() - t0
        rec = {"experiment": "E1b", "workers": workers, "chunk_mb": mb, "seconds": round(secs, 3), "rows": len(out)}
        rows.append(rec)
        append_jsonl("bench_e1b.jsonl", rec)
        print(f"  chunk={mb:4d}MB  {secs:7.2f}s  rows={len(out)}", flush=True)
    return rows


def e3_pagerank(top_k=8, workers=WORKERS):
    print("== E3 PageRank ==", flush=True)
    nodes, index, A, _ = s3.load_graph(top_k)
    PT = s3.transition(A).T.tocsr()
    n = A.shape[0]
    print(f"  graph n={n} m={A.nnz // 2}", flush=True)

    base, per_iter = s3.pagerank_serial(PT)
    base_secs = float(np.sum(per_iter[1:]))  # exclude first iteration (allocation warm-up)
    rows = [{
        "experiment": "E3",
        "workers": 1,
        "seconds": round(base_secs, 4),
        "iters": len(per_iter) - 1,
    }]
    append_jsonl("bench_e3.jsonl", rows[0])
    print(f"  p= 1  {base_secs:7.3f}s  iters={len(per_iter) - 1}", flush=True)

    for p in workers[1:]:
        vec, per = s3.pagerank_blocked(PT, p)
        secs = float(np.sum(per[1:]))
        rec = {
            "experiment": "E3",
            "workers": p,
            "seconds": round(secs, 4),
            "iters": len(per) - 1,
            "max_abs_diff": float(np.max(np.abs(vec - base))),
        }
        rows.append(rec)
        append_jsonl("bench_e3.jsonl", rec)
        print(f"  p={p:2d}  {secs:7.3f}s  diff={rec['max_abs_diff']:.2e}", flush=True)
    _summarise(rows, "E3")
    return rows


def e3b_block_sweep(top_k=8, workers=8, blocks=(4, 8, 16, 32, 64)):
    print("== E3b block sweep ==", flush=True)
    nodes, index, A, _ = s3.load_graph(top_k)
    PT = s3.transition(A).T.tocsr()
    rows = []
    for b in blocks:
        vec, per = s3.pagerank_blocked(PT, workers, blocks=b)
        secs = float(np.sum(per[1:]))
        rec = {"experiment": "E3b", "workers": workers, "blocks": b, "seconds": round(secs, 4), "iters": len(per) - 1}
        rows.append(rec)
        append_jsonl("bench_e3b.jsonl", rec)
        print(f"  blocks={b:3d}  {secs:7.3f}s", flush=True)
    return rows


def e3c_isoefficiency(top_k=8, replicas=(1, 4, 16), threads=8):
    """Grow the graph by disjoint replication and watch PageRank speedup improve.

    At one replica the graph is 4.8e5 edges and an iteration costs about a
    millisecond, which is below thread dispatch overhead. Scaling the same algorithm
    to 7.7e6 edges answers the question the E3 curve raises: is PageRank inherently
    unsuitable for parallelism, or merely too small here to show any?
    """
    from scipy import sparse as sp

    print("== E3c isoefficiency ==", flush=True)
    nodes, index, A, _ = s3.load_graph(top_k)
    I = sp.identity(A.shape[0], format="csr")
    rows = []
    for r in replicas:
        big = sp.kron(sp.identity(r, format="csr"), A, format="csr") if r > 1 else A
        PT = s3.transition(big).T.tocsr()
        t0 = time.perf_counter()
        _, per1 = s3.pagerank_serial(PT, max_iter=30, tol=1e-12)
        t1 = float(np.sum(per1[1:]))
        _, perp = s3.pagerank_blocked(PT, threads, max_iter=30, tol=1e-12)
        tp = float(np.sum(perp[1:]))
        rec = {
            "experiment": "E3c",
            "replica": r,
            "nodes": int(big.shape[0]),
            "edges": int(big.nnz // 2),
            "serial": round(t1, 4),
            "parallel": round(tp, 4),
            "speedup": round(t1 / tp, 3),
        }
        rows.append(rec)
        append_jsonl("bench_e3c.jsonl", rec)
        print(f"  replica={r:2d} m={rec['edges']:9,d}  serial={t1:6.3f}s  p{threads}={tp:6.3f}s  S={rec['speedup']:.2f}x", flush=True)
    return rows


def e4_rules(workers=WORKERS, min_support=0.01, max_k=4):
    print("== E4 association rules ==", flush=True)
    tx, names = s4.build_baskets()
    print(f"  baskets={len(tx)} items={len(names)}", flush=True)
    rows = []
    for p in workers:
        with MemorySampler() as mem:
            res = s4.mine(tx, min_support, workers=p, max_k=max_k)
        rec = {
            "experiment": "E4",
            "workers": p,
            "seconds": res["total_seconds"],
            "candidate_gen_seconds": res["candidate_gen_seconds"],
            "counting_seconds": res["counting_seconds"],
            "level_sizes": res["level_sizes"],
            "peak_mb": round(mem.peak_mb, 1),
        }
        rows.append(rec)
        append_jsonl("bench_e4.jsonl", rec)
        print(
            f"  p={p:2d}  total={res['total_seconds']:7.2f}s  "
            f"cand={res['candidate_gen_seconds']:6.2f}  count={res['counting_seconds']:7.2f}",
            flush=True,
        )
    _summarise(rows, "E4")
    return rows


def _summarise(rows, name):
    if not rows:
        return
    t1 = rows[0]["seconds"]
    print(f"  -- {name} speedup:", end=" ")
    for r in rows:
        print(f"p{r['workers']}={t1 / r['seconds']:.2f}x", end=" ")
    print(flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True, choices=["E1", "E1b", "E3", "E3b", "E3c", "E4", "all"])
    ap.add_argument("--topk", type=int, default=8)
    args = ap.parse_args()

    if args.exp in ("E1", "all"):
        e1_scan()
    if args.exp in ("E1b", "all"):
        e1b_chunk_sweep()
    if args.exp in ("E3", "all"):
        e3_pagerank(top_k=args.topk)
    if args.exp in ("E3b", "all"):
        e3b_block_sweep(top_k=args.topk)
    if args.exp in ("E3c", "all"):
        e3c_isoefficiency(top_k=args.topk)
    if args.exp in ("E4", "all"):
        e4_rules()
