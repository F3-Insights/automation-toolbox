---
name: it-governance-workstream
description: Reference loaded by it-governance-collector, it-governance-tool-reviewer and it-governance-orchestrator, not for a user request; adds to orchestration-workstream. Covers controls from an approved policy library as checklist rows with an evidence file per period, evidence collected only against approved and effective controls, control and evidence states, the third-party AI tool review standard against the data-privacy policy, the annual policy refresh as a gap list, and the DONE checklist per mode.
---

# IT governance workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load that skill if it is not loaded. What follows is only what IT governance adds.

Three kinds of work share one folder: collecting evidence that controls operated (for SOC 2, HIPAA or whatever frameworks the rules name), reviewing a third-party AI tool before data goes into it, and the policy library's annual refresh. Agents find, index and judge; people export system evidence, approve policies and decide on vendors.

## The folder

The caller names one governance folder per entity:

- `GOVERNANCE-RULES.md`: the entity, the frameworks in scope, where the policy library lives and its approval state and effective date, who owns which control (roles), the evidence cadence, where system exports land, the vendor review form, the data-privacy policy for AI tools, and what an agent may write. It wins over this skill.
- `CONTROLS.csv`: the control register: `control_id, policy_ref, frameworks, frequency, evidence_expected, owner, effective_from`. The owner's file; agents propose changes.
- `{yyyy}/{period}/`: `STATUS.md`, `LOG.md` (the orchestrator's) and `evidence/INDEX.md`.
- `tool-reviews/<tool>/REVIEW-{yyyy-mm-dd}.md` and `policy-refresh/{yyyy}/GAPS.md`.

## The rule that comes first

Evidence is collected only for controls whose policy is approved and whose `effective_from` is on or before the period's start. A control that is drafted, pending approval or not yet effective is `not-effective` and gets no evidence row. A questionnaire answered "target state" is a claim to verify, never evidence.

## Control states (evidence mode)

| State | When |
|---|---|
| `evidenced` | An artifact from the period shows the control operated: a system export, a log, a signed review, a ticket, a training record |
| `partial` | Evidence covers part of the period or part of the population |
| `missing` | Due this period and nothing found; a request to the owning role |
| `exception` | The evidence shows the control failed (an access review not done, a terminated user still active) |
| `not-effective` | Policy not approved or not yet effective |
| `not-due` | Its frequency puts no occurrence in this period |

## Tool review standard (tool-review mode)

One review per tool and version of its terms. From the vendor's own published documents (terms, data processing addendum, security page, trust report) and the data-privacy policy, answer: what data would go in; whether the vendor trains on it or retains it and for how long; where it is processed; whether a business associate agreement or data processing addendum is available and signed; access control and single sign-on; subprocessors; certifications with dates; and a verdict: approved for which data classes, approved with conditions, or not approved. Cite every fact to a URL and access date; a fact not found is "not found".

## Policy refresh (policy-refresh mode)

`completeness-audit` compares the library with the reference model the rules name and returns the gaps; `fact-check` checks the library's factual claims against its citations. The output is `GAPS.md`: each gap with the policy section, the proposed change and its source. Agents never edit a policy.

## DONE checklist

The orchestrator checks the lines for the Run's mode; starred lines are confirmed by `compliance-evidence-checker`.

Evidence mode:
1. Every control in the register has a state for the period in `STATUS.md`.
2. * Every `evidenced` and `partial` control cites an artifact dated in the period.
3. * Every `exception` cites the artifact that shows it, and is in the owner's list.
4. Every `missing` control is a request to its owning role.
5. No evidence row exists for a `not-effective` control.

Tool-review mode:
1. Every question in the standard is answered with a cited source or "not found".
2. The verdict names the data classes and conditions, and the owner decides it.

Policy-refresh mode:
1. `completeness-audit` and `fact-check` both ran and `GAPS.md` answers each finding.

Every mode: nothing was sent to a vendor or a person, and no policy or register was edited.

## Later tools

- `governance-check --precheck`: controls with an occurrence due this period and no evidence row.
- `governance-record`: one row per control and period in an evidence CSV, never overwriting.
- An exporter per admin system (identity, endpoint, cloud) that drops dated evidence files.
