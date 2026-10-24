---
name: marketing-posts
description: "The editorial pipeline's job skill, run by marketing-post-writer: mine the owner's finished work, narrations and teaching for candidate posts that meet the content library's topic rule, pick the Run's posts, draft them in the public voice with a hidden source on every claim, and have marketing-reviewer check anonymity, voice and facts. Holds the Steps and the content DONE checklist; the shapes and sections are in marketing-content-workstream. Drafts only; nothing is published. Not for a case study (marketing-case-study) or editing one draft (unslop-editorial)."
---

# Marketing posts

One content Run: a refreshed candidate list and the Run's posts drafted, sourced, anonymized and checked, ready for the owner to trim and publish. `marketing-content-workstream` holds the conduct, the shapes and the sections the Steps name; load it, `orchestration-workstream` and `unslop-editorial` first.

## Inputs

- **Marketing rules** (required): `MARKETING-RULES.md` from the marketing Context; it names the content library, the topic rule, the cadence, the sources agents may mine, the voice file and the client list. It wins over this skill.
- **Count** (optional): posts to draft. Default: the rules' cadence (usually one).
- **Topic** (optional): a candidate id or a topic. Default: the best candidate.
- **Instructions** (optional): override the defaults, never the rules.
- **Dry run**: candidates only; draft nothing.

## Steps

1. [judgment] Orient. Read the rules, the content library and the last Run's `candidates.json` if the rules name a working folder that holds one.
2. [judgment] Mine candidates, by section Mine candidates, into RUN/candidates.json.
   → dry run: step 7
3. [judgment] Pick the Run's posts: the owner's topic, else the candidates that best meet the topic rule with the lowest identification risk, lane rotation as the rules say. Record why in RUN/plan.json.
4. [hand-off: marketing-worker] Draft: with two or more posts, one worker per post in parallel, told to follow section Draft a post, with the rules' path, the candidate row, its sources, the voice file and `RUN/drafts/`. With one post, draft it yourself by the same section.
5. [hand-off: marketing-reviewer] Check, in parallel: one reviewer on section Check a public draft with the drafts, the rules' path and the client list; one on the `review-facts` checklist with each draft's claims and their sources (two reviewers on disjoint halves when the sources are many). Never pass the writer's notes.
   → a FAIL, first round: step 6 (max 1)
   → all PASS, or a second FAIL: step 7
6. [judgment] Revise on the findings, by section Revise on findings, then re-check the revised drafts only.
   → revised: step 5
7. [judgment] Write RUN/DONE.md, walking the DONE checklist below with evidence per item, and report: the drafts with their paths, channel, length and verdicts; the top candidates with their lane and source; anything parked for risk; the questions as one numbered list.
   → reported: done

## DONE: a content Run

1. The candidate list holds at least the rules' number of ideas, each with a source or marked a general teaching point, and each meeting the topic rule.
2. The Run's drafts exist with a hidden source on every claim about real work.
3. `marketing-reviewer` on Check a public draft says PASS on anonymity, voice and length for each draft.
4. `marketing-reviewer` on `review-facts` finds every sourced claim VERIFIED, or the claim was removed.
5. Nothing was published, scheduled, uploaded or sent (cite the Run folder as the only output).
