# LaTeX 版报告（小组协作）

这份是 `report/Report.docx` 的 LaTeX 版本，**按章节拆成了独立文件**，四个人可以各改各的，不会互相覆盖。

## 目录结构

```
latex/
├── main.tex                 主文件：导言区、封面、目录、\input 各章（一般不用动）
├── sections/
│   ├── 01_abstract.tex      摘要
│   ├── 02_introduction.tex  引言（背景/目标/数据来源）
│   ├── 03_methodology.tex   方法（管线/并行策略/分析方法/评测协议）
│   ├── 04_results_and_analysis.tex  结果（数据、网络、板块、规则、聚类、性能）
│   ├── 05_discussion.tex    讨论（三层对比、实现缺陷、瓶颈、有效性威胁）
│   ├── 06_conclusion_and_future_work.tex  结论与未来工作
│   ├── 07_individual_contribution_statement.tex  个人贡献
│   ├── 08_references.tex    参考文献
│   └── 09_appendix_a_reproducibility.tex    附录
└── figures/                 13 张图（与 Word 版完全相同，改图请重跑 src/figures.py）
```

## 建议分工

| 成员 | 负责文件 |
|---|---|
| A 数据与管线 | `02_introduction.tex`、`03_methodology.tex` 前半 |
| B 图算法 | `04_results_and_analysis.tex` 的 4.2–4.3 节 |
| C 规则与聚类 | `04_results_and_analysis.tex` 的 4.4–4.5 节 |
| D 统筹 | `01_abstract.tex`、`05`、`06`、`07`、`08`，以及 `main.tex` |

改之前先说清楚谁在改哪个文件——这是拆文件的唯一意义。

## 三种用法律

**1. Overleaf（推荐，零安装）**

1. 打开 [overleaf.com](https://www.overleaf.com) → New Project → Upload Project
2. 上传本目录的 `Report_LaTeX.zip`
3. 编译器保持默认 **pdfLaTeX**，直接 Recompile

多人实时协作、历史版本回溯都在 Overleaf 里，不需要 Git。

**2. 本地编译（本机已装 MiKTeX）**

```bash
cd report/latex
pdflatex main.tex && pdflatex main.tex && pdflatex main.tex
```

要跑三遍：第一遍生成 `.aux`，第二遍填目录和交叉引用，第三遍才稳定。也可以装 `latexmk` 后一条命令 `latexmk -pdf main.tex`。

**3. 只想读**

直接看 `main.pdf`（21 页，已编译好）。

## 改内容时的三条规矩

1. **不要手工编号。** 章节、图、表、公式的编号都是 LaTeX 自动生成的。写 `\section{Methodology}`，不要写 `\section{3. Methodology}`。
2. **数字从结果来。** 正文里的数字是 `src/build_report.py` 从 `results/*.jsonl` 生成的。如果重跑了实验，改 `report/Report.md` 对应文字后重跑 `python src/md2tex.py`，而不是在 `.tex` 里手改——否则 Word 版和 LaTeX 版会不一致。
3. **图不要单独改。** `figures/` 里的 PNG 由 `src/figures.py` 生成。要改样式就改脚本重跑，别在目录里直接替换图片，否则下次重跑会被覆盖。

## 已知的取舍

- **交叉引用是纯文本。** 正文里写的是 "Figure 6"、"Section 4.6"，不是 `\ref{}`。因为图序和章节序与 Word 版严格一致，这样两边读起来对得上；代价是如果你增删了图，正文里的编号要自己改。想改用 `\ref`，给图加 `\label{fig:xx}` 即可。
- **表格用 `booktabs` + `tabularx`。** 竖线全部去掉，横向只有三条粗细不同的线，这是学术排版惯例。列宽自动分配，不要在单元格里加 `\hline`。
- **参考文献是手工 `enumerate`。** 没有用 BibTeX。如果老师要求特定格式（如 IEEE），换成 `\bibliography` 更快。
- **字体是 Latin Modern**（`lmodern`）。在 Overleaf 和本机一致，不需要装额外字体。

## 编译验证

本机 MiKTeX 25.12 + pdfLaTeX 编译通过：**0 error，0 overfull box，21 页**。
