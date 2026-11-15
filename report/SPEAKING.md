# 汇报执行稿 — 4 人 × 60 秒

对应 `report/CS5488汇报/CS5488汇报.pptx`（8 页）。**每人 2 页、60 秒**，合计 4 分钟 + 30 秒缓冲。

每人只需要背自己那 4 句。但**交接句必须说出口**——卡壳几乎都发生在换人那两秒。

---

## 时间轴

| 时间 | 人 | 页 | 你负责的唯一数字 |
|---|---|---|---|
| 0:00–1:00 | **A** | 1–2 | 25,997 → 21,033 |
| 1:00–2:00 | **B** | 3–4 | 6.93× / 4.51× / 0.96× |
| 2:00–3:00 | **C** | 5–6 | Q = 0.75，ρ = 0.49 |
| 3:00–4:00 | **D** | 7–8 | 652 |

---

## A · 0:00–1:00 ｜ 提问 + 数据缺陷

> Film historians describe Hong Kong cinema as a small pool of people reused across thousands of
> films. We asked whether an algorithm given nothing but cast lists would find the same circles.
>
> There was a problem first. This dataset has no country field — filtering by release region gives
> twenty-six thousand titles, and it puts Brad Pitt inside the Hong Kong network. So we stopped
> calling it a production list, analysed the release network, and let the algorithm separate the
> cinemas.

**交接（必说）：** "That decision is what makes the next part measurable."

要点：不要解释项目背景，直接抛问题；"Brad Pitt" 这个词是让人抬头的钩子，说慢一点。

---

## B · 1:00–2:00 ｜ 三种策略 + 三个天花板

> Three workloads, three strategies. The scan is parse-bound, so it runs on a process pool — threads
> would be blocked by the GIL. PageRank partitions rows and synchronises once per iteration. Rule
> counting shards without locks.
>
> Same machine, same data: six point nine times, four point five times — and PageRank at sixteen
> workers is zero point nine six. Slower than serial. A tier that degrades under parallelism is a
> result, not a failure.

**交接：** "So the engineering gave us three ceilings. The network itself gave us something stranger."

要点：三个数字报完就停，不要逐个解释；0.96 那句要停顿，它是全场最反直觉的一句。

---

## C · 2:00–3:00 ｜ 两个发现

> No country label was supplied, and Louvain still separates the cinemas: modularity zero point
> seven five, stable across random seeds. The largest bloc, eight thousand people, is the Cantonese
> core — Simon Yam, Anthony Wong, Eric Tsang.
>
> Inside it, PageRank and degree correlate at only zero point four nine. The top names are the ones
> the industry's own histories put at the centre — not the busiest performers.

**交接：** "Which brings us to the check that everything else rests on."

要点：说人名时看观众，不要看屏；"no country label was supplied" 是本项目最硬的一句。

---

## D · 3:00–4:00 ｜ 验证 + 收束

> The rules come first as a check, not as a finding: six hundred and fifty-two, and the strongest
> ones are unsurprising on purpose. If a genre taxonomy produced anything else, the pipeline would
> be broken.
>
> What we would change: FP-Growth, a real country label, dynamic communities. What we would not
> repeat: parallel PageRank at this scale. Every number is one command away in the repository.

要点：最后一句说完就停，不要说"谢谢大家"再等掌声。超时的话，第 7 页整段（652 那句）可以直接删掉。

---

## 三个必答题（每人只需守自己那段，但都要知道答案）

**"PageRank 只有 1.8×，是不是白做了？"**
不是。四进程到顶，十六进程退回 0.96，说明这个规模下并行是负收益；但图放大十六倍后八线程仍只有
2.1×，所以上限是内存带宽，不是同步。能区分"该并行"和"不该并行"，本身就是结论。

**"2.6 万部里大部分是外片，还能叫香港网络吗？"**
我们从没称它香港出品网络。这份数据没有出品国字段，三种筛法分别得到 25,997 / 15,715 / 0，报告 §4.1
全写了。我们分析发行网络，本地工业以粤语板块的形式被无监督地找出来。

**"板块凭什么说是真的？"**
跨随机种子 NMI 0.89，可复现；成员可解释，粤语核心里是任达华、黄秋生、曾志伟；分辨率扫描
（0.25 / 0.5 / 1.0）也把划分如何随参数变化列出来了。

---

## 今晚怎么练

1. **只背自己那 4 句**，不看幻灯片。背到能连续说完不卡。
2. **两个人一组对接**：A 说完交接句，B 立刻接——练那两秒的衔接。
3. **整组连排两遍**，掐表。第一遍必超，第二遍砍形容词。
4. 目标：整段 **3:30**，留 30 秒。

## 明天到场 15 分钟

PDF 放映（`CS5488汇报.pdf`）→ 确认 16:9 → 从头翻一遍确认翻页速度 → 试翻页笔 → 计时器交给 D
（最后一个人，最清楚还剩多少时间）。
