"""Shared paths, timing and memory instrumentation for the CS5488 pipeline."""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field

import psutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
INTERIM = os.path.join(ROOT, "data", "interim")
OUT = os.path.join(ROOT, "data", "out")
RESULTS = os.path.join(ROOT, "results")
FIGURES = os.path.join(ROOT, "figures")

for _d in (INTERIM, OUT, RESULTS, FIGURES):
    os.makedirs(_d, exist_ok=True)


class MemorySampler:
    """Sample the resident set size of this process and its children in a thread."""

    def __init__(self, interval: float = 0.1):
        self.interval = interval
        self.peak = 0
        self._stop = threading.Event()
        self._proc = psutil.Process(os.getpid())
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _rss(self) -> int:
        total = 0
        try:
            total += self._proc.memory_info().rss
            for child in self._proc.children(recursive=True):
                try:
                    total += child.memory_info().rss
                except psutil.Error:
                    pass
        except psutil.Error:
            pass
        return total

    def _run(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, self._rss())
            self._stop.wait(self.interval)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=2)

    @property
    def peak_mb(self) -> float:
        return self.peak / (1024 * 1024)


@dataclass
class Record:
    stage: str
    workers: int
    seconds: float
    peak_mb: float
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = {
            "stage": self.stage,
            "workers": self.workers,
            "seconds": round(self.seconds, 4),
            "peak_mb": round(self.peak_mb, 1),
        }
        d.update(self.extra)
        return d


def timed(stage: str, workers: int, fn, *args, **kwargs):
    """Run fn under a wall clock and a memory sampler; return (result, Record)."""
    with MemorySampler() as mem:
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        seconds = time.perf_counter() - t0
    return result, Record(stage=stage, workers=workers, seconds=seconds, peak_mb=mem.peak_mb)


def dump_json(name: str, payload) -> str:
    path = os.path.join(RESULTS, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return path


def append_jsonl(name: str, payload) -> str:
    path = os.path.join(RESULTS, name)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"
