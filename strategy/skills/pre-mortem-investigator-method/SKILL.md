---
name: pre-mortem-investigator-method
description: "Reference loaded by the pre-mortem-investigator agent, not for a user request: the step-by-step procedure for surfacing a strategic plan's assumptions before a pre-mortem, from reading the plan, its quant inputs and the whole company knowledge base, through tagging assumptions stated, implied or missing across five categories, to writing the gate-1 file and returning a summary. Not for running the pre-mortem itself; use the pre-mortem skill. Not for gathering external evidence; use pre-mortem-researcher-method."
---

# Surfacing a plan's assumptions

This is the procedure the `pre-mortem-investigator` agent works through, in order. The agent file holds the goal, the judgment, the rules and the gate-1 file's exact structure; this skill holds the steps.

## What you do

### Step 1: Read everything

Read the plan in full. Read the quant inputs. Read every file in `context/`. Spend the time. The quality of your surfacing depends on knowing the company.

### Step 2: Identify assumptions in five categories

For each assumption you identify, tag it with one of three states:

- **STATED**: explicitly in the plan
- **IMPLIED**: present in the plan but not made explicit
- **MISSING**: not in the plan but the plan depends on it

The five categories:

1. **Market assumptions.** What about competitors, customers, demand, pricing, or geography is being taken for granted?
2. **Operational assumptions.** What does the plan assume about execution capability, team capacity, process scaling, or technology readiness?
3. **Capital and timing assumptions.** What does the plan assume about money flow, payback timing, capital availability, or interest-rate environment?
4. **Cultural and organizational assumptions.** What does the plan assume about how people will respond, how culture scales, who will drive what, or change-management capacity?
5. **Counterfactual assumptions.** What alternative paths are being implicitly rejected without being named?

### Step 3: Write the gate-1 file

Write to the output path specified in your prompt. Structure: the gate-1 file template in the agent's Output section, exactly.

### Step 4: Return a summary

Return a brief summary to the orchestrator: how many assumptions you flagged in each category, how many clarifying questions you wrote, and the path to the gate-1 file.
