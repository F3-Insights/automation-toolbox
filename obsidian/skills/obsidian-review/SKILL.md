---
name: obsidian-review
description: "The checklist a fresh obsidian-worker follows to judge vault changes it did not make (today the curator's change set: splices, link, frontmatter and fact fixes, moves, merges, conflict callouts), from the notes alone and never the maker's reasoning, returning PASS or FAIL per change. Read-only. Dispatched by the obsidian-curate Run; not for a user request."
user-invocable: false
---

# Reviewing vault changes

You judge changes someone else proposed, so nothing wrong or lost reaches the owner's vault. Load `obsidian-search` first and keep its rules. You are read-only: write nothing, in the vault or anywhere else, and never fix a change yourself.

## Inputs

- The change set's path (`RUN/proposals.json`), and the vault map's when there is one. The vault rules are the setting `vault_rules`. If the brief carries the maker's reasoning or summary, set it aside.

## The checks

Read every target and source note yourself with `obsidian-vault-read` and `obsidian-vault-links`. For each change:

1. **splice**: every added line is in the source note word for word, apart from a `(from [[...]])` line or a callout; the target does not already say it; the heading fits what the text is about.
2. **replace**, kind `link`: the new link resolves to the note the old one meant, read in context. Kind `frontmatter`: each key and value is what the vault rules and the note's content give. Kind `fact`: the cited newer note states the new fact, dated later, and the old text survives struck through.
3. **move**: the note's content fits the destination by the vault map better than where it is, and no link names it by path.
4. **mark_merged**: everything the inbox note says is in `into` or in a splice of this change set. Nothing is lost.
5. **callout**: the two notes do disagree, and the quoted claims are theirs.

A check you could not make is a FAIL that says why. PASS only when a careful owner reading the same notes would agree.

## Return

One json block and nothing after it:

```json
{"verdicts": [{"id": "c1", "verdict": "PASS", "why": "<one line>"}]}
```

Every change id gets a verdict.
