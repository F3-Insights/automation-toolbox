---
name: playbook-ratification
description: Run the owner's ratification session over their playbook folder. Offers the next queue items and inbox proposals sized to the time they have, walks only the flagged bullets and conflicts as focused questions, records every verdict as it is given, and promotes a ratified draft into its function's playbooks, then rebuilds the index with playbook_index.py. Use for "let's ratify", "review the playbook proposals", "I have ten minutes for playbooks". Not for drafting a playbook; use playbook-distilling.
argument-hint: '[optional: the playbook or proposal to start with]'
allowed-tools: Bash(python3 ~/.claude/skills/playbook-ratification/scripts/playbook_index.py:*), Bash(git -C:*), Read, Write, Edit, AskUserQuestion
---

# Ratify playbooks

Run a ratification session against the owner's playbook folder (the setting `playbooks_dir`). Paths below are relative to that folder. A playbook is a short set of cited rules for how the owner decides one category of matter; ratified, it becomes the owner's rule.

The folder has a shared ratification pipeline (`_inbox/`, `verdicts/`, `voice/`, `policies/`, `meta/`) over playbooks grouped by business function (folders the owner chooses, such as `finance/` or `sales/`), each function holding up to `playbooks/`, `drafts/` and `briefs/`. A draft is ratified within its own function. `INDEX.md` is the authority on where any file sits. This is the verdict loop: the owner's scarce attention, spent only on the uncertain part, with every judgment kept.

## Session flow

1. **Orient, silently.** Read the ratification queue (the setting `ratification_queue`, by default `meta/RATIFICATION-QUEUE.md`; each item is tagged with its function), the folder's recent history if it is a git repository (`git -C <folder> log --oneline -5`), and the files in `_inbox/` (one queue for all functions). Build the menu: the next queue items, any inbox proposals, and any corrections not yet harvested. If the arguments name a playbook, go straight to it.
2. **Offer the menu.** Show three to five candidates with their estimated ratification time (from `meta/ratification-briefs/<name>.md`). Recommend one by queue order, foundational items first. Let the owner pick. Ask how many minutes they have and size the session to fit; a short session is one or two questions, in queue order, each answerable in about three minutes of dictation.
3. **Per playbook, brief first, not draft first.** Present the ratification brief (scope, strongest bullets, the check-closely flags). Then walk only the check-closely items and any conflicts as focused questions (a choice where the options are crisp; open discussion where they are not). Bullets with strong evidence and no flags are handled together: "the remaining N bullets are well evidenced; accept as written, or read them?"
4. **Record verdicts as you go.** Every decision (accept, edit, reject, carve-out) is appended to `verdicts/YYYY-MM.md` immediately, created from the template in `verdicts/README.md`. Edits to bullet text happen in the file as they are agreed. Never save verdicts for the end: a dropped session must lose nothing.
5. **Promote on completion.** When the owner ratifies a playbook:
   - move `<function>/drafts/<name>-playbook-draft.md` to `<function>/playbooks/<name>.md`, inside the function that owns it;
   - set its frontmatter `status: ratified v1.0, YYYY-MM-DD`;
   - tick it in the ratification queue;
   - rebuild the index: `python3 ~/.claude/skills/playbook-ratification/scripts/playbook_index.py <folder>`;
   - if the decision store holds this playbook, its status changes there only by the owner's own process; this session changes the files.
6. **Commit per playbook, not per session**, when the folder is a git repository: stage the files you changed by name and commit with a message naming the playbook and the verdict count. One playbook ratified is one commit, so the history stays readable.
7. **Close.** Report what was ratified, the verdicts recorded, and what is next in the queue with its estimated time. Do not press the owner to continue.

## Hard rules

- **Ratification is the owner's alone.** Never mark anything ratified without their explicit confirmation for that playbook in this session.
- **Never soften a conflict to speed the session.** Conflicts and thin-evidence flags are why the owner's attention is here.
- **Rejected bullets are recorded, not deleted silently.** A rejection is a rule too: it tells future distilling what the owner does not endorse.
- **A changed draft gets backtested** against the category's historical cases before it goes back in the queue (see `playbook-distilling`). Regressions are flagged for the owner, never applied on your own.
- **Partial sessions are fine.** A playbook can be left mid-review; note the progress in the queue file. Never rush the owner to finish because the session is ending.

## The index

`scripts/playbook_index.py` rebuilds `INDEX.md` from the frontmatter of every playbook, policy, draft and brief: ratified playbooks first, then policies, drafts and briefs, each function under its own heading. Headings and their order come from the optional table `function_labels` under `[playbook-ratification]` in the owner settings; a function folder with no label is listed under its folder name. An optional `meta/INDEX-FOOTER.md` is appended as written, for pointers to rules kept elsewhere.
