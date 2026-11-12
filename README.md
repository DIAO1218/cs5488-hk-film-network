# 香港发行网络的并行图分析

> Parallel Graph Analytics of the Hong Kong Release Network
> CS5488 Data-Intensive Computing · 小组项目

香港电影市场是全球联系最紧密的合作网络之一：一小群演员与技术人员，被数千部作品反复使用。
本项目用 IMDb 公开全量数据重建这张网络——**扫描 1.696 亿行、五个源文件**——并用三种不同的
并行策略分析它，每种策略对应一种形态完全不同的负载。

报告在 [`report/`](report/)，演示文稿是 `report/Slides.pptx`。

---

## 主要结果

| 项目 | 数值 |
|---|---|
| 工作集 | 21,033 部影片 · 360,502 条署名 · 127,218 人 |
| 网络规模 | **51,878 节点 · 388,168 条边**，密度 2.9e-04，度分布指数 γ ≈ 2.05 |
| 社区结构 | Louvain：**1,285 个社区，Q = 0.75**，跨随机种子稳定性 NMI = 0.89 |
| 无标签分离出的板块 | 粤语核心 8,379 · 好莱坞 8,108 · 邵氏 4,916 · 欧洲 4,196 · 日本 4,179 |
| 扫描层 | 109.70 s → 15.83 s，16 进程 **6.93×** |
| 规则计数 | 1.96 s → 0.43 s，**4.51×**（计数能扩展，候选生成不能） |
| PageRank | **1.67×**；图放大 16 倍后仍只有 2.14×——瓶颈是内存带宽，不是同步开销 |

## 两个关键发现

**一、"发行市场"不等于"电影工业"。** IMDb 公开数据里没有出品国字段，`title.akas` 的
`region = HK` 标记的是**发行地**而非出品地。文中测试的三种筛法分别选出 25,997 / 15,715 / 0 部
（见报告 §4.1）。因此本项目分析的是香港**发行**网络，并让社区发现算法自己去分离各国电影——
它确实做到了，而且是无监督的。

**二、三种负载，三个天花板。** 扫描（无依赖）、迭代求解器（每轮一次同步）、不规整的挖掘阶段
（代价依赖数据），在同一台 20 核机器上分别给出 6.93×、1.67×、4.51×。这些差异由**依赖结构**
而非硬件决定，而且在测量之前就能推出来。

---

## 目录结构

```
src/
  download_data.py   分段并行下载五个 IMDb 数据包（20 线程 Range）
  s1_scan.py         字节区间切块扫描器——第 1 层的并行原语
  pipeline.py        S0/S1 驱动：解压、过滤、连接、落盘工作集
  s2_graph.py        演员展开、番位截断、边构建
  s3_analytics.py    PageRank、Louvain、标签传播、抽样介数
  s4_rules.py        带分片无锁计数的 Apriori
  bench.py           实验 E1、E1b、E3、E3b、E3c、E4 与扩展性扫描
  analyze.py         实质分析 → results/analysis.json
  figures.py         全部 13 张图，从 results/ 重新生成
  build_report.py    英文报告，数字从 results/ 注入
  build_report_zh.py 中文对照版，同一批数字
  make_slides.py     8 页演示文稿
report/
  Report.docx/.pdf        正式报告（17 页）
  Report_zh.docx/.pdf     中文对照版
  Report.md               报告源文件（上面两份都由它生成）
  latex/                  LaTeX 工程，按章节拆分便于并行编辑
  SPEAKING.md             4 分钟讲稿与问答预案
data/
  out/               派生图产物（已提交，约 19 MB），无需下载 1.78 GB 也能复现分析
figures/             报告引用的全部图表
results/             每次基准运行一行 JSON；analysis.json；s1/s2 汇总
```

---

## 快速开始

只需要 Python ≥ 3.10 与 `requirements.txt` 里的依赖。

```bash
pip install -r requirements.txt
```

