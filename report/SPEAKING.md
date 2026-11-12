# Presentation pack — 4 minutes, 4 speakers

The brief: 4 minutes of speaking, 1 minute of questions, every member speaks. The deck is 8 slides; each speaker owns two.

| Time | Speaker | Slides | What they must land |
|---|---|---|---|
| 0:00–0:35 | 1 | 1–2 | The question, and the fact that IMDb has no country field. Open with the question, not with "our project is about…" |
| 0:35–1:00 | 1 | 2 | The three filters and their three answers: 26,000 / 15,700 / 0. Then the decision. |
| 1:00–1:30 | 2 | 3 | Three workloads → three strategies, and why process pool rather than threads (the GIL). |
| 1:30–2:00 | 2 | 4 | The three numbers: 6.8×, 4.5×, ~1.4×. One sentence of reason each. |
| 2:00–2:30 | 3 | 5 | Blocs emerge without labels; Q = 0.77, NMI = 0.89; label propagation fails at 0.08. |
| 2:30–3:00 | 3 | 6 | Rank ≠ volume; the top six are the documented core. |
| 3:00–3:30 | 4 | 7 | Rules validate the pipeline; career clusters agree with the graph. |
| 3:30–3:55 | 4 | 8 | What we would change, what we would not repeat, one command reproduces everything. |
| 3:55–4:00 | 4 | — | Stop talking. Do not add a thank-you slide. |

## Rules that decide whether this scores

1. **Never read a bullet aloud.** The bullet is the evidence; the sentence is the claim.
2. **One number per slide, spoken slowly.** 6.8× at 16 workers. Then stop. Do not list all five.
3. **If you overrun, cut slide 7, never slides 2 or 4.** The data defect and the scaling curve are the two things an examiner will remember.
4. **Every speaker names the next speaker**, so the handover is not a silence.

## Questions to expect

**"Isn't 25,997 titles mostly foreign films? How can you call this a Hong Kong network?"**
The strongest question, and slide 2 is the answer. We do not call it a Hong Kong *production* network; no field in the release identifies production country, and we report the three definitions we tested. What we analyse is the release network, and the local industry enters it as the Cantonese-language bloc that the algorithm finds without a country label. Bloc membership is estimated from collaboration data, so conclusions about structure inside a bloc survive the weaker premise; conclusions about market share would not.

**"Why is your PageRank speedup so poor — is that a failure?"**
No, and the reason is measured, not asserted. At 478k edges an iteration costs about 1 ms, which is comparable to thread dispatch, and when we grew the graph sixteen-fold the speedup stayed near 2× rather than improving — so the limit is memory bandwidth on a sparse matvec, not synchronisation. Two different failure modes; we distinguish them with the E3c experiment.

**"Why not Spark / Dask / a cluster?"**
Because the binding constraint here is one machine's memory and the per-iteration dependency, not the volume of data. The scan tier at 6.8× on 16 cores already exceeds what a single-node Spark setup would give at this size, once JVM start-up and shuffle are counted. Say this only if asked; do not volunteer it.

**"How did you verify the communities are real?"**
Two ways. Cross-seed NMI of 0.89 — the partition is reproducible. And the membership is interpretable: the blocs correspond to cinemas that were never supplied to the algorithm. We do not claim the boundaries are ground truth; Louvain's resolution limit is visible in the sweep at 0.25, 0.5 and 1.0.

**"What is the contribution of each member?"**
Have the exact percentages ready and be able to name a concrete artefact for each — a module, a figure, a section. Vague percentages are the single fastest way to lose the individual score.
