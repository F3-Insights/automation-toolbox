---
name: marketing-case-study
description: "The case study's job skill, run by marketing-case-study-writer: from a closed engagement's closeout and files, a short, sourced, anonymized story of the situation, the work, what changed and the lesson, checked by marketing-reviewer for anonymity, facts and a prospective buyer's read, and marked internal until the owner records the client's consent. Holds the Steps and the case-study DONE checklist; the shapes and sections are in marketing-content-workstream. Nothing is published and no client is contacted. Not for regular posts (marketing-posts)."
---

# Marketing case study

One case study from one closed engagement, ready for the owner to ask the client's consent and publish. `marketing-content-workstream` holds the conduct, the shapes and the sections the Steps name; load it, `orchestration-workstream` and `unslop-editorial` first.

## Inputs

- **Marketing rules** (required): `MARKETING-RULES.md` from the marketing Context, its consent register above all, and the voice file. It wins over this skill.
- **Engagement** (required): the engagement's name; its folder (under the setting `engagements_dir`, or its own Context) holds the closeout and deliverables. The closeout's `Case Study <date>.md` draft, when there is one, is the starting point: projects' engagement closeout leaves it as a file and names this job as the owner's next launch.
- **Instructions** (optional): override the defaults, never the rules.
- **Dry run**: confirm the engagement is closed and list the sources; draft nothing.

## Steps

1. [judgment] Orient. Read the rules and the engagement's folder. The engagement must be closed by the rules' definition, with a closeout to cite; if not, stop with that as the question to the owner.
   → not closed, or no closeout: stop
   → dry run: step 6
2. [judgment] Consent. Look the engagement up in the rules' consent register. None: the draft will be internal, and the consent request becomes a question to the owner (never drafted to the client).
3. [judgment] Draft the case study, by section Draft a case study, into `RUN/drafts/`.
4. [hand-off: marketing-reviewer] Check, in parallel: one reviewer on section Check a public draft (the draft, the rules' path, the client list); one on the `review-facts` checklist (the draft's claims and the engagement's files); one on the `review-red-team` checklist (the draft only, a prospective buyer as reader, one line of purpose). Never pass the notes.
   → a FAIL, first round: step 5 (max 1)
   → all PASS, or a second FAIL: step 6
5. [judgment] Revise on the findings, by section Revise on findings, then re-check.
   → revised: step 4
6. [judgment] Write RUN/DONE.md, walking the DONE checklist below with evidence per item, and report: the draft's path and whether it is internal, the verdicts, the claims removed, and the consent question and any other decisions as one numbered list.
   → reported: done

## DONE: a case study

1. The engagement is closed by the rules' definition, and its closeout is cited.
2. The draft has the four parts, each sourced to the engagement's files.
3. Consent: the rules record the client's written consent for this piece, or the draft is marked `INTERNAL: not for publication until consent` and the consent request is a question to the owner.
4. Without consent, `marketing-reviewer` on Check a public draft says PASS on anonymity; with consent, it checks only what the consent covers.
5. `marketing-reviewer` on `review-facts` finds every claim VERIFIED; on `review-red-team`, reading as a prospective buyer, no section is below the bar without a fix applied or reported.
6. Nothing was published or sent, and no one outside the owner was contacted.
