"""Render the report into the course template (Project_report_template.doc).

The template fixes a different section order than Report.md uses, so this script
re-sections the same text rather than restyling the old file: Abstract,
Introduction, Motivation, Objective, Data Sources, Methodology, Results and
Analysis, Discussion, Conclusion — then the contribution statement and references,
which the specification requires but the template does not enumerate.
"""
from __future__ import annotations

import os
import re
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "report"))
import make_docx as M  # noqa: E402  (shared inline/font/table helpers)

TEMPLATE = os.path.join(BASE, "_rpt_tpl.docx")
SRC = os.path.join(BASE, "report", "Report.md")
OUT = os.path.join(BASE, "report", "Report_template.docx")

BODY_SIZE = Pt(11)
FIG_WIDTH = Cm(16.2)
WIDTHS = {
    2: [4.6, 13.2],
    3: [4.2, 4.6, 9.0],
    4: [2.8, 2.4, 5.4, 7.2],
    5: [1.2, 3.4, 3.4, 4.6, 5.2],
}
# md section title -> template section title(s)
RENAME = {
    "1. Abstract": None,              # handled as the cover abstract
    "2. Introduction": "Introduction",
    "3. Methodology": "Methodology",
    "4. Results and Analysis": "Results and Analysis",
    "5. Discussion": "Discussion",
    "6. Conclusion and Future Work": "Conclusion",
    "7. Individual Contribution Statement": "Individual Contribution Statement",
    "8. References": "References",
}


def split_sections(lines):
    """[(title, body_lines)] for every '## ' heading."""
    out, cur, buf = [], None, []
    for ln in lines:
        if ln.startswith("## "):
            if cur is not None:
                out.append((cur, buf))
            cur, buf = ln[3:].strip(), []
        elif cur is not None:
            buf.append(ln)
    if cur is not None:
        out.append((cur, buf))
    return out


def split_subsections(lines):
    """Split a section body at '### ' headings."""
    pre, subs, cur, buf = [], [], None, []
    for ln in lines:
        if ln.startswith("### "):
            if cur is not None:
                subs.append((cur, buf))
            cur, buf = ln[4:].strip(), []
        elif cur is None:
            pre.append(ln)
        else:
            buf.append(ln)
    if cur is not None:
        subs.append((cur, buf))
    return pre, subs


def paragraphs_of(lines):
    """Group lines into paragraph strings, dropping blanks and captions."""
    paras, buf = [], []
    for ln in lines:
        s = ln.strip()
        if not s:
            if buf:
                paras.append(" ".join(buf))
                buf = []
            continue
        if s.startswith("![") or s == "---" or s.startswith("|"):
            continue
        if s.startswith("*") and s.endswith("*") and s.count("*") == 2:
            continue
        buf.append(s)
    if buf:
        paras.append(" ".join(buf))
    return paras


def add_borders(table):
    """The template ships without a table style, so draw the grid explicitly."""
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "BFBFBF")
        borders.append(el)
    tblPr.append(borders)


