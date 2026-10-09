"""The digest: the organised pack as Markdown, built to be read once and pasted into a prompt.

The workers (continuity, audience editor, writer) never open a file; the digest is inlined in
their dispatch prompt. So every line carries the reference to cite it by, the evidence is
listed under the category that claimed it, in the profile's order, and the fuller material a
bullet is written from (a task's description, a note's text with both its ends, a mail excerpt)
sits under its item.

Size: aimed at 30,000 characters, hard stop 38,000. Over the target a ladder of cuts runs,
cheapest loss first (the look-ahead meetings, the unassigned items' material, edited notes,
goal detail, the unassigned list, then the depth of material under each category), and above
the hard cap the forced cuts shorten the material itself. Every cut that fired is named at the
end of the digest. A category's roster (one line per item) is never cut.
"""

from _common import one_line

TARGET_CHARS, HARD_CAP_CHARS = 30000, 38000
NOTE_CHARS = 1500
CUT_MARK = "[… middle cut …]"

LADDER = (
    ("lookahead_items", False, "the look-ahead meetings were reduced to their totals"),
    ("unassigned_detail", False, "the unassigned items lost their material; their roster lines remain"),
    ("edited_note_chars", 600, "notes edited rather than written in the period were shortened to 600 characters"),
    ("goal_detail", False, "the goals were reduced to their titles"),
    ("unassigned_items", 10, "the unassigned items were cut to 10 rows; the shares still count every one"),
    ("unassigned_items", 0, "the unassigned items were reduced to their counts and clusters"),
    ("category_detail", 12, "only the top 12 items in each category carry their material"),
    ("category_detail", 8, "only the top 8 items in each category carry their material"),
)
FORCED = (
    ("direct_report_chars", 250, "the hard cap cut each direct report's own words to 250 characters"),
    ("note_chars", 900, "the hard cap cut note text to 900 characters, start and end both kept"),
    ("description_chars", 200, "the hard cap cut task descriptions to 200 characters"),
    ("excerpt_chars", 200, "the hard cap cut mail excerpts to 200 characters"),
    ("category_detail", 5, "the hard cap left only the top 5 items in each category carrying material"),
    ("category_detail", 3, "the hard cap left only the top 3 items in each category carrying material"),
    ("description_chars", 120, "the hard cap cut task descriptions to 120 characters"),
)


def defaults():
    return {"lookahead_items": True, "unassigned_detail": True, "edited_note_chars": NOTE_CHARS,
            "goal_detail": True, "unassigned_items": None, "category_detail": 0,
            "direct_report_chars": 600, "note_chars": NOTE_CHARS, "description_chars": 0,
            "excerpt_chars": 0}


def head_tail(text, limit):
    """Text within a limit, keeping both ends: a meeting note's follow-through sits at the end."""
    body = str(text or "")
    if len(body) <= limit:
        return body
    head = round(limit * 0.6)
    return f"{body[:head].rstrip()}\n{CUT_MARK}\n{body[-(limit - head):].lstrip()}"


def roster_line(row):
    detail = one_line(row.get("detail"), 110)
    return (f"- [{row.get('kind')}] {one_line(row.get('title'), 90)}" + (f"; {detail}" if detail else "")
            + (f" ({row['matched_signal']})" if row.get("matched_signal") else "")
            + (" (pulled back by the executive)" if row.get("pulled_back") else "")
            + (f" (moved from {row['moved_from']})" if row.get("moved_from") else "")
            + f" [{row.get('ref')}]")


def material(row, record, opts):
    """The fuller material under one item: description, note text or the latest message."""
    kind, text = row.get("kind"), str((record or {}).get("text") or "").strip()
    if not text:
        return []
    if kind == "task":
        return [f"  Description: {one_line(text, opts['description_chars'])}"]
    if kind == "note":
        limit = opts["note_chars"] if row.get("authored_in_period", True) else min(opts["note_chars"],
                                                                                  opts["edited_note_chars"])
        return ["  Note text:"] + [f"  {line}" for line in head_tail(text, limit).splitlines() if line.strip()]
    if kind == "mail":
        return [f"  Latest message: {one_line(text, opts['excerpt_chars'])}"]
    if kind == "direct_report":
        return [f"  Their words: {one_line(text, opts['direct_report_chars'])}"]
    return []


