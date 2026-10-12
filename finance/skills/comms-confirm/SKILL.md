---
name: comms-confirm
description: "Ask a person (the owner, a colleague by role, a client contact) to confirm something the work needs, record that the question is out, end the session, and let a later check notice the answer. Four uses: ask (resolves the role to a person, records the request, puts a waiting task on the owner's list, relays the question through the owner, one message per session, never contacting colleagues unless delivery is set to direct); check (a no-model precheck of the record, the Portal task and the email thread that prints NOTHING or WORK); close (marks it resolved with who answered and the evidence); remind (the morning message listing requests past due or due today). Use whenever semi-attended work (a close, forecast, report, project) must wait on an answer instead of guessing. Not for chasing work already delegated; use comms-follow-ups."
argument-hint: "[ask | check | close | remind] [store or folder] [question, role, channels, due, fallback]"
allowed-tools: Read, Bash(python3:*), Bash(python3 ~/.claude/skills/comms-confirm/scripts/confirm_portal.py:*), Bash(python3 ~/.claude/skills/comms-reply-to-email/scripts/find_contact.py:*), Bash(python3 ~/.claude/skills/comms-reply-to-email/scripts/notify_owner.py:*), Skill, Task
---

# Confirm with a person

Work that runs without its owner watching meets questions only a person can answer: was this invoice for September, is the payroll accrual posted, may the forecast assume the new hire. This skill records such a question, gets it to the right person, and lets the work end its session. A later check, which needs no model, notices the answer and says so.

For now the owner is the relay: the skill never writes to a colleague. It messages the owner, asking them to put the question to the named person, and records the request as waiting on that person. Every Portal task it makes sits on the owner's own list. Nothing here sends anything to anyone but the owner.

The request's fields, the store, the channels, the delivery setting, the fallbacks and how answers are matched are in `rules.md` beside this file. Read it before the first request in a session. One script keeps the store (paths relative to this skill's folder); it reaches the Portal only through `scripts/confirm_portal.py` beside it and the owner only through `python3 ~/.claude/skills/comms-reply-to-email/scripts/notify_owner.py`:

```bash
python3 scripts/confirm.py who FOLDER --role ROLE
python3 scripts/confirm.py new STORE --question Q --of ROLE --channel task|owner|email [...]
python3 scripts/confirm.py task STORE ID
python3 scripts/confirm.py relay STORE_OR_FOLDER ... [--dry-run]
python3 scripts/confirm.py record STORE ID --draft D --subject S
python3 scripts/confirm.py check PATH ...
python3 scripts/confirm.py close STORE ID --by WHO --answer A --evidence E
python3 scripts/confirm.py reopen STORE ID --by WHO --note N
python3 scripts/confirm.py remind STORE_OR_FOLDER ... [--dry-run]
```

## Inputs

