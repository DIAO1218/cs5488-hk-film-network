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
