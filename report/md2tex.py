"""Convert the report Markdown into a LaTeX project split by section.

One source of truth: Report.md is generated from the benchmark artefacts, and this
script turns it into a project where each section is its own file, so four people
can edit in parallel without conflicting.
"""
from __future__ import annotations

import os
import re
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "report", "Report.md")
OUTDIR = os.path.join(BASE, "report", "latex")
SECDIR = os.path.join(OUTDIR, "sections")

SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*]+\*)")


# pdflatex cannot typeset Greek or math symbols straight from UTF-8 text, so the
# few that appear in the prose are mapped to math mode here.
SYMBOLS = {
    "γ": r"$\gamma$", "ρ": r"$\rho$", "λ": r"$\lambda$", "σ": r"$\sigma$",
    "α": r"$\alpha$", "β": r"$\beta$", "μ": r"$\mu$",
    "×": r"$\times$", "≥": r"$\geq$", "≤": r"$\leq$", "≈": r"$\approx$",
    "→": r"$\to$", "∈": r"$\in$", "·": r"$\cdot$", "−": r"$-$", "±": r"$\pm$",
    "—": r"\textemdash{}", "–": r"\textendash{}", "’": r"'", "‘": r"'",
    "é": r"\'{e}", "ō": r"\={o}", "ü": r'\"{u}', "ä": r'\"{a}', "ö": r'\"{o}',
    "²": r"$^2$", "³": r"$^3$", "⁵": r"$^5$", "⁶": r"$^6$", "⁷": r"$^7$",
    "⁴": r"$^4$", "⁸": r"$^8$", "⁹": r"$^9$",
}


def esc(text: str) -> str:
    for k, v in SPECIAL.items():
        text = text.replace(k, v)
    for k, v in SYMBOLS.items():
        text = text.replace(k, v)
    return text


def inline(text: str) -> str:
    """Escape plain runs, then re-apply bold / italic / code markup."""
    out = []
    for token in INLINE.split(text):
        if not token:
            continue
        if token.startswith("**") and token.endswith("**") and len(token) > 4:
            out.append(r"\textbf{" + esc(token[2:-2]) + "}")
        elif token.startswith("`") and token.endswith("`") and len(token) > 2:
            body = token[1:-1]
            if re.match(r"https?://", body):
                out.append(r"\url{" + body + "}")
            else:
                out.append(r"\texttt{" + esc(body) + "}")
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            out.append(r"\emph{" + esc(token[1:-1]) + "}")
        else:
            out.append(esc(token))
    return "".join(out)


def colspec(ncols: int, first_col_max: int = 0) -> str:
    """Left column stays narrow unless its content is long enough to overflow."""
    if ncols <= 1:
        return "X"
    head = "X" if first_col_max > 22 else "l"
    return head + "X" * (ncols - 1)


def slug(text: str) -> str:
    text = re.sub(r"^[0-9]+\.?\s*", "", text)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return text or "section"


def convert_table(rows: list[str]) -> str:
    parsed = []
    for row in rows:
        if re.fullmatch(r"\|[\s:\-\|]+\|", row):
            continue
        parsed.append([c.strip() for c in row.strip("|").split("|")])
    if not parsed:
        return ""
    ncols = max(len(r) for r in parsed)
    first_max = max((len(r[0]) for r in parsed), default=0)
    body = []
    for i, cells in enumerate(parsed):
        cells = cells + [""] * (ncols - len(cells))
        # a cell starting with "[" would be parsed as \\[len] optional argument;
        # item names like "G:Animation" have no natural break points, so add some
        rendered = []
        for c in (inline(c) for c in cells):
            c = c.replace(":", r":\allowbreak{}").replace(r"\_", r"\_\allowbreak{}")
            rendered.append("{}" + c if c.startswith("[") else c)
        line = " & ".join(rendered) + r" \\"
        body.append(line)
        if i == 0:
            body.append(r"\midrule")
    return (
        "\\begin{table}[H]\n\\centering\n\\footnotesize\n"
        f"\\begin{{tabularx}}{{\\textwidth}}{{{colspec(ncols, first_max)}}}\n"
        "\\toprule\n" + "\n".join(body) + "\n\\bottomrule\n"
        "\\end{tabularx}\n\\end{table}\n"
    )