class Writer:
    def __init__(self, doc):
        self.doc = doc
        self.fig = 0
        self.tab = 0

    def h1(self, text):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(11)
        p.paragraph_format.space_after = Pt(5)
        p.paragraph_format.keep_with_next = True
        M.set_run_font(p.add_run(text), name="Cambria", size=Pt(16), bold=True,
                       color=RGBColor(0x1A, 0x1A, 0x1A))

    def h2(self, text):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(9)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        M.set_run_font(p.add_run(text), name="Cambria", size=Pt(12.5), bold=True,
                       color=RGBColor(0x1A, 0x1A, 0x1A))

    def para(self, text):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        M.add_inline(p, text, size=BODY_SIZE)

    def bullets(self, items):
        for it in items:
            p = self.doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.7)
            p.paragraph_format.first_line_indent = Cm(-0.35)
            p.paragraph_format.space_after = Pt(2)
            M.set_run_font(p.add_run("\u2022  "), size=BODY_SIZE)
            M.add_inline(p, it, size=BODY_SIZE)

    def figure(self, path, caption):
        if not os.path.exists(path):
            return
        self.fig += 1
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        p.add_run().add_picture(path, width=FIG_WIDTH)
        c = self.doc.add_paragraph()
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.paragraph_format.space_after = Pt(10)
        text = re.sub(r"^Figure\s+\d+\.\s*", "", caption)
        M.add_inline(c, f"Figure {self.fig}. {text}", base_italic=True, size=Pt(9))

    def table(self, rows):
        if not rows:
            return
        ncols = max(len(r) for r in rows)
        t = self.doc.add_table(rows=0, cols=ncols)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        add_borders(t)
        t.autofit = False
        M.cell_margins(t)
        for r_idx, cells in enumerate(rows):
            cells = cells + [""] * (ncols - len(cells))
            row = t.add_row()
            for c_idx, text in enumerate(cells):
                para = row.cells[c_idx].paragraphs[0]
                para.paragraph_format.space_after = Pt(1)
                para.paragraph_format.line_spacing = 1.0
                if r_idx == 0:
                    M.add_inline(para, text, base_bold=True, size=Pt(9))
                    M.shade(row.cells[c_idx], "EFEFEA")
                else:
                    M.add_inline(para, text, size=Pt(9))
        if ncols in WIDTHS:
            M.set_col_widths(t, WIDTHS[ncols])
        M.repeat_header(t.rows[0])

        # keep a short table on one page: no row may split, and every row but the
        # last asks to stay with the next one
        for r_idx, row in enumerate(t.rows):
            trPr = row._tr.get_or_add_trPr()
            trPr.append(OxmlElement("w:cantSplit"))
            if r_idx < len(t.rows) - 1:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        para.paragraph_format.keep_with_next = True
        self.doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def markdown(self, lines):
        """Emit a section body: headings, paragraphs, bullets, tables, figures."""
        i, n = 0, len(lines)
        while i < n:
            s = lines[i].strip()
            if not s or s == "---":
                i += 1
                continue
            if s.startswith("### "):
                self.h2(s[4:].strip())
                i += 1
                continue
            m = re.fullmatch(r"!\[(.*?)\]\((.+?)\)", s)
            if m:
                path = m.group(2)
                caption = ""
                j = i + 1
                while j < n and not lines[j].strip():
                    j += 1
                if j < n and re.fullmatch(r"\*[^*].*\*", lines[j].strip()):
                    caption = lines[j].strip().strip("*")
                    i = j
                self.figure(path if os.path.isabs(path) else os.path.join(BASE, path), caption)
                i += 1
                continue
            if s.startswith("|"):
                block = []
                while i < n and lines[i].strip().startswith("|"):
                    block.append(lines[i].strip())
                    i += 1
                rows = [[c.strip() for c in r.strip("|").split("|")] for r in block
                        if not re.fullmatch(r"\|[\s:\-\|]+\|", r)]
                self.table(rows)
                continue
            if s.startswith(("- ", "* ")):
                items = []
                while i < n and lines[i].strip().startswith(("- ", "* ")):
                    items.append(lines[i].strip()[2:])
                    i += 1
                self.bullets(items)
                continue
            if re.match(r"^\d+\.\s", s):
                start = i
                k = 0
                while i < n and re.match(r"^\d+\.\s", lines[i].strip()):
                    k += 1
                    p = self.doc.add_paragraph()
                    p.paragraph_format.left_indent = Cm(0.9)
                    p.paragraph_format.first_line_indent = Cm(-0.55)
                    p.paragraph_format.space_after = Pt(1)
                    p.paragraph_format.line_spacing = 1.0
                    M.set_run_font(p.add_run(f"{k}.  "), size=BODY_SIZE)
                    M.add_inline(p, re.sub(r"^\d+\.\s*", "", lines[i].strip()), size=BODY_SIZE)
                    i += 1
                item_paras = self.doc.paragraphs[-k:] if k else []
                for q in item_paras[:-1]:
                    q.paragraph_format.keep_with_next = True
                continue
            if s.startswith("```"):
                i += 1
                code = []
                while i < n and not lines[i].strip().startswith("```"):
                    code.append(lines[i])
                    i += 1
                i += 1
                pr = self.doc.add_paragraph()
                pr.paragraph_format.space_before = Pt(4)
                pr.paragraph_format.space_after = Pt(8)
                pr.paragraph_format.line_spacing = 1.0
                M.set_run_font(pr.add_run("\n".join(code)), name="Consolas", size=Pt(8.5))
                continue

            para = []
            while i < n and lines[i].strip() and not lines[i].strip().startswith(
                    ("|", "#", "![", "- ", "* ", "```")):
                if re.match(r"^\d+\.\s", lines[i].strip()):
                    break
                para.append(lines[i].strip())
                i += 1
            if para:
                self.para(" ".join(para))
            else:
                i += 1          # never leave the cursor stuck


