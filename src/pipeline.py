"""Stage S0/S1 driver: decompress, scan, filter, join, persist the Hong Kong working set."""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from multiprocessing import Pool

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import s1_scan as s1
from src.common import INTERIM, RESULTS, dump_json, human

NAMES = ["title.akas", "title.basics", "title.principals", "name.basics"]


def paths() -> dict:
    return {n: os.path.join(INTERIM, f"{n}.tsv") for n in NAMES}


def ensure_decompressed(force: bool = False) -> dict:
    stats = {}
    total = 0.0
    for name in NAMES:
        _, secs, size = s1.decompress(name, force=force)
        stats[name] = {"seconds": round(secs, 3), "bytes": size}
        total += secs
    stats["_total_seconds"] = round(total, 3)
    return stats


def run_s1(workers: int, chunk_mb: int = 8, persist: bool = False) -> dict:
    """Run the full S1 pipeline and return per-file timings and row counts.

    A single process pool serves all four scans: on Windows, spawning 16 interpreters
    costs more than parsing the two smallest files, so per-stage pools made the
    parallel version slower than the serial one for those stages.
    """
    p = paths()
    timings = {}
    pool = None
    if workers != 1:
        pool = Pool(workers)
    try:
        t0 = time.perf_counter()
        hk_ids, rec = _timed(
            lambda: s1.scan(p["title.akas"], "akas", None, workers, chunk_mb, merge="set", pool=pool)
        )
        timings["title.akas"] = rec
        timings["title.akas"]["rows_out"] = len(hk_ids)

        titles, rec = _timed(
            lambda: s1.scan(p["title.basics"], "basics", hk_ids, workers, chunk_mb, merge="list", pool=pool)
        )
        timings["title.basics"] = rec
        timings["title.basics"]["rows_out"] = len(titles)

        principals, rec = _timed(
            lambda: s1.scan(p["title.principals"], "principals", hk_ids, workers, chunk_mb, merge="list", pool=pool)
        )
        timings["title.principals"] = rec
        timings["title.principals"]["rows_out"] = len(principals)

        person_ids = {row[1] for row in principals}
        people, rec = _timed(
            lambda: s1.scan(p["name.basics"], "names", person_ids, workers, chunk_mb, merge="list", pool=pool)
        )
        timings["name.basics"] = rec
        timings["name.basics"]["rows_out"] = len(people)
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    total = time.perf_counter() - t0
    out = {
        "workers": workers,
        "chunk_mb": chunk_mb,
        "total_seconds": round(total, 3),
        "files": timings,
        "counts": {
            "hk_titles": len(hk_ids),
            "titles_kept": len(titles),
            "principal_rows": len(principals),
            "distinct_people": len(person_ids),
        },
    }

    if persist:
        _write_titles(titles)
        _write_principals(principals)
        _write_people(people)
        dump_json("s1_summary.json", out)
    return out


def _timed(fn):
    t0 = time.perf_counter()
    rows = fn()
    return rows, {"seconds": round(time.perf_counter() - t0, 3), "rows": len(rows)}


def _write_titles(rows) -> None:
    path = os.path.join(INTERIM, "hk_titles.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["tconst", "title_type", "start_year", "genres"])
        for r in rows:
            year = r[2] if r[2].isdigit() else ""
            genres = "" if r[3] == "\\N" else r[3]
            w.writerow([r[0], r[1], year, genres])


def _write_principals(rows) -> None:
    path = os.path.join(INTERIM, "hk_principals.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["tconst", "nconst", "category", "job", "ordering"])
        for r in rows:
            job = "" if r[3] == "\\N" else r[3]
            w.writerow([r[0], r[1], r[2], job, r[4]])


def _write_people(rows) -> None:
    path = os.path.join(INTERIM, "people.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["nconst", "primary_name", "birth_year", "professions"])
        for r in rows:
            birth = r[2] if r[2].isdigit() else ""
            prof = "" if r[3] == "\\N" else r[3]
            w.writerow([r[0], r[1], birth, prof])


if __name__ == "__main__":
    st = ensure_decompressed()
    for k, v in st.items():
        if not k.startswith("_"):
            print(f"gunzip {k:18s} {human(v['bytes']):>9s}  {v['seconds']:6.2f}s")
    print(f"total gunzip {st['_total_seconds']:.1f}s")
    res = run_s1(workers=os.cpu_count(), persist=True)
    print(json.dumps(res, indent=2))
