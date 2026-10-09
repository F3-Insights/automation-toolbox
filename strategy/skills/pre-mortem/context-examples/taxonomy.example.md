Fictional example.

# Meridian Decision Taxonomy

*Last revised: 2026-01. Owner: CEO and Engineering Partner.*

How we categorize strategic decisions, and which framing pattern the pre-mortem orchestrator applies by default. The category drives both which subagents run and which prior entries in `strategic-history.md` and `lessons-learned.md` are most relevant.

## Categories

| Category | Definition | Default framing | Capital threshold |
|---|---|---|---|
| **Capacity expansion** | New facility, major equipment, headcount above 10% of prior FY | Pre-mortem (primary) | Apply if ≥ $500k |
| **Geographic expansion** | Operating in a new state or region | Pre-mortem + red-team | Apply at any capital level |
| **Customer concentration shift** | Top-10 customer composition changes by >5%, or a single customer crosses 10% | Pre-mortem | Apply at any level |
| **Product line addition** | New SKU family, end-market entry, service line | Devil's advocate | Apply at any level |
| **Capital structure** | Debt issuance, equity raise, distributions above $1M, ownership change | Pre-mortem + devil's advocate | Apply at any level |
| **M&A** | Acquisition (any size) or divestiture | All three patterns, sequentially | Apply at any level |
| **Operational reset** | Major system change (ERP, MES, PLM, financial close) | Pre-mortem | Apply if ≥ $1M or ≥ 6 months |
| **Talent: senior** | Hiring or losing a partner-level, plant-manager-level, or top-15-engineer role | Devil's advocate | Apply at any level |

## Cross-cutting tags

A single initiative often belongs to multiple categories. The orchestrator applies all applicable defaults and runs them in order. Examples from the active question:

- **Texas expansion** = Geographic expansion + Capacity expansion → Pre-mortem (primary) + Red-team (secondary)
- **Acquiring a competitor** = M&A + (almost always) Customer concentration shift → all three patterns

## When this taxonomy gets revised

Annually, at the same review where `lessons-learned.md` gets curated. Categories that produced sharper critique stay; categories that produced noise get folded into adjacent categories or dropped.

## What's deliberately not a category

- "Operational improvements" below the capital threshold: these get a 30-minute conversation, not a pre-mortem.
- Sales pipeline decisions: sales is run by ops, not by the strategic-decision process.
- Marketing initiatives: Meridian doesn't run marketing initiatives that would meet the bar.
