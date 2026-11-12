"""Stage S4: association rule mining over per-film baskets.

Each film becomes a basket of items:
  G:<genre>            one per genre label
  C:<crew category>    one per crew category present in the credits

Itemsets are represented as Python ints used as bitsets, so subset tests are a
single bitwise AND. Candidate generation is the irregular phase (cost depends on
how many transactions contain a candidate); counting is regular and is sharded
across worker processes with no locking, each merging a local Counter at the end.
"""
from __future__ import annotations

import csv
import itertools
import json
import os
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common import INTERIM, OUT

TAG = "S4"


def item_name(tag: str, value: str) -> str:
    return f"{tag}:{value}"


def build_baskets() -> tuple[list[int], list[str]]:
    """Return (transactions as bitmasks, item vocabulary)."""
    vocab: dict[str, int] = {}
    baskets: dict[str, set[int]] = defaultdict(set)

    with open(os.path.join(INTERIM, "hk_titles.csv"), newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            for g in row["genres"].split(","):
                if g:
                    vocab.setdefault(item_name("G", g), len(vocab))
                    baskets[row["tconst"]].add(vocab[item_name("G", g)])

    with open(os.path.join(INTERIM, "hk_principals.csv"), newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cat = row["category"]
            if cat in ("actor", "actress", "self", "archive_footage", "archive_sound"):
                continue
            key = item_name("C", cat)
            vocab.setdefault(key, len(vocab))
            baskets[row["tconst"]].add(vocab[key])

    tx = []
    for _, items in baskets.items():
        if len(items) < 2:
            continue
        mask = 0
        for i in items:
            mask |= 1 << i
        tx.append(mask)
    inv = {v: k for k, v in vocab.items()}
    names = [inv[i] for i in range(len(inv))]
    return tx, names


def _bits(mask: int) -> list[int]:
    out = []
    i = 0
    while mask:
        if mask & 1:
            out.append(i)
        mask >>= 1
        i += 1
    return out


_TX: list[int] = []


def _init_tx(tx: list[int]) -> None:
    global _TX
    _TX = tx


def _count_task(task) -> dict:
    bounds, cands, sizes = task
    return _count_shard(bounds, cands, sizes)


def _count_shard(bounds: tuple[int, int], cands: set[int], sizes: tuple[int, ...]) -> dict:
    lo, hi = bounds
    local: dict[int, int] = defaultdict(int)
    tx = _TX
    for i in range(lo, hi):
        m = tx[i]
        for size in sizes:
            for combo in itertools.combinations(_items_of(m), size):
                mask = 0
                for c in combo:
                    mask |= 1 << c
                if mask in cands:
                    local[mask] += 1
    return dict(local)


def _items_of(mask: int) -> list[int]:
    return _bits(mask)


def candidate_gen(prev: set[int], k: int) -> set[int]:
    """Apriori join + prune against the previous level's frequent set."""
    items = sorted(prev)
    out: set[int] = set()
    for a, b in itertools.combinations(items, 2):
        if (a | b).bit_count() != k:
            continue
        cand = a | b
        ok = True
        for sub in itertools.combinations(_bits(cand), k - 1):
            sm = 0
            for s in sub:
                sm |= 1 << s
            if sm not in prev:
                ok = False
                break
        if ok:
            out.add(cand)
    return out


def mine(tx: list[int], min_support: float, workers: int = 1, max_k: int = 4) -> dict:
    global _TX
    _TX = tx
    n = len(tx)
    thresh = max(1, int(min_support * n))
    t_cand = 0.0
    t_count = 0.0

    # level 1
    t0 = time.perf_counter()
    counts: Counter = Counter()
    for m in tx:
        for i in _bits(m):
            counts[1 << i] += 1
    t_count += time.perf_counter() - t0

    freq = {m for m, c in counts.items() if c >= thresh}
    support = {m: counts[m] for m in freq}
    all_levels = [len(freq)]

    pool = None
    if workers != 1:
        _TX = tx
        pool = Pool(workers, initializer=_init_tx, initargs=(tx,))

    try:
        for k in range(2, max_k + 1):
            t0 = time.perf_counter()
            cands = candidate_gen(freq, k)
            t_cand += time.perf_counter() - t0
            if not cands:
                break

            t0 = time.perf_counter()
            sizes = (k,)
            if workers == 1:
                got = _count_shard((0, n), cands, sizes)
            else:
                step = max(1, len(tx) // (workers * 8))
                shards = [(s0, min(s0 + step, n)) for s0 in range(0, n, step)]
                tasks = [(b, cands, sizes) for b in shards]
                tallies: Counter = Counter()
                for part in pool.imap_unordered(_count_task, tasks, chunksize=1):
                    tallies.update(part)
                got = dict(tallies)
            t_count += time.perf_counter() - t0

            freq = {m for m, c in got.items() if c >= thresh}
            support.update({m: got[m] for m in freq})
            all_levels.append(len(freq))
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    return {
        "workers": workers,
        "min_support": min_support,
        "transactions": n,
        "candidate_gen_seconds": round(t_cand, 3),
        "counting_seconds": round(t_count, 3),
        "total_seconds": round(t_cand + t_count, 3),
        "level_sizes": all_levels,
        "itemsets": support,
    }


def rules_from_itemsets(support: dict, n_tx: int, names: list[str], min_conf: float = 0.6, min_lift: float = 1.2):
    out = []
    for mask, sup in support.items():
        bits = _bits(mask)
        if len(bits) < 2:
            continue
        for r in range(1, len(bits)):
            for ant in itertools.combinations(bits, r):
                amask = 0
                for a in ant:
                    amask |= 1 << a
                cons = mask & ~amask
                if cons == 0:
                    continue
                a_sup = support.get(amask)
                c_sup = support.get(cons)
                if not a_sup or not c_sup:
                    continue
                conf = sup / a_sup
                lift = conf / (c_sup / n_tx)
                if conf >= min_conf and lift >= min_lift:
                    out.append(
                        {
                            "antecedent": " + ".join(names[b] for b in ant),
                            "consequent": " + ".join(names[b] for b in _bits(cons)),
                            "support": sup / n_tx,
                            "confidence": conf,
                            "lift": lift,
                        }
                    )
    out.sort(key=lambda r: (-r["lift"], -r["support"]))
    return out


if __name__ == "__main__":
    tx, names = build_baskets()
    print(f"baskets={len(tx)} items={len(names)}")
    print(names)
    res = mine(tx, 0.02, workers=1, max_k=3)
    print(json.dumps({k: v for k, v in res.items() if k != "itemsets"}, indent=2))
    rl = rules_from_itemsets(res["itemsets"], res["transactions"], names)
    print(f"rules={len(rl)}")
    for r in rl[:10]:
        print(f"  {r['antecedent']} -> {r['consequent']}  sup={r['support']:.3f} conf={r['confidence']:.2f} lift={r['lift']:.2f}")
