# Idea notes: "Building a Software Factory that actually works"

- **Source:** "Building a Software Factory that actually works (Full Course)", G. Isenberg's
  YouTube channel, about 31 minutes: https://www.youtube.com/watch?v=_LCeJZFIsd4
- **Format:** Isenberg interviews a guest engineer (named in the auto-captions as "Ross Mike"),
  who shows his own setup on screen.
- **Notes taken:** 2026-10-11, from the video's captions. The transcript is kept beside this file
  for reference only and is not committed: the repository is public and the transcript is the
  creator's material. This summary is ours; quotes are short.

## The idea in one paragraph

A "software factory" is not a product or a special tool. It is a fixed workflow, written down as
a handful of markdown files (an `AGENTS.md` plus a few skills), that every coding agent follows
on every change: work in isolation, build to a code standard, prove the change works, then pass
an external review in a loop until it scores full marks. Only then does the person step in, and
their whole job is to look at the proof and press merge. The guest's claim is that this lets one
person run many agents on many features at once without the output becoming "slop", and that it
works with any model and any agent tool.

## The four stations

The guest calls them isolate, build, prove and ship. Isenberg recasts them as a physical
factory, and the guest says he may rename his to match.

| Station | What happens | The factory analogy |
|---|---|---|
| **1. Isolate** | Every feature starts in its own git worktree, branched fresh from `origin/main`. Never build on main. The worktree is cleaned up after the merge. | A custom order gets its own station so it can't disturb the rest of production. |
| **2. Build** | The agent writes the code while following a "code structure" skill: a service-layer architecture that a human developer, or another agent with no context, can pick up and understand. | The assembly line. |
| **3. Prove** | The agent must show that the change works, not just say so. An "evidence-driven testing" skill records the bug or the missing feature before, and the working version after, as video or screenshots. A "before and after" skill covers machines that can't record. When there is nothing visible, it writes tests and reports numbers instead (a page load that went from about 850 ms to about 60 ms). | Quality control. |
| **4. Ship** | The agent opens a pull request with the proof embedded in its description. An external code-review agent (he uses Greptile; he names CodeRabbit and Macroscope as alternatives) scores it out of five. Below 5/5, the agent goes back to Build, then Prove, then Ship, and waits for a new score. At 5/5, the person merges. | Out the door, with a feedback loop back to the line. |

## The decisions that shape it

- **Put the workflow in `AGENTS.md`, not facts about the code.** He argues most `AGENTS.md`
  files are useless because they describe what the code looks like, which the agent can read for
  itself. His holds only what the agent would not do on its own: the workflow.
- **The workflow lives in skills** (new feature, code structure, evidence-driven testing, before
  and after, the review loop). `AGENTS.md` sequences them.
- **One worktree per feature is the parallelism.** That is how he runs about 15 features at once
  across several terminal tabs.
- **Proof is the review artifact.** The person reviews screenshots, videos and numbers, not the
  diff. He admits he barely skims code now.
- **An outside reviewer sets the bar, and a number decides when to stop.** The review agent's
  confidence score is the exit condition of the loop, not the building agent's opinion of itself.
- **The loop runs on its own.** A failed proof or a low review score sends the agent back to
  Build without being told to. The skills are written so the agent can see that the criteria are
  not met.
- **Model and harness don't matter.** He shows Claude Code-style terminal sessions and Cursor
  Cloud agents, and says the same files work anywhere.

## What is surprising, or pushed hardest

- **"A software factory is literally just a bunch of markdown files."** He is openly critical of
  startups selling "software factories" as products, and adds that some startups are now "an
  agent with a couple markdown files".
- **Agents can't "pinky promise".** The strongest emphasis in the video is proof: agents
  sometimes claim work they didn't do, or think a fix worked without testing it. Evidence beats
  assurance, and he calls the proof step his favourite.
- **"It works" is not "it's written well."** One model's working code was reviewed by another,
  which found duplication, scattered functions and dead code. Hence a code-structure skill
  enforced during the build, not afterwards.
