# Financial & Data-Delivery Decks: Learnings

*How to build a deck whose job is to **make numbers tell a clear, defensible story** to a finance-literate executive audience. Read [_universal.md](_universal.md) first. For a finance-led practice this is home turf, so the bar for rigor is high.*

Use: board packs, monthly/quarterly reviews, variance analysis, ROI models, data-analytics findings, readiness-assessment scorecards.

---

## The job

The audience is numerate and skeptical. They want the **so-what of the number** first, the supporting detail second, and the ability to trust and trace every figure. A table is not a finding; the finding is what the table *means*.

---

## Principles

1. **Lead with the insight, not the table.** One highlighted insight per data slide (an action title that states it), with the supporting numbers smaller and in service. "Margin fell 3 pts on freight, not pricing" beats a grid of twelve rows the audience has to mine.

2. **Pick the chart from the message** (Zelazny). The message dictates the form:
   - *Delta / "why did it change"* → **waterfall (bridge)**, the default finance explain-the-change slide (revenue bridge, cost walk, margin walk).
   - *Change over time* → **line** (continuous) or **column** (discrete periods).
   - *Rank / which is biggest* → **sorted bar**.
   - *Part-to-whole / mix* → **100% stacked bar** (prefer over pie; pie only for a few parts that truly sum to a whole; never 3-D, never exploded).
   - *Relationship* → **scatter / bubble**.
   - *Size + mix together* → **Marimekko**.
   - *Status across many metrics* → **dashboard / KPI scorecard** with RAG.
   - *Capability / maturity* → **heatmap / Harvey-balls** assessment.

3. **One focal series; mute the rest.** Highlight the bar/line/point that carries the message; gray the comparators. Annotate the inflection point or the variance that matters. Don't make the audience find it.

4. **Data-ink discipline (Tufte).** Erase non-data ink: heavy gridlines, borders, 3-D, shadows, redundant legends. Every drop of ink should encode data. A clean chart reads as competence.

5. **Precision and traceability.** Every figure gets a source line and a clear period label. Reconcile to a single source of truth. State the basis (actual vs. forecast vs. budget; gross vs. net; currency). Round sensibly and consistently. A number you can't defend is worse than no number.

6. **Expose assumptions for any estimate.** Market-sizing, ROI, projections: show the build (top-down and bottom-up converging) and the key assumptions on the slide or one click away. Finance audiences trust the model they can interrogate.

7. **Variance is a story, not a variance column.** Frame deltas as cause → magnitude → so-what (bridge chart + one-line driver call-outs), not as a raw actual-vs-budget table.

8. **Honesty over flattery.** The house voice is the trusted advisor. Don't hide the bad number; contextualize it. (And per the house client-facing rules: name services, never prices, in any client-facing data slide.)

---

## Data slide types (Prove / Compare & decide)

big-number / stat · waterfall (bridge) · trend (line/column) · ranking (bar) · composition (stacked/100%) · scatter/bubble · Marimekko · comparison table (Harvey balls / RAG) · maturity-heatmap assessment · dashboard / KPI scorecard · market-sizing build.

---

## Diagram engine note

By design: **financial charts are bespoke SVG or a vetted chart primitive**, not Mermaid (Mermaid is for incidental flowcharts only). Charts must hit the data-ink bar; if a chart can't reach a professional standard in code, it becomes a framed slot for the real asset.

---

## Sources

Zelazny, *Say It With Charts* (message→chart) · Tufte (data-ink, chartjunk) · Minto (answer-first) · consulting data-viz practitioner guides (Umbrex, Analyst Academy).
