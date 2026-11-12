"""Convert Proposal.md into a clean, template-aligned DOCX."""
import re
import sys
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

SRC = r"C:/Users/26657/Desktop/CS5488/Project_Work/Proposal.md"
OUT = r"C:/Users/26657/Desktop/CS5488/Project_Work/Proposal.docx"

BODY_FONT = "Times New Roman"
BODY_SIZE = Pt(11)


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
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), name)


INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*]+\*)")


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


COL_WIDTHS = {
    2: [5.0, 11.2],
    3: [4.4, 4.6, 7.2],
    4: [3.2, 2.2, 4.4, 6.4],
    5: [1.2, 3.4, 3.4, 4.0, 4.2],
    6: [1.0, 3.0, 3.0, 3.2, 3.0, 3.0],
}


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


def cell_margins(table, top=40, bottom=40, left=80, right=80):
    tblpr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for tag, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        node = OxmlElement(f"w:{tag}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    tblpr.append(mar)


def repeat_header(row):
    trpr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trpr.append(el)


def add_page_number_footer(section):
    footer = section.footer
    p = footer.paragraphs[0]
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
    with open(SRC, "r", encoding="utf-8") as fh:
        lines = fh.read().split("\n")

    doc = Document()

    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    for attr in ("top_margin", "bottom_margin"):
        setattr(section, attr, Cm(2.54))
    for attr in ("left_margin", "right_margin"):
        setattr(section, attr, Cm(2.4))

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = BODY_SIZE
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    add_page_number_footer(section)

    i = 0
    n = len(lines)
    first_h1_done = False
    title_break_done = False
    cover_done = False

    while i < n:
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            if not title_break_done:
                doc.add_page_break()
                title_break_done = True
            i += 1
            continue

        # table block
        if stripped.startswith("|"):
            is_cover_table = not cover_done
            cover_done = True
            if is_cover_table:
                spacer = doc.add_paragraph()
                spacer.paragraph_format.space_before = Pt(10)
                spacer.paragraph_format.space_after = Pt(0)
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            rows = []
            for idx, row in enumerate(block):
                if re.fullmatch(r"\|[\s:\-\|]+\|", row):
                    continue
                cells = [c.strip() for c in row.strip("|").split("|")]
                rows.append((cells, idx))
            if not rows:
                continue
            ncols = max(len(r[0]) for r in rows)
            table = doc.add_table(rows=0, cols=ncols)
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.autofit = False
            cell_margins(table)
            for r_idx, (cells, _) in enumerate(rows):
                cells = cells + [""] * (ncols - len(cells))
                row_obj = table.add_row()
                for c_idx, text in enumerate(cells):
                    cell = row_obj.cells[c_idx]
                    para = cell.paragraphs[0]
                    para.paragraph_format.space_after = Pt(2)
                    para.paragraph_format.line_spacing = 1.0
                    if r_idx == 0:
                        add_inline(para, text, base_bold=True, size=Pt(9.5))
                        shade(cell, "EDEDE8")
                    else:
                        add_inline(para, text, size=Pt(9.5))
            if rows:
                if ncols in COL_WIDTHS:
                    set_col_widths(table, COL_WIDTHS[ncols])
                repeat_header(table.rows[0])
            doc.add_paragraph().paragraph_format.space_after = Pt(4)
            continue

        # code block
        if stripped.startswith("```"):
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            para = doc.add_paragraph()
            para.paragraph_format.space_before = Pt(4)
            para.paragraph_format.space_after = Pt(8)
            para.paragraph_format.line_spacing = 1.0
            run = para.add_run("\n".join(code_lines))
            set_run_font(run, name="Consolas", size=Pt(9))
            continue

        # headings
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped[level:].strip()
            if level == 1:
                para = doc.add_paragraph()
                if not cover_done:
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                para.paragraph_format.space_before = Pt(0 if not first_h1_done else 18)
                para.paragraph_format.space_after = Pt(4)
                run = para.add_run(text)
                set_run_font(run, size=Pt(18), bold=True, color=RGBColor(0x1A, 0x1A, 0x1A))
                first_h1_done = True
            elif level == 2:
                para = doc.add_paragraph()
                if not cover_done:
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                para.paragraph_format.space_before = Pt(14)
                para.paragraph_format.space_after = Pt(8)
                run = para.add_run(text)
                set_run_font(run, size=Pt(13), bold=True, color=RGBColor(0x2C, 0x2C, 0x2C))
            else:
                para = doc.add_paragraph()
                para.paragraph_format.space_before = Pt(10)
                para.paragraph_format.space_after = Pt(4)
                run = para.add_run(text)
                set_run_font(run, size=Pt(11.5), bold=True, color=RGBColor(0x2C, 0x2C, 0x2C))
            i += 1
            continue

        # bullet list
        if stripped.startswith("- "):
            para = doc.add_paragraph(style="List Bullet")
            para.paragraph_format.space_after = Pt(3)
            para.paragraph_format.left_indent = Cm(0.75)
            add_inline(para, stripped[2:])
            i += 1
            continue

        # numbered list
        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            para = doc.add_paragraph(style="List Number")
            para.paragraph_format.space_after = Pt(3)
            para.paragraph_format.left_indent = Cm(0.75)
            add_inline(para, m.group(2))
            i += 1
            continue

        # blockquote-ish italic note
        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            para = doc.add_paragraph()
            para.paragraph_format.space_before = Pt(8)
            run = para.add_run(stripped.strip("*"))
            set_run_font(run, size=Pt(9.5), italic=True, color=RGBColor(0x5F, 0x5E, 0x5A))
            i += 1
            continue

        # normal paragraph
        para = doc.add_paragraph()
        para.paragraph_format.space_after = Pt(6)
        if cover_done:
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        else:
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_inline(para, stripped)
        i += 1

    doc.save(OUT)
    print("written:", OUT)


if __name__ == "__main__":
    build()