- **Use** (required): ask, check, close or remind.
- **Store** (required): the caller's `CONFIRMATIONS.md`, in the work's own folder. For an engagement folder it is the period folder, `FOLDER/yyyy/yyyy-mm/CONFIRMATIONS.md`. Check, relay and remind also take a folder and find every store under it.
- **Question** (ask): one answerable sentence, with the context links that show why it is asked.
- **Asked of** (ask): a role, such as "the AP lead", "the owner", "the client's controller". Never a name typed into the calling skill; the person comes from the caller's context.
- **Delivery** (ask, a setting): `relay` or `direct`. Default `relay`, the owner's decision until they change it: the owner is asked to put the question to the person, no email is drafted to them and no task goes on their list. `direct` keeps the older behaviour, an email draft to the person for the owner to send; it is off unless the setting says otherwise (`--delivery direct`, or `CONFIRM_DELIVERY=direct` in the environment). Never switch it on your own judgment.
- **Channels** (ask): any of owner (a question to the owner now, when present), task (a Portal task on the owner's list, waiting on the person) and, with delivery direct only, email (a draft to the person). Default: task.
- **Due** (ask, optional): the date an answer is wanted. Default the end of the next full business day after asking (weekends skipped; holidays are not counted).
- **Fallback** (ask, optional): proceed with a stated assumption, escalate to the owner, or wait. Default escalate, which is the morning reminder.
- **Record** (ask, optional): the engagement folder and phase, so a Waiting on row is kept, or a file where answers are appended. Default the store alone.
- **Who** (close, required): the calling skill or person closing it.

If a required input was not given, ask. If no one can be asked, stop and name it.

## Steps

1. [judgment] Settle the use and the inputs. For ask, write the question as one sentence the person can answer without opening anything, list the context links, and choose the channels, the due date and the fallback. Take the delivery from the setting. With no one present, the owner channel becomes a task on the owner's list. → a required input is missing and no one can be asked: stop → use is check: step 9 → use is close: step 11 → use is remind: step 12
2. [script] Resolve the role to a person. For an engagement folder run `python3 scripts/confirm.py who FOLDER --role ROLE`; otherwise read the role from the caller's context (its BACKGROUND.md, a Context, the brief). Then pin the person's Portal contact with `python3 ~/.claude/skills/comms-reply-to-email/scripts/find_contact.py "<name or address>"`. The owner needs no lookup. → no person for the role, or several contacts, and no one can be asked: stop → several people or contacts and the owner is present: ask
3. [script] Record the request: `python3 scripts/confirm.py new STORE --question Q --of ROLE --person "Name <address>" --contact UUID --channel CH --due D --fallback F --assume A --context LINK --engagement FOLDER --phase NAME --by WHO`. It prints the request id and the delivery. The same question to the same role in the same store returns the existing request, never a second. → `"outcome": "existing"` and its channels are already out: done
4. [ask] Owner channel with the owner present: put the question, with its context, as one numbered line. Skip this step for the other channels. → the owner answers: step 11
5. [script] Task channel: `python3 scripts/confirm.py task STORE ID`. It runs `scripts/confirm_portal.py task`, which finds the request's task by its marker or creates it once, on the owner's list, WAITING on the person when they have a contact. → it fails: stop
6. [script] Delivery relay, once the session's last question is recorded: `python3 scripts/confirm.py relay STORE_OR_FOLDER`. It sends the owner ONE message through `comms-reply-to-email/scripts/notify_owner.py` asking them to put each question not yet relayed to its person, with where the answer goes, and marks each one relayed. Then end the session; the work waits on the requests. Skip this step with delivery direct. → `NOTHING` or `SENT`: done → `NOT SENT` (notifications are off or rehearsing): done → it fails: stop
7. [hand-off: comms-draft-email] Email channel, delivery direct only: draft the question to the person through the drafting skill, which checks with `outbound-check`, writes in the owner's voice and never sends. With no one present the draft stays in the Portal for the owner to deliver. → no draft was made (`outbound-check` held, or the drafter stopped): done
8. [script] Note the draft so a reply can be matched: `python3 scripts/confirm.py record STORE ID --draft DRAFT_ID --subject "SUBJECT"`. Then end the session; the work waits on the request. → recorded: done
9. [script] Look for answers: `python3 scripts/confirm.py check STORE_OR_FOLDER`. The first line is `NOTHING` or `WORK: answered ...; past due ...`; answers found are recorded in the store and in the Waiting on row. → `NOTHING`: done
10. [judgment] For each answered request, read the evidence (the comment, the reply email, the typed answer). If it answers the question, the calling work uses it and closes it at step
    11. If it does not ("let me check"), run `python3 scripts/confirm.py reopen STORE ID --by WHO --note N`. A past-due request with the proceed fallback is closed as assumed at step 11; one with escalate is already in the owner's morning reminder and needs nothing here. → something to close: step 11 → nothing to close: done
11. [script] Close: `python3 scripts/confirm.py close STORE ID --by WHO --answer "A" --evidence REF`, or `--assumed` for a proceed fallback, or `--withdrawn`. The record is closed with it and the request's Portal task gets one comment with the answer and its evidence, then is marked done (cancelled when withdrawn). → closed: done
12. [script] Remind: `python3 scripts/confirm.py remind STORE_OR_FOLDER ...`, with `--dry-run` to see the message without sending it. It sends the owner ONE message listing every open request past due or due today (who, the question, when it was asked, where to answer), or nothing when there are none. A request already in today's reminder is not listed again until the next day. → `NOTHING` or `SENT`: done → `NOT SENT` or `DRY RUN`: done → it fails: stop

On a stop, say why in one line and what would unblock it.

## How other skills use it

A skill that needs a confirmation does not ask in prose and does not build its own queue. It runs ask with the question, the role and the record, relays once at the end of its session, and ends with the phase it blocks set to waiting. Its next session, or a scheduler, runs check first; `WORK` means an answer arrived or a proceed request's due date passed. A scheduler also runs remind each business morning over the folders that hold stores. For an engagement folder (a month-end close, for one), pass `--engagement FOLDER --phase NAME` to `new`: a row is added to the period STATUS.md's `## Waiting on` table with the request id in its question, check marks it answered when the answer comes, and close closes it (rules.md, "The Waiting on row"). The work's own orchestrator reads that table to see the phase can continue. A role resolves from BACKGROUND.md's Roles when it is written as `- AP lead: Name <address>`.

## When no one is present

Check and remind run on their own; check starts a session only on `WORK`. Ask never uses the owner channel live: the question goes on the owner's task list instead, and relay tells the owner in one message. Drafts (delivery direct) are never delivered; they wait in the Portal. Step 2 stops rather than choosing between two people. A past-due request with the escalate fallback is listed in the owner's morning reminder each business day until it is answered or closed; one with proceed is closed as assumed, and the assumption is written into the work's log so the owner sees it.
