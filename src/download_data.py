"""Segmented parallel downloader for the IMDb dumps (single-connection throughput is throttled)."""
from __future__ import annotations

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = "https://datasets.imdbws.com/{name}.tsv.gz"
RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
FILES = ["title.ratings", "title.basics", "name.basics", "title.akas", "title.principals"]
PART = 3 * 1024 * 1024
THREADS = 20

_lock = threading.Lock()
_done = [0]


def head_size(url: str) -> int:
    r = requests.head(url, timeout=30, allow_redirects=True)
    r.raise_for_status()
    return int(r.headers["Content-Length"])


def fetch_part(url: str, dst: str, start: int, end: int, attempts: int = 4) -> None:
    last = None
    for _ in range(attempts):
        try:
            headers = {"Range": f"bytes={start}-{end - 1}"}
            with requests.get(url, headers=headers, timeout=120, stream=True) as r:
                r.raise_for_status()
                buf = r.content
            if len(buf) != end - start:
                raise IOError(f"short read {len(buf)} != {end - start}")
            with open(dst, "r+b") as fh:
                fh.seek(start)
                fh.write(buf)
            with _lock:
                _done[0] += len(buf)
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5)
    raise RuntimeError(f"part {start}-{end} failed: {last}")


def download(name: str) -> tuple[str, int, float]:
    url = BASE.format(name=name)
    dst = os.path.join(RAW, f"{name}.tsv.gz")
    size = head_size(url)
    if os.path.exists(dst) and os.path.getsize(dst) == size:
        return dst, size, 0.0
    t0 = time.perf_counter()
    with open(dst, "wb") as fh:
        fh.truncate(size)
    spans = [(s, min(s + PART, size)) for s in range(0, size, PART)]
    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        list(pool.map(lambda sp: fetch_part(url, dst, sp[0], sp[1]), spans))
    got = os.path.getsize(dst)
    if got != size:
        raise RuntimeError(f"{name}: size mismatch {got} != {size}")
    return dst, size, time.perf_counter() - t0


if __name__ == "__main__":
    for nm in FILES:
        p, sz, secs = download(nm)
        rate = sz / secs / 1024 if secs else 0
        print(f"{nm:18s} {sz/1048576:7.1f} MB  {secs:6.1f}s  {rate:7.0f} KB/s", flush=True)
