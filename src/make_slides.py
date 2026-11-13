"""Build the 4-minute presentation deck from the measured results."""
from __future__ import annotations

import json
import os
import sys

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common import FIGURES, RESULTS, ROOT

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "report", "Slides.pptx")
INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x5F, 0x5E, 0x5A)
ACCENT = RGBColor(0x2F, 0x5D, 0x8C)
FONT = "Calibri"


def jload(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as fh:
        return json.load(fh)


def jlines(name):
    path = os.path.join(RESULTS, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def textbox(slide, left, top, width, height, text, size=18, bold=False, color=INK, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = FONT
    return box


def bullets(slide, left, top, width, height, items, size=15):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    first = True
    for item, level in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.level = level
        p.space_after = Pt(9)
        run = p.add_run()
        run.text = ("•  " if level == 0 else "–  ") + item
        run.font.size = Pt(size if level == 0 else size - 2)
        run.font.color.rgb = INK if level == 0 else MUTED
        run.font.name = FONT
    return box


def note(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def base(prs, title, kicker=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    if kicker:
        textbox(s, 0.62, 0.34, 11.5, 0.3, kicker.upper(), size=11, bold=True, color=ACCENT)
        textbox(s, 0.62, 0.62, 12.0, 0.7, title, size=27, bold=True)
    else:
        textbox(s, 0.62, 0.55, 12.0, 0.9, title, size=30, bold=True)
    line = s.shapes.add_connector(1, Inches(0.62), Inches(1.38), Inches(12.72), Inches(1.38))
    line.line.color.rgb = RGBColor(0xD9, 0xD9, 0xD4)
    line.line.width = Pt(0.75)
    return s


def picture(slide, name, left, top, width=None, height=None):
    path = os.path.join(FIGURES, name)
    if not os.path.exists(path):
        return
    if width:
        slide.shapes.add_picture(path, Inches(left), Inches(top), width=Inches(width))
    else:
        slide.shapes.add_picture(path, Inches(left), Inches(top), height=Inches(height))


def build():
    a = jload("analysis.json")
    e1 = jlines("bench_e1.jsonl")
    e3 = jlines("bench_e3.jsonl")
    e4 = jlines("bench_e4.jsonl")
    e3c = jlines("bench_e3c.jsonl")
    cm = a["community"]
    sp = lambda rows: (rows[0]["seconds"] / rows[-1]["seconds"]) if rows else 0
    s1 = sp(e1)
    s4 = sp(e4)
    s3 = sp(e3)
    top9 = 100 * sum(c["share"] for c in a["communities"][:9])
    b3 = max(r["speedup"] for r in e3c) if e3c else 0

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # 1 ---------------------------------------------------------------- title
    s = prs.slides.add_slide(prs.slide_layouts[6])
    textbox(s, 0.9, 1.85, 11.6, 1.0, "Does the network know what film history knows?", size=38, bold=True)
    textbox(s, 0.9, 3.05, 11.2, 1.3,
            "Parallel graph analytics of the Hong Kong release network", size=22, color=MUTED)
    textbox(s, 0.9, 4.55, 11.2, 1.0,
            "CS5488 Data-Intensive Computing   ·   Group project   ·   November 2026", size=14, color=MUTED)
    textbox(s, 0.9, 6.35, 11.2, 0.4,
            f"170 M rows scanned   ·   {a['graph']['edges']:,} co-star edges   ·   three parallel tiers on 20 threads",
            size=13, color=ACCENT)
    note(s, "SPEAKER 1 (60 s). Open with the question, not the method. 'Film historians say Hong Kong "
            "cinema was built on a small set of recurring collaborators. We asked whether an algorithm "
            "given nothing but cast lists arrives at the same answer — and what it costs to compute that "
            "at the scale of the whole IMDb.' Then the one-line roadmap: data, three parallel tiers, "
            "three findings.")

    # 2 ---------------------------------------------------------------- data
    s = base(prs, "The data has no country field — so we had to choose", "1 · the dataset")
    bullets(s, 0.62, 1.75, 5.9, 4.3, [
        ("IMDb public dumps: 1.78 GB compressed, 9.2 GB of text, 169.6 M rows", 0),
        ("Five files: titles, release aliases, cast/crew credits, people, ratings", 0),
        ("No production-country column exists in this release", 0),
        ("Three candidate filters, three different answers:", 1),
        ("region = HK  →  25,997 titles (admits every import)", 1),
        ("region = HK + Chinese alias  →  15,715 (selects the imports)", 1),
        ("region = HK + Chinese original title  →  0 (IMDb romanises)", 1),
    ], size=14)
    picture(s, "fig02_dataflow.png", 6.75, 1.9, width=6.1)
    textbox(s, 6.75, 5.0, 6.1, 1.6,
            "Decision: keep the release market, state it plainly, and let community detection "
            "separate the cinemas. That turned a data defect into the main result.",
            size=13, color=MUTED)
    note(s, "SPEAKER 1 (60 s). Own the weakness before the examiner finds it. 'The obvious filter is "
            "region equals HK. It returns 26,000 titles — and Brad Pitt is in the largest community, "
            "because every Hollywood film released in Hong Kong also has a Hong Kong alias. Requiring a "
            "Chinese alias makes it worse: that selects the imports. So we stopped pretending we had a "
            "production list and analysed the release network instead.'")

    # 3 ---------------------------------------------------------------- pipeline
    s = base(prs, "Three workloads, three parallel strategies", "2 · engineering")
    picture(s, "fig01_pipeline.png", 0.62, 1.65, width=8.3)
    bullets(s, 8.95, 1.75, 3.85, 4.4, [
        ("Tier 1 · byte-range map-reduce, process pool", 0),
        ("Parse-bound → the GIL rules out threads", 1),
        ("Tier 2 · blocked sparse matvec", 0),
        ("Rows partition; one barrier per iteration", 1),
        ("Tier 3 · sharded counting", 0),
        ("No locks during the scan; merge once", 1),
    ], size=13)
    textbox(s, 0.62, 5.55, 12.0, 1.3,
            "gzip is not seekable, so decompression is serial by construction (33.8 s, 4% of the "
            "serial cost). We report it separately instead of hiding it inside a stage.",
            size=13, color=MUTED)
    note(s, "SPEAKER 2 (60 s). The claim to land: 'parallelise it' is not one decision. Three workloads "
            "of the same size, same machine, three different ceilings. Point at the pipeline, then at "
            "the three tiers. Mention the gunzip openly — it is the Amdahl argument made concrete.")

    # 4 ---------------------------------------------------------------- scaling
    s = base(prs, "Same machine, three ceilings", "3 · results")
    picture(s, "fig10_scaling.png", 0.62, 1.6, height=4.9)
    bullets(s, 7.35, 1.75, 5.4, 4.6, [
        (f"Scan  {s1:.1f}× at 16 workers", 0),
        ("serial merge is the tail", 1),
        (f"Rule counting  {s4:.1f}× at 16 workers", 0),
        ("candidate generation saturates at ~1×", 1),
        (f"PageRank  {s3:.1f}× — and {b3:.1f}× at 16× the graph", 0),
        ("bandwidth-bound, not overhead-bound", 1),
    ], size=14)
    textbox(s, 7.35, 5.35, 5.3, 1.3,
            "First version created a pool per stage: 2.6× peak, then slower at 16 workers. "
            "One pool, one reference file per worker: 6.8×.",
            size=12, color=MUTED)
    note(s, "SPEAKER 2 (60 s). Give the three numbers in order and explain each in one sentence. E1 slows "
            "because the parent merges the partial results serially. E4's candidate generation is "
            "irregular, so the slowest shard decides the finish. PageRank does not improve when the graph "
            "grows sixteen-fold, which means the limit is memory bandwidth, not synchronisation — a "
            "different failure mode, and a more interesting one.")

    # 5 ---------------------------------------------------------------- blocs
    s = base(prs, "The blocs are real, and nobody labelled them", "4 · finding 1")
    picture(s, "fig06_network.png", 0.55, 1.55, height=5.3)
    bullets(s, 7.5, 1.7, 5.3, 4.6, [
        (f"Louvain: Q = {cm['q']:.2f}, {cm['n']:,} communities", 0),
        (f"Cross-seed stability NMI = {cm['stability_nmi']:.2f}", 1),
        (f"Nine blocs cover {top9:.0f}% of {a['graph']['nodes']:,} people", 0),
        ("Hollywood · Cantonese · mainland · Shaw-era · European · Japanese", 1),
        (f"Label propagation collapses: Q = {cm['lpa']['q']:.2f}, 87% in one label", 0),
        ("Cheap, and useless on this graph", 1),
    ], size=14)
    note(s, "SPEAKER 3 (60 s). The headline: no country label was given to the algorithm, and it still "
            "separated the cinemas. Then the negative control — label propagation is five times cheaper "
            "and returns one giant blob at modularity 0.08. That is why we report both: the cheap method "
            "fails in a way that is invisible unless you measure modularity.")

    # 6 ---------------------------------------------------------------- local core
    s = base(prs, "Inside the local bloc, rank ≠ volume", "5 · finding 2")
    picture(s, "fig05_pr_vs_degree.png", 0.62, 1.6, width=6.4)
    bullets(s, 7.3, 1.7, 5.5, 4.8, [
        ("PageRank and degree correlate at ρ = 0.53 — related, not the same", 0),
        ("Top rank: Ku Feng, Simon Yam, Anthony Wong, Shih Kien, Eric Tsang, Francis Ng", 0),
        ("These are the people the industry's own histories name", 0),
        ("Several higher-degree performers do not appear", 1),
        ("They accumulated credits, not central collaborators", 1),
        ("Decade profile: the local bloc peaks before 1990, the mainland bloc after 2000", 0),
    ], size=13.5)
    note(s, "SPEAKER 3 (60 s). Make the analytical point, not the fan point: PageRank rewards repeated "
            "collaboration with hubs, so the ranking surfaces the industry's structural centre rather "
            "than its busiest performers. If asked 'isn't this just the famous names' — that is the "
            "result: the algorithm independently recovers the names film historians list.")

    # 7 ---------------------------------------------------------------- rules
    s = base(prs, "Rules validate the pipeline before they explain it", "6 · finding 3")
    picture(s, "fig09_rules.png", 0.62, 1.6, width=6.2)
    bullets(s, 7.1, 1.75, 5.7, 4.6, [
        ("652 rules at support ≥ 1%, confidence ≥ 0.6, lift > 1.2", 0),
        ("Strongest are structural: animation → adventure, lift 7.8", 0),
        ("Crew-role pairs above 2% support are the studio signature", 0),
        ("Technical roles travel together in assembly-line production", 1),
        ("Weakest after 2000 — the comparison is future work", 1),
        ("Career clustering (k = 8, silhouette 0.66) agrees with the graph ranking", 0),
    ], size=13.5)
    note(s, "SPEAKER 4 (55 s). Be honest that the top rules are unsurprising — that is the point: a "
            "pipeline that returns anything else would be broken. The interesting rules are the crew-role "
            "pairs in the middle of the distribution.")

    # 8 ---------------------------------------------------------------- close
    s = base(prs, "What we would do next, and what we would not", "7 · close")
    bullets(s, 0.62, 1.75, 6.0, 4.6, [
        ("Replace Apriori with FP-Growth", 0),
        ("moves the ceiling from the irregular phase to counting", 1),
        ("Get a country label from a dump, not a SPARQL endpoint", 0),
        ("removes the largest threat to validity", 1),
        ("Dynamic community detection instead of fixed-label flux", 0),
    ], size=14)
    bullets(s, 7.0, 1.75, 5.8, 4.6, [
        ("What we would not do again", 0),
        ("run PageRank in parallel at 10⁵ edges", 1),
        ("spawn a pool per stage", 1),
        ("trust a release-region filter as a production filter", 1),
        ("", 0),
        ("Reproducible: every number from one command", 0),
        ("python src/bench.py --exp all", 1),
    ], size=14)
    note(s, "SPEAKER 4 (55 s). Close on judgement rather than a summary: the three things we would change, "
            "and the three we would not repeat. End on the reproducibility line — if an examiner asks how "
            "a number was produced, the answer is a command, not a recollection.")

    prs.save(OUT)
    print("written:", OUT, "slides:", len(prs.slides))


if __name__ == "__main__":
    build()