def render(pack, opts, fired):
    records = {r.get("ref"): r for r in pack.get("items") or []}
    author, period, outline = pack.get("author") or {}, pack.get("period") or {}, pack.get("outline") or {}
    tier = pack.get("tier") or {}
    lines = [f"# Evidence digest: {one_line(author.get('scope_name'))}", "",
             f"Period {period.get('since_local') or period.get('since')} to "
             f"{period.get('until_local') or period.get('until')}, exclusive, in {period.get('timezone')}.",
             f"Collected by the {tier.get('name')} tier: {tier.get('why') or ''}",
             f"The sweep ran at {(pack.get('provenance') or {}).get('collected_at') or 'a time the ledger does not record'}"
             f" (UTC); organised at {(pack.get('provenance') or {}).get('organised_at') or 'an unrecorded time'}.",
             "", "Every line below carries the reference to cite it by. Copy the reference onto the same "
                 "line of the report as the figure, date or name you take from it."]

    # The outline: what the report is about, before any evidence.
    length, materiality = outline.get("length") or {}, outline.get("materiality") or {}
    lines += ["", "## The outline", "", f"Source: {one_line(outline.get('source'))}."]
    if outline.get("report_title"):
        lines.append(f"Report title line: {outline['report_title']}")
    lines.append(f"Length: {length.get('target_words_min')} to {length.get('target_words_max')} words, "
                 f"hard cap {length.get('hard_cap_words')}. {one_line(length.get('text'))}")
    if materiality.get("amount") is not None:
        lines.append(f"Materiality: {one_line(materiality.get('text')).rstrip('.')}. A figure below "
                     f"{materiality.get('currency')}{materiality['amount']:,.0f} is not reportable on its own, "
                     f"only inside a pattern that carries its own count and total.")
    else:
        lines.append("Materiality: none stated, so no figure is judged immaterial.")
    if outline.get("names_to_roles"):
        lines.append("Names to roles, for rewriting a sentence that put a person beside a fault "
                     "(a name is welcome for credit or joint work):")
        lines += [f"- {one_line(p.get('name'))}: {one_line(p.get('role'))}" for p in outline["names_to_roles"]]
    lines += [f"- Reader **{one_line(m.get('role'))}** answers for {one_line(m.get('answers_for'))}"
              for m in outline.get("leadership_team") or []]
    lines += [f"- Form rule: {one_line(r)}" for r in outline.get("form_rules") or []]
    for label, key in (("Never appears", "never_appears"), ("Never recorded, not even as evidence", "never_recorded"),
                       ("Delivery", "delivery"), ("Cadence", "cadence")):
        if outline.get(key):
            lines.append(f"{label}: {one_line(outline[key])}")
    if outline.get("missing_sections"):
        lines.append(f"The outline does not carry: {', '.join(outline['missing_sections'])}. Say so rather "
                     f"than working around it.")
    lines += [f"- Seat **{one_line(s.get('name'))}**: {one_line(s.get('description'))}" for s in outline.get("seats") or []]
    lines += ["", "Write under these headers, in this order, and under no others:"]
    lines += [f"  {i}. {c['name']} ({c['kind']}, seat {c['seat']}): {one_line(c.get('covers'))}"
              for i, c in enumerate(pack.get("categories") or [], 1)]
    lines.append("The outline allows an empty category's section to be dropped." if outline.get("drop_empty_categories")
                 else "Every category gets a section, including one with nothing to report, which says so in one line.")
    lines += [f"- OUTLINE ERROR: {one_line(e)}" for e in outline.get("errors") or []]

    # The categories: the spine of the digest.
    cats = pack.get("categories") or []
    lines += ["", f"## Evidence by category ({len(cats)} categories)", "",
              "Each category is one header of the report, in this order. Everything a category claimed is "
              "listed under it. The unassigned bucket further down is for the owner, not the report."]
    for c in cats:
        n = c["counts"]
        lines += ["", f"### {c['name']}",
                  f"Kind {c['kind']}, seat {c['seat']}, importance {c['importance']}"
                  + (f", owned by {c['owner']}" if c.get("owner") else "") + f". {one_line(c.get('covers'))}",
                  f"Counts: {n['evidence']} evidence items, {n['meeting_hours']} meeting hours, "
                  f"{n['threads_awaiting_owner']} threads awaiting the owner, {n['p1_tasks']} P1 tasks, "
                  f"{n['overdue_tasks']} overdue, {n['deadlines_in_lookahead']} due in the look-ahead, "
                  f"{n['carry_overs']} carry-overs."]
        if c["standing_metrics"]:
            lines.append("Standing metrics, every week:")
            for m in c["standing_metrics"]:
                lines.append(f"- {m['name']}: {m['value']} as of {m['as_of'] or 'no date given'} "
                             f"[facts://{m['facts_key']}] source {one_line(m['source_label'])}"
                             if m["status"] == "present" else
                             f"- {m['name']}: MISSING, expected from {one_line(m['source_label'])}. Write "
                             f"'not available this week'; do not estimate it.")
        if c["carry_overs"]:
            lines.append("CARRY-OVERs, which this report has to say what happened to:")
            lines += [f"- CARRY-OVER **{one_line(x.get('label'))}**: {one_line(x.get('text'), 300)} (reported "
                      f"{x.get('report_date') or 'previously'}, {x.get('weeks_running')} week(s) running; "
                      f"{one_line(x.get('reason'))}) [{x.get('ref')}]" for x in c["carry_overs"]]
        rows, depth = c["evidence"], opts["category_detail"] or len(c["evidence"])
        lines.append(f"Every item this category claimed, ranked, {len(rows)} of them." if rows else
                     "No evidence matched this category this period. It is on the silent list, and Gate 2 asks about it.")
        for index, row in enumerate(rows):
            lines.append(roster_line(row))
            if index < depth:
                lines += material(row, records.get(row["ref"]), opts)
        if c.get("evidence_left_out"):
            lines.append(f"- {c['evidence_left_out']} further items rank below these; they are in the counts.")
        for d in c.get("direct_report_input") or []:
            lines.append(f"- [direct report] {one_line(d.get('name'))} on {one_line(d.get('reports_on'))}, "
                         f"{one_line(d.get('title'))} [{d.get('ref')}]")
            lines += material({"kind": "direct_report"}, d, opts)
        if c.get("prior_labels"):
            lines.append(f"Reported before under this category: {', '.join(c['prior_labels'])}.")

    # The unassigned bucket and the noise: for the owner.
    loose, noise = pack.get("unassigned") or {}, pack.get("noise") or {}
    lines += ["", f"## Unassigned ({loose.get('total', 0)} items matched no category)", "",
              "FOR THE OWNER AND NOT FOR THE REPORT. Do not write a section from it.",
              "By kind: " + "; ".join(f"{k} {v}" for k, v in (loose.get("counts") or {}).items()) + ".",
              f"Unassigned share: meeting hours {noise.get('meeting_hours_unassigned_pct')} percent "
              f"({noise.get('meeting_hours_unassigned')} of {noise.get('meeting_hours_total')}), mail threads "
              f"{noise.get('mail_threads_unassigned_pct')} percent, open tasks {noise.get('open_tasks_unassigned_pct')} percent."]
    if noise.get("largest_clusters_by_counterparty_domain"):
        lines.append("Largest clusters by counterparty domain: " + "; ".join(
            f"{x['domain']} {x['items']}" for x in noise["largest_clusters_by_counterparty_domain"]) + ".")
    if noise.get("largest_clusters_by_title_word"):
        lines.append("Largest clusters by title word: " + "; ".join(
            f"{x['word']} {x['items']}" for x in noise["largest_clusters_by_title_word"]) + ".")
    shown = loose.get("items") or []
    if opts["unassigned_items"] is not None:
        shown = shown[:opts["unassigned_items"]]
    for row in shown:
        lines.append(roster_line(row))
        if opts["unassigned_detail"]:
            lines += material(row, records.get(row["ref"]), opts)
    if len(loose.get("items") or []) > len(shown):
        lines.append(f"- {len(loose['items']) - len(shown)} further unassigned items are not listed.")

    # Gate 1 proposals: counted, never judged.
    block = pack.get("proposals") or {}
    lines += ["", f"## Gate 1 proposals ({block.get('gate_weight')})", "",
              "FOR THE EXECUTIVE, NOT FOR THE REPORT. Every line carries the count behind it."]
    if not block.get("any"):
        lines.append("Nothing to propose: the categories stand as the profile has them.")
    lines += [f"- ADD a category: {r['key']} ({r['items']} items, {r['hours']} meeting hours). {r['reason']}"
              for r in block.get("add_category") or []]
    lines += [f"- DROP this week: {r['name']}. {r['reason']}" for r in block.get("drop_this_week") or []]
    lines += [f"- FOLD into the catch-all: {r['name']}. {r['reason']}" for r in block.get("fold_into_other") or []]
    lines += [f"- CATCH-ALL candidate: [{r['kind']}] {one_line(r['title'])}; {one_line(r['detail'])} [{r['ref']}]"
              for r in block.get("other_topics_candidates") or []]
    lines.append(f"Carry-overs that have to be answered: {block.get('carry_overs_to_answer')}.")

    # The silences and continuity: Gate 2's question.
    silent, continuity = pack.get("silent") or {}, pack.get("continuity") or {}
    lines += ["", f"## Silent this period ({silent.get('count', 0)} items)", "",
              "Silence is not absence; only the owner can say whether one of these moved."]
    if silent.get("categories"):
        lines.append(f"Categories with no evidence: {', '.join(silent['categories'])}.")
    if silent.get("outline_projects"):
        lines.append(f"Projects the profile names that nothing matched: {', '.join(silent['outline_projects'])}.")
    lines += [f"- Goal, {g.get('priority')}, untouched: {one_line(g.get('title'))} [{g.get('ref')}]"
              for g in silent.get("goals") or []]
    missing = (pack.get("direct_reports") or {}).get("missing") or []
    if missing:
        lines.append(f"Direct reports with no update found: {', '.join(str(m) for m in missing)}.")
    lines += ["", f"### Continuity ({continuity.get('reports_read', 0)} earlier reports read)"]
    lines += [f"- {one_line(r.get('title'))}, {r.get('date')}, {r.get('bullets')} bullets [{r.get('ref')}]"
              for r in continuity.get("reports") or []] or ["No earlier report was found, so nothing carries over yet."]
    lines += [f"- CARRY-OVER in no category, **{one_line(x.get('label'))}**: {one_line(x.get('text'), 200)} "
              f"({one_line(x.get('reason'))})" for x in continuity.get("carry_overs_unassigned") or []]

    goals = pack.get("goals") or []
    lines += ["", f"## Goals ({len(goals)})", ""] + ([
        f"- {one_line(g.get('title'))}" + (f"; {', '.join(str(g[k]) for k in ('priority', 'horizon', 'status') if g.get(k))}"
                                           if opts["goal_detail"] else "") + f" [{g.get('_ref') or g.get('ref')}]"
        for g in goals] or ["None on this scope."])

    calendar = pack.get("calendar") or {}
    span, ahead = calendar.get("period") or {}, calendar.get("lookahead") or {}
    lines += ["", "## Calendar [pack://calendar]", "",
              "FOR THE OWNER AND NOT FOR THE REPORT. Meeting time is never a bullet; pack://calendar is the "
              "reference where a gate answer turns on one of these totals.",
              f"In scope this period: {span.get('meetings_in_scope')} meetings, {span.get('hours_sum')} hours summed"
              + (f", {span['hours_union']} as wall clock, {span.get('double_booked_hours')} double booked, against "
                 f"{span.get('all_meetings_hours_sum')} hours of meetings of every kind" if "hours_union" in span else "")
              + "."]
    if span.get("by_day"):
        lines.append("Hours by day: " + "; ".join(f"{d} {h}" for d, h in span["by_day"].items()) + ".")
    if ahead:
        lines.append(f"Look-ahead: {ahead.get('meetings_in_scope')} meetings, {ahead.get('hours_sum')} hours.")
        if opts["lookahead_items"]:
            lines += [f"- {m.get('start_local')}, {m.get('hours')} hours, {one_line(m.get('title'))} [{m.get('ref')}]"
                      for m in ahead.get("items") or []]

    provenance = pack.get("provenance") or {}
    lines += ["", "## Could not be determined", ""]
    lines += [f"- {one_line(x.get('what'))}: {one_line(x.get('why'))}" if isinstance(x, dict) else f"- {one_line(x)}"
              for x in provenance.get("could_not_determine") or []] or ["Nothing."]
    if provenance.get("warnings"):
        lines += ["", "## Warnings from the read", ""] + [f"- {one_line(w)}" for w in provenance["warnings"]]
    lines += ["", "## Caps that fired", ""]
    lines += [f"- In the pack: {one_line(c)}" for c in provenance.get("caps_applied") or []]
    lines += [f"- In this digest: {c}" for c in fired]
    if not provenance.get("caps_applied") and not fired:
        lines.append("None. Nothing was cut.")
    return "\n".join(lines).rstrip() + "\n"


def build(pack):
    """(the digest, its stats). The ladder runs only as far as the target needs, and a cut is
    kept only when it made the digest shorter."""
    opts, fired = defaults(), []
    text = render(pack, opts, fired)
    for steps, limit in ((LADDER, TARGET_CHARS), (FORCED, HARD_CAP_CHARS)):
        for key, value, reason in steps:
            if len(text) <= limit:
                break
            previous = opts[key]
            opts[key] = value
            trial = render(pack, opts, fired + [reason])
            if len(trial) < len(text) - len(reason) - 20:
                fired.append(reason)
                text = trial
            else:
                opts[key] = previous
    return text, {"characters": len(text), "lines": text.count("\n"), "caps_applied": fired,
                  "over_target": len(text) > TARGET_CHARS, "over_hard_cap": len(text) > HARD_CAP_CHARS}
