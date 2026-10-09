# Claim ledger and open questions

The document that travels with any diagram, memo or readout that makes factual claims about a client. Every number and mechanic traces to a first-person source or it comes off the artifact. Produced by the `fact-check` agent and the `process-flow-workstream` skill, consumed before every client review. In a process-flow Run, `python3 ~/.claude/skills/process-flow-workstream/scripts/claim_ledger.py memo` writes this shape as `VERIFICATION v<N>.md`.

```
# <Artifact name>: Verification and Open Questions, v<N>

## 1. Claim ledger, every claim on the artifact and its final sourcing

| Claim | Primary source |
|---|---|
| <the claim as it appears on the artifact, with its number> | **<Source type> [<timestamp or page>] <Speaker or author>:** "<verbatim quote>" |
| <claim> | **Secondary:** <document>, <location>. Not yet confirmed by a first-person source. |
| <claim> | **CONTRADICTED:** <source A> says X; <source B> says Y. Shown as X pending <who> |

## 2. Corrections applied since v<N-1>

- <what changed on the artifact, why, which source forced it>

## 3. Caveats

- <numbers that rest on a secondary source, estimates the client gave rather than
  measured, anything the reader should weight down>

## 4. Notable new facts not on the artifact

Facts the sources contain that the artifact does not show, with source and location.
Each one is either added in the next version or deliberately left off with a reason.

## 5. Open questions, prioritised

| # | Question, phrased ready to ask | Why it matters | Who can answer | Already answered? |
|---|---|---|---|---|
| 1 | | | | no / **yes, see <source>** |

## 6. Source inventory

| Source | Type | Date | Read in full? |
|---|---|---|---|
```

Rules:

- A claim with no quote is not verified, whatever the checker remembers.
- Secondary-sourced numbers stay on the artifact only with a visible caveat.
- A contradiction is recorded, not resolved; the author decides which to show and the ledger says so.
- When a new primary source arrives, the ledger is diffed against it (changed verdicts and new facts only), not rebuilt.
- The open-questions table becomes the agenda for the validation session; a question the sources already answer is cited, not asked.

## Tie-out ledger

When the claims are the same figures quoted across several reports, use the tie-out ledger of the `report-tieout` skill instead.
