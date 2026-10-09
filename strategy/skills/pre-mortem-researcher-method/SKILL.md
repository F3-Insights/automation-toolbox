---
name: pre-mortem-researcher-method
description: "Reference loaded by the pre-mortem-researcher agent, not for a user request: the step-by-step procedure for gathering sourced external evidence on a strategic initiative, from reading the plan, through four to six plan-specific queries and searches that favour primary, recent and comparable sources, to writing research.md and returning a summary. Not for running the pre-mortem itself; use the pre-mortem skill. Not for surfacing the plan's assumptions; use pre-mortem-investigator-method."
---

# Gathering external evidence for a pre-mortem

This is the procedure the `pre-mortem-researcher` agent works through, in order. The agent file holds the goal, the judgment, the rules and the exact structure of `research.md`; this skill holds the steps.

## What you do

### Step 1: Read the plan

Read the plan and confirm the decision category. Note the geography, time horizon, capital scale, and any named external entities (competitors, customers, suppliers, regulators).

### Step 2: Generate 4 to 6 research queries

Queries should be specific to the plan. Examples for a geographic-expansion initiative:

- Recent multi-state expansion case studies in <industry>
- Regulatory differences between <origin state> and <target state> for <industry>
- Comparable companies that opened a second facility in <target state> in the last 5 years
- Labor market data for <target metro area>: <industry> operator wages and availability
- Recent customer concentration trends in <target region>

Avoid generic queries like "is expansion risky" or "how do companies handle growth." The point is to gather evidence specific to *this* plan.

### Step 3: Execute the searches

Run each query through `WebSearch`. Scan the results for promising sources. For sources that look substantive, fetch the full content via `WebFetch`. Look especially for:

- Primary sources (regulatory filings, company press releases, industry reports)
- Recent data (last 3 years, ideally last 12 months)
- Comparable cases (not "experts say X" but "Company Y did X and Z happened")

Skip:

- Blog content from generic business publications
- LinkedIn thought-leadership posts
- Vendor-sponsored content masquerading as research

### Step 4: Write research.md

Output structure: the `research.md` template in the agent's Output section, exactly.

Aim for 5 to 8 findings. Fewer if the searches don't turn up substance; more is usually padding.

### Step 5: Return a summary

Tell the orchestrator: how many findings you produced, what sources they came from, and where the file lives.