def convert_body(lines: list[str]) -> str:
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        s = raw.strip()

        if not s:
            i += 1
            continue

        if s == "---":
            i += 1
            continue

        # figure: image line, blank, then italic caption
        m = re.fullmatch(r"!\[(.*?)\]\((.+?)\)", s)
        if m:
            path = m.group(2)
            caption = ""
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j < n:
                cap = lines[j].strip()
                if cap.startswith("*") and cap.endswith("*") and cap.count("*") == 2:
                    caption = cap.strip("*")
                    i = j
            caption = re.sub(r"^Figure\s+\d+\.\s*", "", caption)
            out.append(
                "\\begin{figure}[htbp]\n\\centering\n"
                f"\\includegraphics[width=\\linewidth]{{{path}}}\n"
                f"\\caption{{{inline(caption)}}}\n"
                "\\end{figure}\n"
            )
            i += 1
            continue

        # table
        if s.startswith("|"):
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            out.append(convert_table(block))
            continue

        # code block
        if s.startswith("```"):
            i += 1
            code = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("\\begin{verbatim}\n" + "\n".join(code) + "\n\\end{verbatim}\n")
            continue

        # headings
        if s.startswith("### "):
            # LaTeX numbers headings itself; drop the manual "3.1 " prefix
            text = re.sub(r"^\d+(\.\d+)*\.?\s*", "", s[4:])
            out.append("\\subsection{" + inline(text) + "}\n")
            i += 1
            continue
        if s.startswith("## "):
            text = re.sub(r"^\d+(\.\d+)*\.?\s*", "", s[3:])
            out.append("\\section{" + inline(text) + "}\n")
            i += 1
            continue
        if s.startswith("# "):
            i += 1
            continue

        # lists
        if s.startswith("- "):
            items = []
            while i < n and lines[i].strip().startswith("- "):
                items.append("  \\item " + inline(lines[i].strip()[2:]))
                i += 1
            out.append("\\begin{itemize}\n" + "\n".join(items) + "\n\\end{itemize}\n")
            continue

        mnum = re.match(r"^(\d+)\.\s+(.*)$", s)
        if mnum:
            items = []
            while i < n:
                mm = re.match(r"^(\d+)\.\s+(.*)$", lines[i].strip())
                if not mm:
                    break
                items.append("  \\item " + inline(mm.group(2)))
                i += 1
            out.append("\\begin{enumerate}\n" + "\n".join(items) + "\n\\end{enumerate}\n")
            continue

        # note / blockquote
        if s.startswith("> "):
            out.append("\\begin{quote}\\small\\itshape " + inline(s[2:]) + "\\end{quote}\n")
            i += 1
            continue

        # caption orphan (italic line not after an image)
        if s.startswith("*") and s.endswith("*") and s.count("*") == 2 and not s.startswith("**"):
            out.append("\\begin{center}\\small\\itshape " + inline(s.strip("*")) + "\\end{center}\n")
            i += 1
            continue

        # paragraph: collect until blank line
        para = []
        while i < n and lines[i].strip() and not lines[i].strip().startswith(("|", "#", "- ", "![")):
            if re.match(r"^\d+\.\s", lines[i].strip()):
                break
            para.append(lines[i].strip())
            i += 1
        out.append(inline(" ".join(para)) + "\n")

    return "\n".join(out)



LATEX_README = """# LaTeX 版报告（小组协作）

这份是 `report/Report.docx` 的 LaTeX 版本，**按章节拆成了独立文件**，四个人可以各改各的，不会互相覆盖。

> 本文件由 `report/md2tex.py` 自动生成。要改说明文字请改脚本，不要直接改这里——
> 重新生成 LaTeX 工程时会覆盖。

## 目录结构

```
latex/
├── main.tex                 主文件：导言区、封面、目录、\\\\input 各章（一般不用动）
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
└── figures/                 13 张图（与 Word 版相同，改图请重跑 src/figures.py）
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

要跑三遍：第一遍生成 `.aux`，第二遍填目录和交叉引用，第三遍才稳定。装 `latexmk` 后可用一条命令：`latexmk -pdf main.tex`。

**3. 只想读**

直接看 `main.pdf`（21 页，已编译好）。

## 改内容时的三条规矩

1. **不要手工编号。** 章节、图、表、公式的编号都是 LaTeX 自动生成的。写 `\\\\section{Methodology}`，不要写 `\\\\section{3. Methodology}`。
2. **数字从结果来。** 正文里的数字由 `src/build_report.py` 从 `results/*.jsonl` 生成。重跑实验后应改 `report/Report.md` 的上游生成器再重跑 `python report/md2tex.py`，而不是直接在 `.tex` 里手改——否则 Word 版、中文版和 LaTeX 版会互相不一致。
3. **图不要单独换。** `figures/` 里的 PNG 由 `src/figures.py` 生成；在目录里直接替换图片，下次重跑会被覆盖。

## 已知的取舍

- **交叉引用是纯文本。** 正文写的是 "Figure 6"、"Section 4.6"，不是 `\\\\ref{}`。因为图序与章节序与 Word 版严格一致，两边读起来能对上；代价是增删图后要自己改正文编号。想换成 `\\\\ref`，给图加 `\\\\label{fig:xx}` 即可。
- **表格用 `booktabs` + `tabularx`。** 去掉竖线、只留三条横线，是学术排版惯例；列宽自动分配，不要在单元格里加 `\\\\hline`。
- **参考文献是手工 `enumerate`。** 没有用 BibTeX。若老师要求特定格式（如 IEEE），换成 `\\\\bibliography` 更快。
- **字体是 Latin Modern**（`lmodern`），Overleaf 与本地表现一致，无需额外字体。

## 编译验证

本机 MiKTeX 25.12 + pdfLaTeX：**0 error，0 overfull box，21 页**。
"""

