"""Fill the course cover sheet from the single member list used by the report.

The template ships as .doc; `_cover_tpl.docx` is its converted copy (see README).
Everything else here is generated, so re-running this after editing MEMBERS in
src/build_report.py keeps the cover sheet in step with the report.
"""
from __future__ import annotations

import os
import shutil

from docx import Document
from docx.shared import Cm

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(BASE, "_cover_tpl.docx")
OUT = os.path.join(BASE, "..", "Submission", "project_cover_sheet.docx")

MEMBERS = [
    ("60371620", "Liuxianjia DIAO", "ldiao7-c@my.cityu.edu.hk"),
    ("61080389", "Lingxiao Zhou", "lingxzhou3-c@my.cityu.edu.hk"),
    ("60018560", "Ziyao YANG", "ziyaoyang5-c@my.cityu.edu.hk"),
    ("60263031", "Jin LI", "k1160967796@163.com"),
]

TITLE = ("Cinema Blocs and Local Talent Structure: Parallel Graph Analytics of the "
         "Hong Kong Release Network from 169.6 Million IMDb Rows")

HIGHLIGHTS = [
    "Scanned 169.6 M rows across five IMDb dumps on one laptop and built a 51,878-node, "
    "388,168-edge collaboration network of the Hong Kong release market.",
    "Three parallel strategies matched to three workload shapes: 6.93x on the scan tier, "
    "4.51x on rule counting, and PageRank that degrades to 0.96x at 16 workers.",
    "Without a single country label, Louvain recovers the cinema blocs: modularity 0.75 at "
    "cross-seed stability NMI 0.89.",
    "PageRank identifies the historically documented core of the local industry rather than "
    "its most prolific performers (Spearman rho 0.49 against degree).",
    "Every number is reproduced by one command, and the benchmark logs ship with the code.",
]

DELIVERABLES = [
    ("report.pdf", "Main project report (23 pages)"),
    ("slides.pdf", "Presentation slides, 11 pages"),
    ("data.md", "Data sources, licence, download script and derived graph"),
]


def set_text(par, text):
    runs = par.runs
    if not runs:
        par.add_run(text)
        return
    runs[0].text = text
    for r in runs[1:]:
        r.text = ""


def main():
    shutil.copy(TPL, OUT)
    d = Document(OUT)
    P = d.paragraphs

    # All three lines share one geometry: colon at 3.5 cm, values at 3.9 cm, and a
    # hanging indent so wrapped or repeated values stay in the value column.
    # chr(9)/chr(10) because python-docx turns them into a tab and a line break.
    rows = [
        (3, "Student IDs", ", ".join(m[0] for m in MEMBERS)),
        (4, "Student Names", ", ".join(m[1] for m in MEMBERS)),
        (5, "Student Emails", chr(10).join(m[2] for m in MEMBERS)),   # one address per line
    ]
    for idx, label, value in rows:
        par = P[idx]
        for r in list(par.runs):
            r._element.getparent().remove(r._element)
        pf = par.paragraph_format
        pf.left_indent = Cm(3.9)
        pf.first_line_indent = Cm(-3.9)
        pf.tab_stops.add_tab_stop(Cm(3.5))    # colon column
        pf.tab_stops.add_tab_stop(Cm(3.9))    # value column, same as the hanging indent
        par.add_run(label + chr(9) + ":" + chr(9) + value)

    set_text(P[9], TITLE)
    for idx, text in zip(range(12, 17), HIGHLIGHTS):
        set_text(P[idx], text)

    t = d.tables[0]
    for i, (name, desc) in enumerate(DELIVERABLES, start=1):
        set_text(t.rows[i].cells[0].paragraphs[0], name)
        set_text(t.rows[i].cells[1].paragraphs[0], desc)

    d.save(OUT)
    print("written:", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
