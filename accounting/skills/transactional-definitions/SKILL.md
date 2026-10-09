---
name: transactional-definitions
description: Maintain and apply a client's transactional definitions, the rulebook saying which account, department, location and class a transaction takes and why. Read it before recommending any coding, cite the rule, escalate conflicts to the owner instead of guessing, write the answers back as new rules, and queue process-improvement proposals without applying them. Use for "how should this be coded", or when a close, JE draft, reclass or chart-of-accounts question needs a coding decision. For a queue of such questions, start accounting-questions-orchestrator.
argument-hint: "[client] [lookup <transaction> | escalate | propose | write-back]"
allowed-tools: Read, Glob, Grep, Write
---

# Transactional definitions

Every client's ledger has a rulebook, usually in three people's heads. This skill keeps it in one file per client, `transactional-definitions.md` in the client's close workspace, and governs how an agent uses it. The file's content is client data and never enters this repository; the protocol and the schema are what this skill carries.

## The protocol, in order

1. **Read before recommending.** Before proposing an account, department, location or class for any transaction, read the client's definitions file in full. A recommendation made without it is a guess, and the skill says so rather than making it.
2. **Cite the rule.** Every coding recommendation names the section and rule it rests on: "SG&A > Professional fees, rule 3: legal retainers by entity." If no rule covers the case, say "no rule covers this" and go to step 3.
3. **Escalate conflicts, do not resolve them.** When two rules disagree, when the ledger history contradicts a rule, or when no rule exists, the case goes to the **Escalations** section with the evidence (JE ids, amounts, dates) and the two or three plausible codings. The owner decides.
4. **Write the answer back.** When the owner answers an escalation, the answer becomes a rule in the right section, dated, with the escalation it resolved. The escalation row is marked resolved, never deleted.
5. **Propose, never apply.** Process improvements (a new class dimension, a department split, a vendor default) go to the **Proposals** queue with the problem, the change, what it would fix, and what it would cost. Nothing is applied until the owner marks it approved, and even then a person makes the ledger change.

## The file shape

```
# <Client> transactional definitions (accounts, departments, locations, classes)
Evidence window: <ledger postings from> to <to>. Last owner review: <date>.

## Departments            what each drives (e.g. COGS versus SG&A twins), with the rule per department
## Locations              usually legal entities; which flows post where
## Classes                business line or product; which rows carry them
## Coding rules already stated     numbered; each with its source in parentheses (who, when, or which document)
## Escalations for the owner       numbered; evidence, options, status (open / resolved <date>)
## Process improvement proposals   numbered; problem, change, fixes, costs, status (queued / approved / declined)
## Account definitions
### Balance sheet · ### Revenue · ### Cost of sales · ### SG&A · ### Below EBITDA
                          one entry per account: number, name, what belongs, what does not,
                          the vendors or customers usually seen, the rule numbers that touch it
```

## Modes

- **`lookup <transaction>`**: return the coding and the rule citations, or "no rule covers this" plus a drafted escalation row.
- **`escalate`**: list open escalations with their evidence, ready for the owner to read in one screen.
- **`propose`**: add a proposal row from a described problem; never change the ledger.
- **`write-back`**: given an owner's answer, add the rule and resolve the escalation.

## Rules

- Definitions describe what the ledger *should* do; ledger history is evidence for a definition, not a definition.
- Vendor and customer names in the file are fine; they are the client's own data in the client's own workspace.
- A coding principle that would hold for any client is noted for the owner as a general practice, not written into one client's file.
