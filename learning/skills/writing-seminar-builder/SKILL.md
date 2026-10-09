---
name: writing-seminar-builder
description: Build business-led AI seminars and other executive teaching decks as self-contained HTML from this skill's presentation library. Use when the owner wants to develop a seminar, webinar, talk, workshop deck, hands-on lab or speaking session, has a "seed idea" or "topic for a talk", or wants a concept turned into scripted slides for a business audience, even without the word seminar. Not for a client status deck (project-status-deck) or a workshop the room works through (workshop-design). Unattended, start learning-seminar-orchestrator.
---

# Seminar Builder

Turn a seed idea into a self-contained **HTML** seminar that renders as both a click-through slide deck and a scroll/editorial page. Output goes to `Content/Seminars/<slug>/index.html` in the training folder (see "The training folder" below), with a `_content-map.md` beside it and the speaker scripts embedded as `<aside class="notes">`.

## The training folder (setting `training_dir`)

Seminars live in one training folder per practice: the `training_dir` setting, or a folder the caller names. With neither, say what is needed and stop. This is the only place the layout is defined; every other mention of "the training folder" in this skill and its `presentation/` and `references/` files means this layout.

```
<training_dir>/
├── CONTEXT.md               ← optional: the practice's voice and its service offers
├── Content/Seminars/
│   ├── _catalog.md          ← one line per seminar, checked so a new one duplicates nothing
│   └── <slug>/              ← one folder per seminar (see "Output convention")
└── Resources/presentation/  ← a copy of this skill's presentation/ folder
```

A seminar links the deck kit through that copy as `../../../Resources/presentation/deck-kit/...`, which is why the paste-ready markup in `presentation/elements/` uses that path. Copy the folder there if it is missing. `CONTEXT.md` is optional; skip it for a client's deck.

## The audience (setting `audience`)

Every seminar is written for one audience: the `audience` setting, or the audience the caller names for this deck, which wins. It is a sentence the owner writes, for example "finance leaders at mid-sized companies" or "operations heads at regional hospitals". With neither, ask for it in step 1 before anything else. Wherever this skill and its `presentation/` and `references/` files say "the audience", "the target audience" or "this audience", they mean this one, and the scale of every number and example is calibrated to it (`presentation/learnings/_universal.md`, "Audience calibration").