- **Most "my agent deleted my files" stories are a branching mistake:** several features worked
  on one branch, so one agent's change overruns another's. Isolation removes the whole class.
- **Reviewing proof works like scrolling stories.** Isenberg likens clicking through
  before-and-after screenshots to Instagram stories: bite-sized yes/no checks a non-technical
  owner can do.
- **It is what engineering teams always did,** a PR with a description, tests and a senior
  reviewer, now done by machines. Isenberg's framing: structure agents "more like a team".
- **A strong pitch for paid code review:** if real users will use the software, use a review
  agent. Several have generous free tiers.
- **The names admit they need work.** Both agree "isolate" is a poor name, and the guest plans to
  adopt Isenberg's factory terms. His skills are free, but he asks people to understand the
  process rather than "blindly copy" it.

## The repository behind it: michaelshimeles/skills

The guest's skills are public at https://github.com/michaelshimeles/skills (read at `4b72f46`,
2026-09-17). It is small: an `AGENTS.md`, six skills and about 4,200 lines in all, most of
them in two places, the review loop (455 lines) and the video recorder (a 1,344-line Python
script). It confirms the video's claim: the "factory" is markdown plus two helper scripts.

### What is in it

| Piece | Origin | What it does |
|---|---|---|
| `AGENTS.md` | his | The workflow as four "beats" (isolate, build, prove, ship), each naming a skill; multi-agent rules; a "completing a task" checklist; a stub of sections each repo should add (its commands, invariants, test setup). Meant to be dropped into any repo. |
| `new-feature` | his | Fetch, check open PRs for overlapping files and stop to ask if any, then make a uniquely named worktree and branch from `origin/main`, verify the branch, and install dependencies fresh. It notes that Claude Code and Cursor manage worktrees themselves, so some steps are skipped there. |
| `code-structure` | his | One pattern: actions decide the "why and when", a service layer owns the reusable "how". When to use it and when not, how to design a service function, a migration checklist and an anti-pattern table (god services, leaky services, over-abstraction). |
| `evidence-driven-testing` | his | The proof step. The agent drives the running app (computer use, or the cua-driver fallback, or a headless Playwright script) while a recorder captures the screen. The agent annotates each check as passed, failed or untested, and the annotations are burned into `evidence.mp4` with a `report.md` and `manifest.json`. The video and summary are posted to the PR and issue. Non-UI changes still owe evidence: numbers, output pairs, transcript excerpts. |
| `before-and-after` | vendored from Vercel Labs (PolyForm Shield 1.0.0) | Drives the `@vercel/before-and-after` CLI to capture two screenshots and print a PR-ready before/after table, uploading the images (to the public host 0x0.st by default). |
| `greploop` and `greploop-apps` | vendored from Greptile (MIT); the second is his variant | Trigger a Greptile review, fetch its confidence score and unresolved comments, fix them, resolve the threads, push, repeat until 5/5 with zero unresolved, up to 10 rounds. Works with GitHub, GitLab and Perforce. The variant uses a different trigger for PRs too large for the normal one. |
| `unslop` | vendored from Cursor's plugins (MIT), edited | Strips signs of AI writing from anything a person will read (commit messages, PR bodies, docs, comments). He edited its trigger so agents apply it without being asked. |

### What the code shows that the video didn't

- **The rules are mostly about agents sharing a repo.** No commits to main. One worktree and
  branch per task and per agent, never touching another's. A scope check against open PRs
  before starting. Only `--force-with-lease`. Regenerate lockfiles, never hand-merge them.
  Confirm a dev-server port is answering your own process. When unsure, "stop and report
  instead of guessing".
- **The agent never merges unless told.** It ends by presenting the PR URL; the person merges.
- **Evidence has rules against faking it.** The recorder's synthetic test source must never be
  passed off as the real app. The video must show the live session. A test that couldn't run is
  marked untested with its reason, never skipped silently. The report names the exact commit
  tested. A fix shows the old failure beside the new success.
- **Capture hygiene is in the skill:** maximize the window first, and never record secrets,
  tokens, customer data or payment details.