def build() -> None:
    doc = Document(TEMPLATE)
    body = doc.element.body
    for el in list(body)[:-1]:          # keep the final sectPr (header/footer live there)
        body.remove(el)

    sec = doc.sections[0]
    sec.top_margin = sec.bottom_margin = Cm(1.6)
    sec.left_margin = sec.right_margin = Cm(1.6)

    for hp in sec.header.paragraphs:
        for run in hp.runs:
            if "[Type the project title]" in run.text:
                run.text = "Cinema Blocs and Local Talent Structure"

    normal = doc.styles["Normal"]
    normal.font.name = M.BODY_FONT
    normal.font.size = BODY_SIZE
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.12

    with open(SRC, encoding="utf-8") as fh:
        lines = fh.read().split("\n")

    front = []
    for ln in lines:
        # the first "## " is the subtitle; stop at the first numbered section
        if ln.startswith("## ") and re.match(r"^## \d+\.", ln):
            break
        front.append(ln)
    title = next(l[2:].strip() for l in front if l.startswith("# "))
    subtitle = next((l[3:].strip() for l in front if l.startswith("## ") and "IMDb" in l), "")

    w = Writer(doc)

    # ---- cover block, as the template lays it out
    members = []
    for ln in front:
        if ln.startswith("|") and not ln.startswith("| Student ID") and "---" not in ln:
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if len(cells) == 3 and cells[0].isdigit():
                members.append(cells)
    ids = ", ".join(m[0] for m in members)
    names = ", ".join(m[1] for m in members)
    mails = ", ".join(m[2] for m in members)
    for label, value in (("Student IDs", ids), ("Student Names", names), ("Student Emails", mails)):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        M.set_run_font(p.add_run(f"{label}\t: "), size=Pt(10))
        M.set_run_font(p.add_run(value), size=Pt(10))

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(2)
    M.set_run_font(p.add_run("Title:"), size=Pt(10))

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(14)
    M.set_run_font(p.add_run(title), name="Cambria", size=Pt(20), bold=True,
                   color=RGBColor(0x1A, 0x1A, 0x1A))

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    M.set_run_font(p.add_run("Abstract: (max 300 words)"), size=Pt(10))

    sections = split_sections(lines)
    by_name = {t: b for t, b in sections}
    abstract_lines = by_name.get("1. Abstract", [])
    for para in paragraphs_of(abstract_lines):
        w.para(para)

    doc.add_page_break()

    # ---- Introduction / Motivation / Objective / Data Sources out of section 2
    intro_body = by_name.get("2. Introduction", [])
    pre, subs = split_subsections(intro_body)
    submap = {t.split()[0]: b for t, b in subs}

    background = submap.get("2.1", [])
    paras = paragraphs_of(background)

    w.h1("Introduction")
    if paras:
        w.para(paras[0])

    w.h1("Motivation")
    for para in paras[1:]:
        w.para(para)

    w.h1("Objective")
    w.markdown(submap.get("2.2", []))

    w.h1("Data Sources")
    w.markdown(submap.get("2.3", []))

    # ---- remaining sections
    order = ["3. Methodology", "4. Results and Analysis", "5. Discussion",
             "6. Conclusion and Future Work", "7. Individual Contribution Statement",
             "8. References"]
    for name in order:
        body_lines = by_name.get(name, [])
        if not body_lines:
            continue
        w.h1(RENAME.get(name, name))
        w.markdown(body_lines)

    doc.save(OUT)
    print(f"written: {OUT}")


if __name__ == "__main__":
    build()
