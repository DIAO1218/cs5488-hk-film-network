"""Stage S0/S1: chunk-parallel scan, filter and join over the IMDb TSV dumps.

Design notes
------------
gzip is not randomly accessible, so decompression is performed once, serially,
and reported as its own stage. What is parallelised is the parse-and-filter pass
over the *uncompressed* stream: the file is split into byte ranges aligned to
newline boundaries, each worker parses its own range with no shared state, and
partial results are merged by the parent. The single-worker path walks the same
chunk list sequentially, so the speedup measurement compares identical work.
"""
from __future__ import annotations

import gzip
import os
import pickle
import shutil
import sys
import time
import zlib
from multiprocessing import Pool

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common import RAW, INTERIM, MemorySampler, human

HEADER_TOKENS = {b"tconst", b"titleId", b"nconst"}

# A Hong Kong *release* is not a Hong Kong *production*: a Hollywood film with an
# English alias registered under region HK would otherwise enter the working set
# (verified by hand - the first region-only run pulled De Niro and Hanks into the
# largest co-star community). Requiring a Cantonese/Mandarin alias under region HK
# removes those rows: en-only HK aliases are foreign releases, yue/cmn/zh aliases
# are Chinese-language originals.
HK_LANGUAGES = {"yue", "cmn", "zh"}

# field positions per file kind
SCHEMA = {
    "basics": dict(id=0, type=1, title=2, orig=3, year=5, runtime=7, genres=8),
    "akas": dict(id=0, region=3, language=4, is_original=7),
    "principals": dict(id=0, ordering=1, person=2, category=3, job=4),
    "names": dict(id=0, name=1, birth=2, profession=4),
}

# Worker-side cache of the read-only reference set. Keeping it in the worker and
# loading it once per process lets a single pool serve every stage of the pipeline,
# which matters because process start-up on Windows costs more than parsing a
# small file does.
_REFS: dict[str, object] = {}


def decompress(name: str, force: bool = False) -> tuple[str, float, int]:
    """gunzip <name>.tsv.gz into data/interim/<name>.tsv. Returns (path, seconds, size)."""
    src = os.path.join(RAW, f"{name}.tsv.gz")
    dst = os.path.join(INTERIM, f"{name}.tsv")
    if os.path.exists(dst) and not force and os.path.getsize(dst) > 0:
        return dst, 0.0, os.path.getsize(dst)
    t0 = time.perf_counter()
    tmp = dst + ".part"
    with gzip.open(src, "rb") as fin, open(tmp, "wb") as fout:
        shutil.copyfileobj(fin, fout)
    os.replace(tmp, dst)
    return dst, time.perf_counter() - t0, os.path.getsize(dst)


def byte_ranges(path: str, n_chunks: int) -> list[tuple[int, int]]:
    """Split a text file into n byte ranges that start and end on newline boundaries."""
    size = os.path.getsize(path)
    if n_chunks <= 1:
        return [(0, size)]
    step = size // n_chunks
    ranges: list[tuple[int, int]] = []
    with open(path, "rb") as fh:
        start = 0
        for i in range(n_chunks):
            if i == n_chunks - 1:
                ranges.append((start, size))
                break
            end = start + step
            fh.seek(end)
            fh.readline()
            end = fh.tell()
            ranges.append((start, end))
            start = end
    return [r for r in ranges if r[1] > r[0]]


def _has_cjk(text: str) -> bool:
    """True if the string contains a CJK ideograph (used as the production filter)."""
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return True
    return False


def _init(path: str, kind: str, refs) -> None:
    _REFS["__inline__"] = (path, kind, refs)


def _refs_for(key: str):
    got = _REFS.get(key)
    if got is None:
        with open(key, "rb") as fh:
            got = pickle.load(fh)
        _REFS[key] = got
    return got


def _parse_task(task) -> list:
    path, kind, refs_key, start, end = task
    return _parse_chunk((start, end), path, kind, _refs_for(refs_key))


def _parse_chunk(rng: tuple[int, int], path: str, kind: str, refs):
    sc = SCHEMA[kind]
    start, end = rng
    with open(path, "rb") as fh:
        fh.seek(start)
        blob = fh.read(end - start)
    out = []
    for line in blob.split(b"\n"):
        if not line:
            continue
        if line[:6] in HEADER_TOKENS:
            continue
        f = line.decode("utf-8", "replace").split("\t")
        if len(f) < 3:
            continue
        if kind == "akas":
            if f[sc["region"]] == "HK":
                out.append(f[sc["id"]])
        elif kind == "basics":
            tid = f[sc["id"]]
            if tid not in refs:
                continue
            ttype = f[sc["type"]]
            if ttype not in ("movie", "tvMovie", "short"):
                continue
            out.append((tid, ttype, f[sc["year"]], f[sc["genres"]]))
        elif kind == "principals":
            tid = f[sc["id"]]
            if tid not in refs:
                continue
            out.append((tid, f[sc["person"]], f[sc["category"]], f[sc["job"]], f[sc["ordering"]]))
        elif kind == "names":
            nid = f[sc["id"]]
            if nid not in refs:
                continue
            out.append((nid, f[sc["name"]], f[sc["birth"]], f[sc["profession"]]))
    return out


def scan(path: str, kind: str, refs, workers: int, chunk_mb: int = 8, merge: str = "list", pool=None):
    """Scan path with `workers` processes. workers=1 runs the same chunks sequentially.

    If an existing `pool` is supplied it is reused, so a pipeline of four scans pays
    process start-up once instead of four times. The reference set is spilled to disk
    and loaded once per worker, because it is far cheaper to read a 0.5 MB pickle
    than to ship it with every one of the several hundred chunk tasks.
    """
    size = os.path.getsize(path)
    chunk_bytes = max(1, chunk_mb) * 1024 * 1024
    n_chunks = max(1, min(4096, -(-size // chunk_bytes)))
    ranges = byte_ranges(path, n_chunks)

    if workers == 1:
        parts = [_parse_chunk(r, path, kind, refs) for r in ranges]
    else:
        key = os.path.join(os.path.dirname(path), f"_refs_{kind}.pkl")
        with open(key, "wb") as fh:
            pickle.dump(refs, fh)
        tasks = [(path, kind, key, s0, e0) for s0, e0 in ranges]
        if pool is None:
            with Pool(workers) as own:
                parts = list(own.imap_unordered(_parse_task, tasks, chunksize=1))
        else:
            parts = list(pool.imap_unordered(_parse_task, tasks, chunksize=1))

    if merge == "set":
        acc = set()
        for p in parts:
            acc.update(p)
        return acc
    acc = []
    for p in parts:
        acc.extend(p)
    return acc


def report_rows(path: str) -> int:
    """Count newlines cheaply (single pass, used for the data source table)."""
    n = 0
    with open(path, "rb") as fh:
        while True:
            block = fh.read(1 << 24)
            if not block:
                break
            n += block.count(b"\n")
    return n


if __name__ == "__main__":
    for name in ("title.akas", "title.basics", "title.principals", "name.basics", "title.ratings"):
        p, secs, size = decompress(name)
        print(f"{name}: {human(size)} uncompressed, gunzip {secs:.1f}s -> {p}")