- **The review loop has a ceiling:** ten rounds by default, and it stops and reports if a review
  times out instead of acting on stale results.
- **"Writing for humans" is a fifth, unspoken beat:** `unslop` runs over every message, PR and
  doc the agent writes.
- **Little of it is his own code.** Two of the six skills are vendored, one is his variant of a
  vendored one, and the other three are short prose. The value is in the order and the
  insistence, not in tooling.
- **The video's "prove" step relies on computer use and FFmpeg.** The README spells out the
  recorder's needs (ffmpeg with libx264, an X11 or wlroots display, or macOS screen-recording
  permission) and the headless fallback.

### Licensing, if we borrow

- His own three skills and `AGENTS.md` carry **no license**, so by default all rights are
  reserved. We can take ideas, not text.
- `greploop` and `unslop` are MIT, so they may be reused with their notice kept.
- `before-and-after` is under PolyForm Shield, which forbids use in a competing product. It is
  the riskiest to vendor into a public toolbox.
- The toolbox already has its own `unslop` family, so there is nothing to vendor there.

## How it compares with our software factory

The toolbox's factory (`software/`: `software-factory-orchestrator` with its triager, builder,
tester, reviewer and lookback, run by Sentinel) already has most of this, often more strictly.

| The video | Ours | Gap or idea |
|---|---|---|
| A worktree per feature, never main | `software_factory_worktree.py`, one worktree per issue; the ship guards never push to main or a default branch | None |
| A code-structure skill applied while building | Each repo's own conventions (`SOFTWARE-FACTORY-RULES.md`), `software-improve-architecture`, `software-doc-standards` | Idea: a default structure standard for repos that have no conventions yet |
| Before-and-after proof: video, screenshots, numbers | `software-verify`: reproduce before fixing; an independent tester takes before-and-after screenshots for UI changes; an evidence folder | Ours keeps the evidence in the Run folder. Idea: embed it in the PR description, as he does, so the person reviews proof where they merge. Video capture is not covered. |
| The building agent proves its own work | The tester and reviewer are separate agents that never see the builder's reasoning | Ours is stricter on independence |
| An external review agent scores the PR; the loop runs until 5/5 | Our reviewer is an internal agent; the PR is reviewed after the ship | Idea: an external review score as an exit condition of the build loop, or a second opinion before a PR opens |
| The agent opens the PR itself | No route to GitHub while agents work (`network: no-github`); only the Automation's `finish` step ships, under guards | Ours is deliberately stricter; worth keeping |
| One person, 15 features at once by hand | Scheduled, one repo per session, issues triaged under policy; Sentinel's ceiling on live Runs | Different aim: unattended rather than supervised parallel work |
| `AGENTS.md` holds the workflow | The workflow lives in agent definitions and `software-factory-workstream`; owner rules in the canon | Agrees with his point: don't spend the agent's context describing the code |

### Ideas worth taking

1. **Put the proof in the pull request body** (screenshots, before-and-after numbers), so
   reviewing means looking at evidence where you merge. See `software-pr`.
2. **Use a review score as a stop condition:** loop build, prove and review until an
   independent score reaches the bar, rather than one review pass.
3. **Record video as evidence** for UI flows, beside the screenshots.
4. **A default code-structure standard** for repos without conventions, applied at build time
   rather than found at review.
5. **The factory vocabulary** (station, assembly line, quality control, shipping) as plain words
   in the guide for non-technical readers.
6. **His evidence rules, as text of our own:** a test that could not run is marked untested with
   its reason; the evidence names the exact commit; a fix shows the old failure beside the new
   success; nothing synthetic passes as real. Check `software-verify` and the tester against each.
7. **A scope check before building:** skip an issue whose files an open factory PR already
   changes, rather than discovering the conflict at merge.
8. **Capture hygiene for screenshots and video:** maximize the window, and keep secrets and
   client data off screen. This matters more for us, since our evidence can show client material.
9. **A cap on every loop:** a fixed number of review-and-fix rounds, reporting rather than
   continuing on a stale or missing review.
