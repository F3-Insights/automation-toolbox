#!/usr/bin/env python3
"""report-profile: write, check and show the role profile a weekly report is written from.

The profile is one Markdown document with twelve `## ` sections (see the
`reference/weekly-report-profile.md` template in the report-weekly skill). It is filled in once
by interview (the report-weekly skill's setup.md) and reviewed every quarter.

Subcommands:
  init      write the blank form (--out PATH, or --out - for standard output; --force overwrites)
  validate  say what is wrong: exit 0 with warnings only, 3 with an error (--json for data)
  show      print a summary, the parsed profile (--json) or the outline it projects to (--outline)
  due       is the quarterly review due? (--today YYYY-MM-DD to pretend; --json)

An error is something no correct profile can have: a missing section, a tier that is not
portal, harvester or manual, a standing metric with no source, a category naming an undeclared
seat, an unreadable review date. A warning (category count outside three to seven, a category
with no signals, no materiality threshold) may still be exactly what the executive meant.

Example:
  python3 report_profile.py validate --profile ~/reports/finance/profile.md
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import _profile as pf
from _common import FAILED, OK, Fail, run_main, safe


def row(kind, section, detail):
    return {"kind": kind, "section": section, "detail": detail}


def check(profile):
    """{errors, warnings, stats} for a parsed profile. No input or output, so it is testable."""
    errors = [row("MISSING_SECTION", n, f"the profile has no '## {n}' section; every one of the "
                  f"{len(pf.PROFILE_SECTIONS)} sections is present, empty if the answer is nothing")
              for n in profile["sections_missing"]]
    warnings = []
    categories = profile["categories"]
    seats = [s["name"] for s in profile["seats"]]
    if not seats:
        errors.append(row("NO_SEATS", "Seats", "the profile names no seat, so no category can say "
                                               "which seat it belongs to"))
    if not categories:
        errors.append(row("NO_CATEGORIES", "Standing categories", "the profile names no category"))
    elif not pf.MIN_CATEGORIES <= len(categories) <= pf.MAX_CATEGORIES:
        warnings.append(row("CATEGORY_COUNT", "Standing categories",
                            f"the profile names {len(categories)} categories; three to seven is the "
                            f"range a report reads well at, a question to ask, not a thing to fix"))
    if categories:
        last = categories[-1]
        if last["name"].casefold() != pf.OTHER_NAME.casefold() or last["kind"] != "other":
            errors.append(row("OTHER_NOT_LAST", "Standing categories",
                              f"the last category is {last['name']!r} of kind {last['kind'] or '(none)'!r}; "
                              f"it is always {pf.OTHER_NAME!r}, kind 'other'"))
    if len([c for c in categories if c["kind"] == "other"]) > 1:
        errors.append(row("OTHER_NOT_LAST", "Standing categories",
                          "more than one category has kind 'other'; exactly one does and it is last"))
    listed = {m["facts_key"] for m in profile["standing_metrics"]} | \
             {m["name"].casefold() for m in profile["standing_metrics"]}
    seen = set()
    for c in categories:
        name = c["name"]
        if name.casefold() in seen:
            errors.append(row("CATEGORY_DUPLICATE", "Standing categories",
                              f"two categories are both called {name!r}"))
        seen.add(name.casefold())
        if c["kind"] not in pf.KINDS:
            errors.append(row("CATEGORY_KIND", "Standing categories",
                              f"category {name!r} has kind {c['kind'] or '(none)'!r}; it is one of "
                              f"{', '.join(pf.KINDS)}"))
        if not c["seat"]:
            errors.append(row("CATEGORY_SEAT", "Standing categories", f"category {name!r} names no seat"))
        elif seats and c["seat"].casefold() not in {s.casefold() for s in seats}:
            errors.append(row("CATEGORY_SEAT", "Standing categories",
                              f"category {name!r} names the seat {c['seat']!r}, which is not one of "
                              f"{', '.join(seats)}"))
        compiled, broken = pf.compile_signals(c["signals"])
        errors += [row("SIGNAL_PATTERN", "Standing categories", f"the signal pattern {p!r} on "
                       f"category {name!r} is not a valid regular expression") for p in broken]
        if c["kind"] != "other" and not any(compiled.values()):
            warnings.append(row("CATEGORY_NO_SIGNALS", "Standing categories",
                                f"category {name!r} carries no signals, so nothing is assigned to "
                                f"it and it is on the silent list every week"))
        if not c["covers"]:
            warnings.append(row("CATEGORY_NO_COVERS", "Standing categories",
                                f"category {name!r} does not say what it covers in one line"))
        warnings += [row("KEYWORD_OVERMATCHES", "Standing categories", f"on category {name!r}, {why}")
                     for k in c["signals"]["keywords"] if (why := pf.keyword_warning(k))]
        warnings += [row("METRIC_NOT_LISTED", "Standing metrics",
                         f"category {name!r} reports {m['name']!r} from facts:{m['facts_key']}, and "
                         f"the Standing metrics section does not list it with a cadence")
                     for m in c["standing_metrics"]
                     if m["facts_key"] and m["facts_key"] not in listed and m["name"].casefold() not in listed]
    for m in profile["standing_metrics"]:
        if not m["source"]:
            errors.append(row("METRIC_NO_SOURCE", "Standing metrics",
                              f"the standing metric {m['name']!r} does not say where its number comes "
                              f"from; write 'from `facts:<key>`' or '{pf.SOURCE_BY_HAND}'"))
        if m["cadence"] not in pf.CADENCES:
            warnings.append(row("METRIC_CADENCE", "Standing metrics",
                                f"the standing metric {m['name']!r} names no cadence of "
                                f"{', '.join(pf.CADENCES)}, so nothing knows which weeks it is due"))
    if profile["tier"] not in pf.TIERS:
        errors.append(row("TIER", "Collection tier and scope signals",
                          f"the collection tier is {profile['tier'] or '(none)'!r}; it is one of "
                          f"{', '.join(pf.TIERS)}"))
    elif profile["tier"] != "manual" and not any(profile["scope_signals"].values()):
        warnings.append(row("NO_SCOPE_SIGNALS", "Collection tier and scope signals",
                            "no attendee domain, title pattern or mail term is given, so most of the "
                            "calendar will come back unassigned"))
    warnings += [row("NO_ARRIVAL_FORM", "Direct reports",
                     f"the direct report {r['role']!r} does not say where their update arrives; "
                     f"write 'mail from `<address>` with subject `/<pattern>/i`', 'note titled "
                     f"`/<pattern>/i`' or 'file `<glob>`' after a semicolon")
                 for r in profile["direct_reports"] if not r["source"]]
    form = profile["form"]
    for ok, kind, section, detail in (
            (profile["leadership"], "NO_LEADERSHIP", "Leadership team",
             "no leadership team member is named, so the audience test has nothing to test against"),
            (form["hard_cap_words"] or form["hard_cap_pages"], "NO_HARD_CAP", "Form rules",
             "no hard cap is stated, so the verifier has no length error to raise"),
            (form["deadline_day"], "NO_DEADLINE", "Form rules", "no deadline day is stated"),
            (form["materiality_amount"] is not None, "NO_MATERIALITY", "Form rules",
             "no materiality threshold is stated, so no figure is judged immaterial and report-verify "
             "skips its IMMATERIAL_FIGURE check; write 'Materiality: $10,000' to set one"),
            (profile["names_to_roles"], "NO_NAMES_TO_ROLES", "Names to roles",
             "no names-to-roles map, so a problem sentence drops its actor rather than naming a role"),
            (profile["delivery"]["recipients"], "NO_RECIPIENTS", "Delivery", "no recipient is named"),
            (profile["exclusions"]["never_published"], "NO_EXCLUSIONS", "Never published",
             "the never-published list is empty")):
        if not ok:
            warnings.append(row(kind, section, detail))
    if "Review date" not in profile["sections_missing"] and not profile["review"]["next"]:
        errors.append(row("REVIEW_DATE", "Review date", "no review date could be read; write dates "
                                                        "as YYYY-MM-DD, the only spelling read"))
    stats = {"sections_present": len(profile["sections_present"]), "seats": len(seats),
             "leadership": len(profile["leadership"]), "categories": len(categories),
             "standing_metrics": len(profile["standing_metrics"]),
             "direct_reports": len(profile["direct_reports"]), "tier": profile["tier"],
             "review_next": profile["review"]["next"], "errors": len(errors), "warnings": len(warnings)}
    return {"errors": errors, "warnings": warnings, "stats": stats}


def review_status(profile, today=None):
    now = today or date.today()
    nxt = profile["review"]["next"]
    when = date.fromisoformat(nxt) if nxt else None
    return {"today": now.isoformat(), "last": profile["review"]["last"], "next": nxt,
            "due": bool(when and when <= now), "days": (when - now).days if when else None,
            "months": pf.REVIEW_MONTHS}


def check_text(result, reading):
    s = result["stats"]
    lines = ["# Report profile", "",
             f"{s['sections_present']} of {len(pf.PROFILE_SECTIONS)} sections, {s['seats']} seat(s), "
             f"{s['categories']} categories, {s['standing_metrics']} standing metric(s), "
             f"{s['direct_reports']} direct report(s), tier {s['tier'] or '(none)'}.",
             f"{s['errors']} error(s), {s['warnings']} warning(s)."]
    lines += [f"- READING: {line}" for line in reading]
    for label, rows in (("Errors", result["errors"]), ("Warnings", result["warnings"])):
        lines += ["", f"## {label}"] + ([f"- {r['kind']} ({r['section']}): {r['detail']}" for r in rows]
                                        or ["None."])
    return "\n".join(lines)


def show_text(p):
    form = p["form"]
    lines = ["# Report profile", "",
             f"Author: {p['author']['role'] or '(not stated)'}, at {p['author']['organisation'] or '(not stated)'}.",
             f"Tier: {p['tier'] or '(none)'}.",
             "Materiality: none stated, so no figure is judged immaterial."
             if form["materiality_amount"] is None else
             f"Materiality: {form['materiality_text']} (read as {form['materiality_currency']}"
             f"{form['materiality_amount']:,.0f})."]
    lines += ["", "## Seats"] + [f"- {s['name']}: {s['description']}" for s in p["seats"]]
    lines += ["", "## Leadership team"] + [f"- {m['role']}: {m['answers_for']}" for m in p["leadership"]]
    lines += ["", "## Standing categories"] + [f"- {c['name']} ({c['kind']}, seat {c['seat']})"
                                               for c in p["categories"]]
    lines += ["", "## Standing metrics"] + [f"- {m['name']} from {m['source'] or '(no source)'}, "
                                            f"{m['cadence'] or '(no cadence)'}" for m in p["standing_metrics"]]
    lines += ["", "## Direct reports"] + [f"- {r['role']}, on {r['reports_on']}; {r['arrives'] or '(no arrival form)'}"
                                          for r in p["direct_reports"]]
    lines += ["", "## Never published"] + [f"- {t}" for t in p["exclusions"]["never_published"]]
    lines += ["", "## Never recorded"] + [f"- {t}" for t in p["exclusions"]["never_recorded"]]
    lines += ["", f"Last reviewed {p['review']['last'] or '(not stated)'}, next {p['review']['next'] or '(not stated)'}."]
    if p["sections_missing"]:
        lines.append(f"Missing sections: {', '.join(p['sections_missing'])}.")
    return "\n".join(lines)


def due_text(s):
    if not s["next"]:
        return "No review date could be read from the profile, so the quarterly review has no clock."
    if s["due"]:
        return (f"Due. The review was set for {s['next']} and today is {s['today']}, {abs(s['days'])} "
                f"days on. Last reviewed {s['last'] or '(not stated)'}.")
    return (f"Not due. The next review is {s['next']}, {s['days']} days from {s['today']}. "
            f"Last reviewed {s['last'] or '(not stated)'}.")


def main():
    parser = argparse.ArgumentParser(description="The role profile a weekly report is written from.")
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init", help="write the blank profile form")
    init.add_argument("--out", default="weekly-report-profile.md", help="where to write it; - for stdout")
    init.add_argument("--force", action="store_true", help="overwrite an existing file")
    for name in ("validate", "show", "due"):
        one = sub.add_parser(name)
        one.add_argument("--profile", default="", help="the profile, a Markdown file")
        one.add_argument("--json", action="store_true", help="print JSON")
        if name == "show":
            one.add_argument("--outline", action="store_true", help="print the outline it projects to")
        if name == "due":
            one.add_argument("--today", default="", help="treat this YYYY-MM-DD as today")
    args = parser.parse_args()

    if args.action == "init":
        if args.out.strip() == "-":
            sys.stdout.write(TEMPLATE)
            return OK
        target = Path(args.out).expanduser()
        if target.exists() and not args.force:
            raise Fail(f"{target} already exists; pass --force to overwrite it")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(TEMPLATE, encoding="utf-8")
        print(f"Wrote the blank profile form to {target}. Fill it in with the executive, section by "
              f"section, then run 'report_profile.py validate --profile {target}'.")
        return OK

    profile, reading = pf.load_profile(args.profile)
    if args.action == "validate":
        result = check(profile)
        print(safe(json.dumps({**result, "reading": reading}, indent=1) if args.json
                   else check_text(result, reading)))
        return FAILED if result["errors"] else OK
    if args.action == "show":
        print(safe(pf.outline_text(profile) if args.outline
                   else json.dumps(profile, indent=1) if args.json else show_text(profile)))
        return OK
    today = None
    if args.today.strip():
        stamp = pf.as_iso(args.today)
        if not stamp:
            raise Fail(f"--today is {args.today!r}; write it as YYYY-MM-DD")
        today = date.fromisoformat(stamp)
    status = review_status(profile, today)
    print(json.dumps(status, indent=1) if args.json else due_text(status))
    return OK


TEMPLATE = '''# Weekly report profile

The role profile for one author's weekly report. Filled in once, in an interview, and reviewed
every quarter. One document with twelve headed sections, so an executive can read and edit it
and so it can live as a note wherever the organisation keeps its record.

**This is the only document the executive edits.** The report outline the pipeline sorts the
week into is a projection of this file, not a second list to keep in step:
`report-profile show --outline` writes it, and `report-pack --outline-file` accepts this file
directly. Every heading below is read by code, so a relabelled one is a section nobody sets.

Describe every person by role. The only place a name belongs in this file is the optional
`Names to roles` map, which exists so a sentence about a problem can carry the role instead
of the person.

A blank form does not pass `report-profile validate`, and should not: the tier, the seats and
the review date are placeholders until somebody has answered for them.

Where the real profile lives: as a note titled `Weekly report profile` attached to the
author's scope, so an assistant can edit it without touching a repository.

```
list_entities(entity_type="note", filters={"entity_type": "domain",
              "entity_id": "<the scope uuid>", "search": "Weekly report profile"}, limit=5)

create_note(title="Weekly report profile", content="<this form, filled in>",
            associations=[{"entity_type": "domain", "entity_id": "<the scope uuid>",
                           "is_primary": true}])
```

The run looks for that note first, then an older `Weekly report outline` note, then an older
`Weekly report spec` note, and says which one it used.

## Author and organisation

Who writes this report, by role, and what the organisation does.

- Role: <the author's role, for example the controller>
- Organisation: <what the organisation does and roughly how large it is>

## Seats

One numbered item per seat: the seat's name, a colon, then one paragraph on what the position
answers for. One person may hold two seats, and they share one report with a header per seat.

1. <Seat name>: <what this position answers for, in one paragraph>

## Leadership team

One item per member: their role and what they answer for. The audience test is run against
this list, so an item earns its place in the report when one of these readers has to know it,
has to decide something because of it, or is affected by it.

1. <Role>: <what this member answers for>

## Standing categories

The categories the week is sorted into, in the order the reader cares about, ending with
`Other topics`. Between three and seven reads well; that is a range and not a rule. Write them
from the job, not from last week's inbox. A category that exists because something happened
once is a category that is silent for the next eleven weeks.

Three kinds, and every category is one of them:

- `operational`: a standing responsibility of the position, taken from what the job is. It
  appears every week whether or not anything happened. The month-end close, the forecast, the
  cash position, receivables. Warehouse output, safety, the delivery fleet.
- `project`: something the person leads or is involved in that has an end. A warehouse move,
  securing financing, kicking off the budget.
- `other`: **exactly one, always last.** The important smaller call-outs that belong to no
  category above.

**Signals** are what let code put a piece of evidence in a category rather than a model
guessing. Six kinds, and a category may carry any of them. Titles and Subjects are regular
expressions, matched case-insensitively against a task, note, project or meeting title and
against a mail subject. Keywords are plain text, matched anywhere in the item including a
note's body. Projects and Goals name a tracked project or goal, by name or by id.
Counterparties are an email domain or a contact's role.

A keyword matches as a whole word or a whole phrase, case-insensitively and allowing a simple
plural, so `invoice` matches "invoices" and no keyword is ever found inside a longer word. A
keyword written in capitals is read as an acronym and matched case-sensitively, so `IT` never
matches "it" and `AR` never matches "are" or "Shareables", while `tax` still matches "Tax".

**First match in category order wins.** An item goes into at most one category and the signal
that matched is recorded beside it, so the order of the categories is their precedence: put
the close above the forecast and a thread about the close forecast lands in the close. An item
that matches nothing is unassigned and is never quietly folded into `Other topics`, because
the size of the unassigned pile is the time-management signal the author is owed.

What the checker rejects outright: no category of kind `other`, more than one, or one that is
not last; a category naming a seat this profile does not declare; a kind that is not one of
the three; a signal pattern that is not a valid regular expression. A category with no signals
is a warning rather than an error, because it will appear on the silent list every week, which
may be exactly right for a responsibility nothing electronic ever touches.

Write nothing but the blocks below under this heading. A line that is not a bullet continues
the bullet above it, so a paragraph after a block lands inside that block's Covers.

### <Category name>
- Seat: <one of the seats above>
- Kind: <operational for a standing responsibility, project for something with an end>
- Covers: <what this category covers, in one line>
- Signals:
  - Titles: `<a pattern matched against a task, note, project or meeting title>`
  - Subjects: `<a pattern matched against a mail subject>`
  - Keywords: `<plain text matched anywhere in the item>`
  - Projects: `<a project by name>`
  - Goals: `<a goal by name>`
  - Counterparties: `<an email domain or a contact's role>`
- Standing metrics:
  - <Metric name> from `facts:<key>`
- Owner: <the role of the direct report who owns this category>

### Other topics
- Seat: <one of the seats above>
- Kind: other
- Covers: important smaller call-outs that belong to none of the categories above.

## Standing metrics

One item per figure the report carries every week, with where the number comes from and how
often it moves. The source is `facts:<key>` for a figure the facts set supplies, or
`supplied by hand` for one the executive gives at a gate. The cadence is weekly, monthly,
quarterly or annual. A figure with no value is reported as not available; nothing is invented.

1. <Metric name> from `facts:<key>`, weekly
2. <Metric name>, supplied by hand, monthly

## Direct reports

One item each: the role, what they report on, and where and when their weekly report arrives.
Three arrival forms, because three are how a weekly update actually reaches somebody:

```
mail from `<an address or a domain>` with subject `/<a pattern>/i`
note titled `/<a pattern>/i`
file `<a glob under the directory the run names>`
```

1. <Role>, reports on <what they report on>; mail from `<address>` with subject `/<pattern>/i`

## Collection tier and scope signals

The tier is how the week is collected: `portal` reads it in code, `harvester` has a worker
read the mail and calendar, `manual` uses the reports in a folder and the executive's own
account. The scope signals are what say a meeting or a thread is this seat's at all.

- Tier: <portal, harvester or manual>
- Attendee domains: `<a domain the seat meets with>`
- Title patterns: `/<a pattern in this seat's meeting titles>/i`
- Mail terms: `<a term that marks this seat's mail>`

## Form rules

Length is a constraint and not a target. The cap is the hard stop.

- Length: <one page, 450 to 600 words>
- Hard cap: <two pages, 1,100 words>
- Deadline: <Friday> by <3 pm>
- Holiday rule: <what happens when the deadline day is a holiday>
- Materiality: <the amount below which a figure is not reportable on its own>

A filled-in line reads `Materiality: $10,000`. Anything still inside angle brackets is a
placeholder and is read as no answer at all, which is what the brackets are for: an example
amount left inside them would parse as a real threshold and the week's figures would be judged
against a number nobody chose.

A smaller figure may still appear inside a pattern that carries its own count and total, so
"eleven billing errors this quarter, $4,900 recovered" is reportable where "$81.40 recovered"
is not. Materiality is optional: with none stated no figure is judged immaterial, every amount
may stand on its own, and `report-verify` skips its IMMATERIAL_FIGURE check and says so.

Then one numbered item per rule about the shape of the document itself: what opens a bullet,
where figures go, what is cut first and what is never cut. The writer is what reads these.

1. <a rule about the shape of the document>

## Names to roles

**Optional, and the one section that holds names.** A person may be named in the report for
credit or for joint work: "working with the controller to resolve the billing reconciliation"
is right, and a win names the people or the team who delivered it. A person is never named in
a sentence that attaches them to a mistake, a delay, a gap, a failure or an unmet obligation.
This map is what the writer substitutes from when it has to rewrite one of those sentences.
With no map it drops the actor entirely, which is also correct, so leaving this out is a
warning at validation and never an error.

1. <the name as it appears in the mail and the meeting invitations>: <their role>

## Delivery

- Recipients: <the roles the report goes to>
- Folder: <where the file is filed>

## Never published

The absolute exclusion list. Nothing here ever reaches the report, whatever else is true.

1. <what never appears in the report>

## Never recorded

What is redacted even from the stored record, so it is not kept for continuity or audit.

1. <what is never stored>

## Review date

Dates are written as `YYYY-MM-DD`, which is the only spelling this reads. The next review is
three months after the last unless a date is written here.

- Last reviewed: <YYYY-MM-DD>
- Next review: <YYYY-MM-DD>
'''


if __name__ == "__main__":
    run_main(main)
