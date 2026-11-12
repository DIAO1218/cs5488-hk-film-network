# Parallel Graph Analytics of the Hong Kong Release Network

CS5488 Data-Intensive Computing — group project.

The Hong Kong film market is one of the densest collaborative networks in cinema: a small pool of
performers and technicians reused across thousands of productions. This project rebuilds that
collaboration network from the full IMDb public dataset — **169.6 million rows scanned across five
files** — and analyses it with three different parallel strategies, each matched to a different
shape of workload.

The report is in [`report/`](report/); the slides are `report/Slides.pptx`.

---

## Headline results

| | |
|---|---|
| Working set | 21,033 titles · 360,502 credited roles · 127,218 people |
| Graph | **51,878 nodes · 388,168 edges**, density 2.9e-04, degree exponent γ ≈ 2.05 |
| Community structure | Louvain: **1,285 communities, Q = 0.75**, cross-seed stability NMI = 0.89 |
| Blocs recovered without labels | Cantonese core (8,379) · Hollywood (8,108) · Shaw-era (4,916) · European (4,196) · Japanese (4,179) |
| Scan tier | 109.70 s → 15.83 s = **6.93× at 16 workers** |
| Rule counting | 1.96 s → 0.43 s = **4.51×** (counting scales, candidate generation does not) |
| PageRank | **1.67×** — and 2.14× at 16× the graph size: bandwidth-bound, not synchronisation-bound |

Two findings that drive the report:

1. **The release market is not the industry.** The IMDb public dump has no country field, and
   `region = HK` in `title.akas` marks *release*, not production. Three candidate filters select
   25,997, 15,715 or 0 titles (see §4.1 of the report). We therefore analyse the Hong Kong *release*
   network and let community detection separate the cinemas — which it does, unsupervised.
2. **Three workloads, three ceilings.** A scan (no dependencies), an iterative solver (one barrier per
   iteration) and an irregular mining phase (data-dependent cost) produce 6.93×, 1.67× and 4.51× on
   the same 20-core machine. The differences are predicted by dependency structure, not by hardware.

---

## Repository layout

```
src/
  download_data.py   segmented parallel fetch of the five IMDb dumps (20 threads)
  s1_scan.py         byte-range chunk scanner — the parallel primitive of tier 1
  pipeline.py        S0/S1 driver: gunzip, filter, join, persist the working set
  s2_graph.py        cast expansion, billing truncation, edge construction
  s3_analytics.py    PageRank, Louvain, label propagation, sampled betweenness
  s4_rules.py        Apriori with sharded lock-free counting
  bench.py           experiments E1, E1b, E3, E3b, E3c, E4 and the scaling sweeps
  analyze.py         substantive analysis -> results/analysis.json
  figures.py         all 13 figures, regenerated from results/
  build_report.py    English report, numbers injected from results/
  build_report_zh.py Chinese companion version, same numbers
  make_slides.py     the 8-slide deck
report/
  Report.docx/.pdf   final report (17 pages)
  Report_zh.docx/.pdf  Chinese reading copy
  Report.md          Markdown source the reports are generated from
  latex/             LaTeX project, split by section for parallel editing
  SPEAKING.md        4-minute talk plan + anticipated Q&A
data/
  out/               derived graph artefacts (committed, ~19 MB) so the analysis can be
                     re-run without downloading 1.78 GB
figures/             all figures referenced by the report
results/             one JSON line per benchmark run; analysis.json; s1/s2 summaries
```

---

## Quick start

Only Python ≥ 3.10 and the packages in `requirements.txt` are needed.

```bash
pip install -r requirements.txt
```

**Run the analysis on the committed graph** (no download, ~3 minutes):

```bash
python src/analyze.py 8      # communities, rules, clusters -> results/analysis.json
python src/figures.py        # regenerate every figure from results/
```

**Reproduce the parallel benchmarks** (needs the raw data, see below):

```bash
python src/bench.py --exp E1     # scan tier, 5 worker counts, ~4 min
python src/bench.py --exp E4     # rule mining
python src/bench.py --exp E3     # PageRank
python src/bench.py --exp E3c    # isoefficiency: replicate the graph 1x/4x/16x
```

**Full pipeline from raw data:**

```bash
python src/download_data.py   # ~1.78 GB, 20-thread ranged download
python src/pipeline.py        # gunzip (9.2 GB) + scan + persist working set
python src/s2_graph.py        # build edges_top3 / edges_top8
python src/analyze.py 8
python src/bench.py --exp all
python src/figures.py
```

**Rebuild the documents:**

```bash
python src/build_report.py && python report/make_docx.py
python src/build_report_zh.py && python report/make_docx.py report/Report_zh.md report/Report_zh.docx
python report/md2tex.py      # LaTeX project in report/latex/
python src/make_slides.py
```

---

## Data

The five source files are the **IMDb non-commercial datasets**
(<https://developer.imdb.com/non-commercial-datasets/>), published as gzip-compressed TSV and
refreshed daily.

| File | Compressed | Rows |
|---|---|---|
| `title.principals` | 754 MB | 90.3 M |
| `title.akas` | 498 MB | 51.3 M |
| `name.basics` | 298 MB | 14.6 M |
| `title.basics` | 220 MB | 11.0 M |
| `title.ratings` | 8.3 MB | 1.5 M |

They are **not committed to this repository**, for two reasons: a single file exceeds GitHub's
100 MB limit, and the IMDb licence permits non-commercial *use*, not redistribution.
`src/download_data.py` fetches them into `data/raw/` (ignored by git), after which every number in
the report is reproducible.

Row counts drift because the release is refreshed daily; they are recorded at download time in
`results/s1_summary.json`.

---

## Method notes worth knowing before reading the code

- **gzip is serial by construction.** It offers no random access, so the 1.78 GB of input is
  decompressed once by a single process (33.8 s) before any parallelism is possible. That stage is
  timed and reported separately rather than hidden inside a stage boundary.
- **One process pool for the whole pipeline.** The first version created a pool per stage; on Windows
  the spawn cost made the 16-worker run *slower* than the 4-worker one (63 s vs 42 s). Reusing a
  single pool and spilling the read-only reference set to disk fixed it — 6.93× instead of 2.62×.
- **Page cache is warmed before timing.** Otherwise the single-worker baseline alone pays the cold
  read and the speedup is inflated by roughly 35%.
- **Peak RSS is sampled per run**, because parallelism trades memory for time and that trade-off
  belongs in the results.

---

## 中文说明

本仓库是 CS5488 小组项目的完整源码与产物。

- 报告：`report/Report.docx`（英文正式版，17 页）；`report/Report_zh.docx`（中文对照版，章节与图号一一对应）
- 演示：`report/Slides.pptx`（8 页，含演讲者备注）；讲稿与问答：`report/SPEAKING.md`
- LaTeX 版：`report/latex/`，按章节拆分，可用 Overleaf 直接打开；打包版 `report/Report_LaTeX.zip`
- **数据未上传**：IMDb 原始数据 1.78 GB，超过 GitHub 单文件限制，且其许可不允许再分发。跑
  `python src/download_data.py` 即可下载；只想看分析结果的话，`data/out/` 里已提交派生图，
  直接跑 `src/analyze.py` 即可复现社区、规则与图表。

---

## Licence and academic use

Coursework produced for CS5488 (Data-Intensive Computing). Source code is provided for reference;
the IMDb data remains under IMDb's non-commercial terms and is not included here.
