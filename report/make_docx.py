"""Markdown -> DOCX converter used for the report.

Handles headings, paragraphs, bullet and numbered lists, pipe tables, fenced code,
images (centred, with the following italic line as the caption) and page numbers.
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
SRC = os.path.join(BASE, "report", "Report.md")
OUT = os.path.join(BASE, "report", "Report.docx")
if len(sys.argv) >= 3:
    SRC = sys.argv[1] if os.path.isabs(sys.argv[1]) else os.path.join(BASE, sys.argv[1])
    OUT = sys.argv[2] if os.path.isabs(sys.argv[2]) else os.path.join(BASE, sys.argv[2])

BODY_FONT = "Times New Roman"
BODY_SIZE = Pt(10.5)
COL_WIDTHS = {
    2: [5.0, 11.2],
    3: [4.4, 4.6, 7.0],
    4: [3.0, 2.4, 4.4, 6.2],
    5: [1.2, 3.3, 3.3, 4.0, 4.1],
    6: [1.0, 3.0, 3.0, 3.1, 3.0, 3.0],
}
INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*]+\*)")


def set_run_font(run, name=BODY_FONT, size=BODY_SIZE, bold=None, italic=None, color=None):
    run.font.name = name
    run.font.size = size
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs"):
        rfonts.set(qn(attr), name)
    # East Asian face must be a CJK font; Times New Roman has no Chinese glyphs
    rfonts.set(qn("w:eastAsia"), "宋体")


def add_inline(paragraph, text, base_bold=False, base_italic=False, size=BODY_SIZE):
    for token in INLINE.split(text):
        if not token:
            continue
        if token.startswith("**") and token.endswith("**") and len(token) > 4:
            run = paragraph.add_run(token[2:-2])
            set_run_font(run, size=size, bold=True, italic=base_italic)
        elif token.startswith("`") and token.endswith("`") and len(token) > 2:
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, name="Consolas", size=Pt(size.pt - 0.5), bold=base_bold)
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, size=size, bold=base_bold, italic=True)
        else:
            run = paragraph.add_run(token)
            set_run_font(run, size=size, bold=base_bold, italic=base_italic)


def shade(cell, hexcolor):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcpr.append(shd)


def cell_margins(table, top=30, bottom=30, left=70, right=70):
    tblpr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for tag, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        node = OxmlElement(f"w:{tag}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    tblpr.append(mar)


def set_col_widths(table, widths):
    table.autofit = False
    tblpr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblpr.append(layout)
    for row in table.rows:
        for idx, width in enumerate(widths):
            if idx < len(row.cells):
                row.cells[idx].width = Cm(width)


def repeat_header(row):
    trpr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trpr.append(el)


def add_page_number_footer(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), " PAGE ")
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rfonts = OxmlElement("w:rFonts")
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), BODY_FONT)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "18")
    rpr.append(rfonts)
    rpr.append(sz)
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = "1"
    run.append(t)
    fld.append(run)
    p._p.append(fld)


def build():
    with open(SRC, encoding="utf-8") as fh:
        lines = fh.read().split("\n")

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2.3)
    sec.left_margin = sec.right_margin = Cm(2.4)

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = BODY_SIZE
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.12
    add_page_number_footer(sec)

    i, n = 0, len(lines)
    cover_done = False
    first_break = False

    while i < n:
        line = lines[i].rstrip()
        s = line.strip()

        if not s:
            i += 1
            continue

        if s == "---":
            if not first_break:
                doc.add_page_break()
                first_break = True
            else:
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(2)
                pPr = p._p.get_or_add_pPr()
                pbdr = OxmlElement("w:pBdr")
                bottom = OxmlElement("w:bottom")
                bottom.set(qn("w:val"), "single")
                bottom.set(qn("w:sz"), "4")
                bottom.set(qn("w:color"), "D9D9D4")
                pbdr.append(bottom)
                pPr.append(pbdr)
            i += 1
            continue

        # image
        m = re.fullmatch(r"!\[(.*?)\]\((.+?)\)", s)
        if m:
            rel = m.group(2)
            path = rel if os.path.isabs(rel) else os.path.join(BASE, rel)
            if os.path.exists(path):
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(2)
                p.add_run().add_picture(path, width=Cm(15.4))
            i += 1
            continue

        # table
        if s.startswith("|"):
            is_cover = not cover_done
            cover_done = True
            if is_cover:
                gap = doc.add_paragraph()
                gap.paragraph_format.space_before = Pt(10)
                gap.paragraph_format.space_after = Pt(0)
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            rows = []
            for row in block:
                if re.fullmatch(r"\|[\s:\-\|]+\|", row):
                    continue
                rows.append([c.strip() for c in row.strip("|").split("|")])
            if not rows:
                continue
            ncols = max(len(r) for r in rows)
            table = doc.add_table(rows=0, cols=ncols)
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.autofit = False
            cell_margins(table)
            for r_idx, cells in enumerate(rows):
                cells = cells + [""] * (ncols - len(cells))
                row_obj = table.add_row()
                for c_idx, text in enumerate(cells):
                    para = row_obj.cells[c_idx].paragraphs[0]
                    para.paragraph_format.space_after = Pt(1)
                    para.paragraph_format.line_spacing = 1.0
                    if r_idx == 0:
                        add_inline(para, text, base_bold=True, size=Pt(8.5))
                        shade(row_obj.cells[c_idx], "EFEFEA")
                    else:
                        add_inline(para, text, size=Pt(8.5))
            if ncols in COL_WIDTHS:
                set_col_widths(table, COL_WIDTHS[ncols])
            repeat_header(table.rows[0])
            sp = doc.add_paragraph()
            sp.paragraph_format.space_after = Pt(3)
            continue

        # code block
        if s.startswith("```"):
            i += 1
            code = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            para = doc.add_paragraph()
            para.paragraph_format.space_before = Pt(4)
            para.paragraph_format.space_after = Pt(8)
            para.paragraph_format.line_spacing = 1.0
            runs = para.add_run("\n".join(code))
            set_run_font(runs, name="Consolas", size=Pt(8))
            continue

        # headings
        if s.startswith("#"):
            level = len(s) - len(s.lstrip("#"))
            text = s[level:].strip()
            para = doc.add_paragraph()
            if level == 1:
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER if not cover_done else WD_ALIGN_PARAGRAPH.LEFT
                para.paragraph_format.space_before = Pt(6)
                para.paragraph_format.space_after = Pt(3)
                set_run_font(para.add_run(text), size=Pt(17), bold=True, color=RGBColor(0x1A, 0x1A, 0x1A))
            elif level == 2:
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER if not cover_done else WD_ALIGN_PARAGRAPH.LEFT
                para.paragraph_format.space_before = Pt(10)
                para.paragraph_format.space_after = Pt(6)
                set_run_font(para.add_run(text), size=Pt(12), bold=True, color=RGBColor(0x2C, 0x2C, 0x2C))
            else:
                para.paragraph_format.space_before = Pt(9)
                para.paragraph_format.space_after = Pt(3)
                set_run_font(para.add_run(text), size=Pt(10.8), bold=True, color=RGBColor(0x2C, 0x2C, 0x2C))
            i += 1
            continue

        if s.startswith("- "):
            para = doc.add_paragraph(style="List Bullet")
            para.paragraph_format.space_after = Pt(2)
            para.paragraph_format.left_indent = Cm(0.7)
            add_inline(para, s[2:])
            i += 1
            continue

        mnum = re.match(r"^(\d+)\.\s+(.*)$", s)
        if mnum:
            para = doc.add_paragraph(style="List Number")
            para.paragraph_format.space_after = Pt(2)
            para.paragraph_format.left_indent = Cm(0.7)
            add_inline(para, mnum.group(2))
            i += 1
            continue

        # blockquote note ("> text")
        if s.startswith("> "):
            para = doc.add_paragraph()
            para.paragraph_format.space_after = Pt(4)
            para.paragraph_format.left_indent = Cm(0.5)
            pPr = para._p.get_or_add_pPr()
            pbdr = OxmlElement("w:pBdr")
            left = OxmlElement("w:left")
            left.set(qn("w:val"), "single")
            left.set(qn("w:sz"), "12")
            left.set(qn("w:space"), "8")
            left.set(qn("w:color"), "C9C9C4")
            pbdr.append(left)
            pPr.append(pbdr)
            run = para.add_run(s[2:])
            set_run_font(run, size=Pt(9), color=RGBColor(0x5F, 0x5E, 0x5A))
            i += 1
            continue

        # caption line (italic single-line)
        if s.startswith("*") and s.endswith("*") and not s.startswith("**") and s.count("*") == 2:
            para = doc.add_paragraph()
            para.paragraph_format.space_after = Pt(10)
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = para.add_run(s.strip("*"))
            set_run_font(run, size=Pt(8.6), italic=True, color=RGBColor(0x3C, 0x3C, 0x3A))
            i += 1
            continue

        para = doc.add_paragraph()
        para.paragraph_format.space_after = Pt(5)
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if cover_done else WD_ALIGN_PARAGRAPH.CENTER
        add_inline(para, s)
        i += 1

    doc.save(OUT)
    print("written:", OUT)


if __name__ == "__main__":
    build()