**只跑分析（不用下载数据，约 3 分钟）** —— 用已提交的派生图：

```bash
python src/analyze.py 8      # 社区、规则、聚类 → results/analysis.json
python src/figures.py        # 从 results/ 重新生成全部图表
```

**复现并行基准实验**（需要原始数据，见下节）：

```bash
python src/bench.py --exp E1     # 扫描层，5 种进程数，约 4 分钟
python src/bench.py --exp E4     # 关联规则
python src/bench.py --exp E3     # PageRank
python src/bench.py --exp E3c    # 等效率实验：把图复制 1×/4×/16×
```

**从原始数据跑完整流程**：

```bash
python src/download_data.py   # 约 1.78 GB，20 线程分段下载
python src/pipeline.py        # 解压（9.2 GB）+ 扫描 + 落盘工作集
python src/s2_graph.py        # 生成 edges_top3 / edges_top8
python src/analyze.py 8
python src/bench.py --exp all
python src/figures.py
```

**重新生成文档**：

```bash
python src/build_report.py && python report/make_docx.py
python src/build_report_zh.py && python report/make_docx.py report/Report_zh.md report/Report_zh.docx
python report/md2tex.py      # 在 report/latex/ 生成 LaTeX 工程
python src/make_slides.py
```

---

## 数据说明

五个源文件是 IMDb 的 **non-commercial datasets**（<https://developer.imdb.com/non-commercial-datasets/>），
以 gzip 压缩的 TSV 发布，每日更新。

| 文件 | 压缩后 | 行数 |
|---|---|---|
| `title.principals` | 754 MB | 9030 万 |
| `title.akas` | 498 MB | 5130 万 |
| `name.basics` | 298 MB | 1460 万 |
| `title.basics` | 220 MB | 1190 万 |
| `title.ratings` | 8.3 MB | 150 万 |

**这些文件没有提交到仓库**，三条理由任一条都成立：单个文件超过 GitHub 的 100 MB 上限；
压缩 1.78 GB、解压 9.2 GB，远超仓库合理体积；IMDb 的许可允许非商业**使用**，但**不允许再分发**。

`src/download_data.py` 会把它们下载到 `data/raw/`（已被 git 忽略），之后报告中每个数字都可复现。
由于发行版每日刷新，行数会漂移，下载当天的数值记录在 `results/s1_summary.json` 中。

---

## 几个读代码前值得知道的设计取舍

- **gzip 天然串行。** 它不提供随机访问，所以 1.78 GB 输入必须先由一个进程解压（33.8 秒）才谈得上并行。
  这一段单独计时并如实报告，而不是藏在某个阶段的边界里。
- **整条管线共用一个进程池。** 第一版每个阶段新建一个池，结果在 Windows 上 16 进程比 4 进程**更慢**
  （63 s 对 42 s）——启动开销把两个小文件吃光了。改成全程复用 + 把只读参照集落盘让每个 worker 只加载
  一次之后，同一测量从 2.62× 变为 6.93×。
- **计时前会预热页缓存。** 否则单进程基线独自承担冷读代价，加速比会虚高约 35%。
- **每次运行都采样峰值内存**，因为并行是用内存换时间，这个代价应当出现在结果里。

---

## 环境

Windows 11 · 20 逻辑核 · 34 GB 内存 · Python 3.13。
依赖见 `requirements.txt`：numpy、scipy、matplotlib、networkx、scikit-learn、psutil、requests、
python-docx、python-pptx。

> 注：本项目**没有用 pandas**。数据准备阶段 pandas 的二进制扩展在本机被系统策略拦截，
> 因此全部表格处理改用 numpy + 标准库 csv 完成——对这类"按行解析"的负载反而更直接。

---

## 许可与用途

CS5488（Data-Intensive Computing）课程作业。源码供参考；IMDb 数据仍归 IMDb 的非商业条款约束，
未包含在本仓库中。