PREAMBLE = r"""\documentclass[11pt,a4paper]{article}

\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[utf8]{inputenc}
\usepackage[margin=2.4cm]{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{array}
\usepackage{float}
\usepackage{caption}
\usepackage{enumitem}
\usepackage[protrusion=true,expansion=true]{microtype}
\usepackage{xcolor}
\usepackage[hidelinks]{hyperref}

\captionsetup{font=small,labelfont=bf,skip=4pt}
\setlist[itemize]{leftmargin=1.2em,itemsep=2pt,topsep=3pt}
\setlist[enumerate]{leftmargin=1.5em,itemsep=2pt,topsep=3pt}
\renewcommand{\arraystretch}{1.15}
\setlength{\parskip}{0.35em}
\setlength{\parindent}{0pt}

\title{%(title)s \\[0.4em] \large %(subtitle)s}
\author{%(author)s}
\date{%(date)s}

\begin{document}
\maketitle

%(cover)s

\tableofcontents
\clearpage

%(inputs)s

\end{document}
"""


def build() -> None:
    with open(SRC, encoding="utf-8") as fh:
        lines = fh.read().split("\n")

    # front matter ends at the first numbered section heading ("## 1. Abstract");
    # the "## " line before it is the subtitle, not a section.
    first = next(i for i, l in enumerate(lines) if re.match(r"^## \d+\.", l))
    front = [l for l in lines[:first] if l.strip() and l.strip() != "---"]

    title = front[0].lstrip("# ").strip()
    subtitle = ""
    for l in front[1:]:
        if l.startswith("## "):
            subtitle = l[3:].strip()
            break

    date = ""
    for l in front:
        if re.search(r"\b(19|20)\d{2}\b", l) and not l.startswith(("#", "|", "**")):
            date = l.strip()
            break

    sub_line = "## " + subtitle
    cover_lines = [l for l in lines[:first]
                   if l.strip() and l.strip() != "---"
                   and not l.startswith("# ")
                   and l.strip() != sub_line
                   and l.strip() != date]
    cover_text = convert_body(cover_lines)
    body = convert_body(lines[first:])

    # split on \section{...} boundaries
    parts = re.split(r"(?=\\section\{)", body)
    if parts and not parts[0].strip().startswith("\\section"):
        preamble_text = parts[0]
        parts = parts[1:]
    else:
        preamble_text = ""

    os.makedirs(SECDIR, exist_ok=True)
    if os.path.isdir(os.path.join(OUTDIR, "figures")):
        shutil.rmtree(os.path.join(OUTDIR, "figures"))
    shutil.copytree(os.path.join(BASE, "figures"), os.path.join(OUTDIR, "figures"))

    inputs = []
    for idx, part in enumerate(parts, start=1):
        m = re.match(r"\\section\{(.+?)\}", part)
        name = slug(re.sub(r"\\[a-zA-Z]+\{|\}", "", m.group(1)) if m else f"part{idx}")
        fname = f"{idx:02d}_{name}.tex"
        with open(os.path.join(SECDIR, fname), "w", encoding="utf-8") as fh:
            fh.write("% " + (m.group(1) if m else fname) + "\n")
            fh.write("% Generated by report/md2tex.py from Report.md -- edit Report.md, then re-run.\n\n")
            fh.write(part.strip() + "\n")
        inputs.append(f"\\input{{sections/{fname}}}")

    main = PREAMBLE % {
        "title": title,
        "subtitle": subtitle,
        "author": "CS5488 Data-Intensive Computing \\textemdash{} Group Project",
        "date": date or r"\today",
        "cover": cover_text,
        "inputs": "\n".join(inputs),
    }
    with open(os.path.join(OUTDIR, "main.tex"), "w", encoding="utf-8") as fh:
        fh.write(main)
    with open(os.path.join(OUTDIR, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(LATEX_README)

    print(f"written {OUTDIR}/main.tex and {len(parts)} section files")

    leftovers = {}
    for root, _, files in os.walk(OUTDIR):
        for f in files:
            if not f.endswith(".tex"):
                continue
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                for ch in fh.read():
                    if ord(ch) > 127:
                        leftovers[ch] = leftovers.get(ch, 0) + 1
    if leftovers:
        print("non-ASCII left in .tex (needs a mapping or XeLaTeX):")
        for ch, c in sorted(leftovers.items(), key=lambda kv: -kv[1]):
            print(f"   {ch!r} x{c}")
    else:
        print("all text is ASCII; pdflatex-safe")


if __name__ == "__main__":
    build()