The first-person habits in these files (the presenter's own examples, "I built", "I watched this fail") are defaults for whoever presents, not one person's style; the presenter's voice guide wins where it differs.

## What to read

This skill is an **orchestrator**. The rules, the visual system, and the reusable parts live in this skill's `presentation/` folder and are the source of truth. Read them; do not restate or fork them here.

| What you need | Where it lives (read before building) |
|---|---|
| Visual + animation system, QA | `presentation/DESIGN-PRINCIPLES.md` |
| Deck strategy for this deck's purpose | `presentation/learnings/` (`_universal` + training / consulting / financial-data) |
| Which slide type fits each beat | `presentation/slide-types/_INDEX.md` |
| Paste-ready visuals (the elements) | `presentation/elements/` |
| CSS/JS/icons to link | `presentation/deck-kit/` |
| Voice (canonical / operational) | the training folder's `CONTEXT.md` when it has one (see "The training folder"), the owner's voice guide (setting `voice_guide`), and the `brand-guide` skill's voice and tone |
| Delivery voice (how the notes should sound) | `references/teaching-style.md` |
| The closing offer (no prices) | `references/closing-offer-menu.md` |
| Story-gathering questions | `references/interview-questions.md` |
| The per-deck content map and the series template | `references/deck-content-map.md` |
| The one-hour hands-on lab | `references/hands-on-lab-kit.md` |

## Core philosophy

- **Business value leads; AI is the means, not the message.** Open and close in language an executive would use if AI didn't exist.
- **Teach the principles; hold the implementation.** Armed, not handed a kit (the give/hold line in `presentation/learnings/training-decks.md`).
- **Series consistency.** The signature framework figure recurs; the voice is locked. Variety comes from matching the right slide *type* to each beat, not from breaking family coherence.

## The workflow

Work through these in order; do not skip ahead.

1. **Gather + interrogate.** Read `references/interview-questions.md` as a question bank and `presentation/learnings/_universal.md`. Ask what the user is bringing (topic notes / a prior transcript / a bare seed idea). For a **training deck, open with the two scope-defining questions and get the user to agree on both, especially (b):**
   - **(a) Assumed knowledge.** What does the audience already know, and what assumptions do they walk in with?
   - **(b) Expected outcomes.** What should they understand or be able to do by the end? **(b) defines the scope of the deck, so lock it explicitly.**
   - **(c) The material only the presenter has.** What have they built, watched fail, or lived through on this topic? Harvest at least one first-person example (with the real artifact or number) and one named friction ("here's where teams get stuck") before designing. These become **on-slide** worked examples and the framework's setup (`presentation/learnings/training-decks.md` #12–13), not just spoken color. If they have none for this topic, flag it: the deck will read as AI-generated without it.

   Then keep **asking framing questions until you reach full alignment** on the substance and the through-line (no fixed count; probe vague answers). Establish the **purpose** (teaching / consulting / financial / **lab**) and **length**, neither hardcoded. Wait for answers before designing.

   **Lab is the fourth purpose:** a one-hour hands-on session where the room leaves with something working. Its shape is `references/hands-on-lab-kit.md`, not the arc below: the deck is a **hold-slide deck** (one slide per checkpoint carrying the "you're done when" gate and the exact clicks, a hold slide between them, the one framing block as the only lecture slide), and the deliverable is four files, not one: run of show, participant handout, prework note, deck. For a lab, (b) is written as the three checkpoints' done-conditions; skip steps 2, 3 and 5 below (no story arc, no outline gate, no offer), build the deck in step 4 from the template's block list, verify in step 6, and red-team in step 7 with one question only: "could a participant who missed the spoken track still pass every gate from the handout and the slides?"

2. **Load the matching guide, then write the story.** First read the `presentation/learnings/` doc that matches the stated purpose (`training-decks` / `consulting-decks` / `financial-data-decks`), on top of `_universal.md`. Then produce the per-deck `_content-map.md` (shape in `references/deck-content-map.md`): the one-sentence spine, the arc the guide prescribes (Setup → Meat → Close for teaching, SCQA for consulting, insight-first for financial), and **each beat's job** (one line per slide). For a training deck, record (a) and (b) at the top of the content-map.

3. **Outline + slide-type selection, then GET APPROVAL.** For each beat, pick the slide **type** from `presentation/slide-types/_INDEX.md` (match the beat's job to a purpose category, then the type whose trigger fits). **Check the pattern budget before presenting** (DESIGN-PRINCIPLES §1B): at most one card grid in the deck, no layout shape more than twice, density varied (at least one near-empty slide and one dense artifact slide). If the outline converges on the same shapes the last deck used, rework it; the idea picks the form. Present the outline to the user as a table: each slide's job + the idea's shape + its chosen type. **Get the user's explicit approval of this outline before building any HTML.** Do not skip this gate.

4. **Build the HTML.** Copy an existing seminar's `index.html` as the scaffold, link `presentation/deck-kit/` through the training folder's copy (path in "The training folder"), and compose each slide from the paste-ready markup in `presentation/elements/`, reusing `deck-kit` primitives. Follow every hard rule in DESIGN-PRINCIPLES, especially: **action titles** (each title is a specific takeaway that reads as a through-line, never a catchphrase, §1A); **no catchphrases or salesy lines anywhere** (the gold sub-line must be a real takeaway or be cut); **labels name the thing** (no "a prompt" / "a skill"); **≤ 3 presses per slide, revealed in the idea's own order** (§6.7); titles and hero emphasis-words run large (§3.2); no em-dashes; one gold accent; no prices; **on-slide text in the operator's-memo register and every meat slide passing the silent read** (§1B, §8: a number, named example, decision rule, or artifact on the slide itself). Embed speaker notes per slide as delivery cues (`references/teaching-style.md`); the notes never restate the slide and never carry value the slide should hold (training-decks #12).

5. **Close with the offer.** Build the offer slide from `references/closing-offer-menu.md` (name the service, never a price).

6. **Verify.** Drive the deck in Playwright: press through every build, screenshot the final state, and measure for overflow, one-line headlines, and alignment per DESIGN-PRINCIPLES §9. Fix, then re-verify.

7. **Executive red-team, then revise.** Spawn a second agent (the Agent tool) to critique the deck as a skeptical senior executive in the target audience. Give it the deck to experience as the audience would (the scroll view, slides plus the speaker notes as the spoken track) and nothing of your own reasoning. For a **training deck, tell it (a) the audience's assumed knowledge and (b) the expected outcomes, and require it to answer the formal question: "starting from (a), did this deck actually deliver (b)?"**, naming exactly where (b) falls short. Otherwise tell it only the one-line purpose. Either way, ask for nuanced feedback on how effectively the content lands and on the presentation (where it is unconvincing, unclear, condescending, over-claimed, or buried). **Explicitly have it hunt for catchphrases and salesy language**: any title, sub-line, or body line that sounds clever but is empty, or reads as a pitch rather than insight. Flag each as a defect to rewrite into a real takeaway. A title that is a topic label rather than a conclusion is also a defect. **Also have it judge whether the deck reads as AI-generated**: all definition and no demonstration, generic enough that the audience could have gotten it from an article. Require it to confirm the deck *earns the non-obvious* (`presentation/learnings/training-decks.md` #11): one real artifact or wired system, one number or lived example, one expert "what everyone gets wrong" insight, and one personal Monday-morning action, and to name every slide that is pure taxonomy with nothing to *do*. **Run the silent-read test first:** give the red-team the scroll view *without* speaker notes and ask what it learned and what it would do Monday; value that exists only in the notes is a defect of the slide. **Have it hunt uniformity and the AI tells** (§1B, §8, training-decks #13–14): slides interchangeable with another deck in the series; peer sets in perfect parallel grammar; category nouns where a named instance belongs; a framework introduced with no named friction; jargon with no plain-English translation at first use; option grids with no starred first move; a "Monday move" too big for a Monday. Then loop back: triage, edit the HTML, re-verify (step 6), and repeat until the objections are resolved, the deck earns the non-obvious, and the "did you learn (b)?" check passes.

8. **Present the result.** Once the deck is done, give the user the local link to view it (`http://127.0.0.1:8765/Content/Seminars/<slug>/`), starting the preview server if it isn't running.

## Revising an existing deck

When the input is an existing deck plus feedback (a delivered-session note, "it felt generic," a specific audience reaction), skip the interview (step 1) and the outline gate (step 3). Read the deck, then **diagnose the current slides against the failure modes**, especially the "earn the non-obvious" bar (`presentation/learnings/training-decks.md` #11) and the catchphrase / topic-title defects. Propose the targeted changes (what to cut, replace, or add, and why), then build them (step 4), verify (step 6), and red-team only the changed slides (step 7). Keep the deck's working spine; change the minimum that resolves the feedback.

## Output convention

```
<training_dir>/Content/Seminars/<slug>/
├── index.html        ← the deck (source of truth)
├── _content-map.md   ← the per-deck story (step 2)
└── (legacy build_deck.py / .pptx may coexist as a record; HTML is current)
```

## If a needed visual doesn't exist yet

Check `presentation/slide-types/_INDEX.md` for its status. If the element is not yet built, either compose it from existing primitives, or add a new element: build the CSS into `deck-kit/`, document it in `presentation/elements/<id>.md` (paste-ready), and mark it coded in the index, so the next deck can reuse it. Verify the new element in Playwright before relying on it.

## Run by learning-seminar-orchestrator

`learning-seminar-orchestrator` runs this workflow in passes, so no one has to sit in the session. The method above is unchanged; only who asks and who red-teams moves.

- **Outline pass** (steps 1 to 3). Read what the owner brought (the seed, notes, a prior transcript) and the seminar catalog (`_catalog.md`, see "The training folder"). Write `_content-map.md` and the outline table, then `questions.md`: the scope questions (a) and (b), the material only the presenter has (c), every figure the deck would show (the owner approves each), and the outline itself for approval, all as one numbered list with a recommended answer each. Stop.
- **Build pass** (steps 4 to 6). Only with the owner's answers and their approval of the outline in the brief. Record (a) and (b) at the top of `_content-map.md`, build, verify in Playwright (open `index.html` by its `file://` path; screenshots into the Run folder).
- **Red team** (step 7). The orchestrator, not the builder, dispatches `executive-red-team` with the scroll view, (a) and (b), and nothing of the builder's reasoning; the builder then revises and re-verifies. At most two rounds; what is still open goes to the owner.
- **Revise pass.** The "Revising an existing deck" section, with the feedback from the brief.
- **Dry run.** The deck is built in the Run folder, never under `Content/Seminars/`.

### DONE (the orchestrator checks each item and cites its evidence)

1. (a) assumed knowledge and (b) expected outcomes are recorded in `_content-map.md` from the owner's answers, not from the builder's guess.
2. At least one first-person example and one named friction are on slides, or their absence is a question to the owner.
3. The owner approved the outline (cite the answer); the build matches it or says where not.
4. Playwright pressed every build: no overflow, one-line headlines, screenshots saved.
5. The red team's silent-read test and "starting from (a), did this deck deliver (b)?" passed, with no open catchphrase, salesy or topic-title defect.
6. No prices, no em-dashes, and every figure on a slide is one the owner approved.
7. The seminar duplicates nothing in `_catalog.md`; its catalog line is proposed, not written.

### Later tools

- `seminar-check`: compute items 4 and 6 from the HTML (overflow report, em-dash and price scan, figures against the approved list).
