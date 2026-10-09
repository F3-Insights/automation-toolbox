#!/usr/bin/env python3
"""find-contact: a name or an email address, to the Portal contacts it could mean.

Step 1 of comms-reply-to-email. It pins a contact only when exactly one contact matches
exactly; it never picks among several, and a near match is listed, not chosen. Read only.

An address is looked up as the contact's natural key and confirmed against the contact's own
addresses. A name goes through the Portal's ranked search, and each contact found is read for
its addresses and company. A match is exact when the full name, ignoring case, accents and
punctuation, equals the query, or when the query is one of its addresses.

Input: the name or address. Prints one JSON object (`verdict` one, several, partial or none;
`pinned`; `candidates`). Exit 0 when one contact is pinned, 3 when none or several could be,
2 on an error.

Example:
    python3 find_contact.py "Dana Whitfield"
"""

import argparse
import re
import unicodedata

import _common as c

MAX_CANDIDATES = 10


def norm_name(text):
    folded = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^\w\s]", " ", folded).split()).casefold()


def card(hydrated, fallback):
    """One candidate's summary from its full record, or from the search hit when unreadable."""
    record = hydrated.get("contact") if isinstance(hydrated.get("contact"), dict) else {}
    company = hydrated.get("company") if isinstance(hydrated.get("company"), dict) else {}
    cid = record.get("id") or fallback.get("id")
    name = (record.get("full_name") or fallback.get("name")
            or " ".join(p for p in (record.get("first_name"), record.get("last_name")) if p) or "")
    return {"id": cid, "_ref": f"portal://contact/{cid}", "name": name,
            "addresses": c.contact_addresses(hydrated),
            "company": company.get("name") or fallback.get("company_name"),
            "title": record.get("title") or fallback.get("job_title"),
            "is_active": record.get("is_active"),
            "merged_into_contact_id": record.get("merged_into_contact_id")}


def read_contact(portal, cid):
    out = portal.call("get", {"entity_type": "contact", "id_or_query": cid})
    return out if isinstance(out, dict) and not out.get("error") else {}


def find(portal, query):
    query = (query or "").strip()
    if len(query) < 2:
        raise c.Failure("give a name or an email address, at least two characters")
    address = c.bare_address(query) if "@" in query else ""
    candidates, notes = [], []

    if address:
        found = read_contact(portal, address)
        entry = card(found, {}) if found else None
        if entry and entry["id"]:
            candidates.append(entry)
        else:
            notes.append(f"no contact holds {address} as its natural key")

    searched = portal.call("search", {"query": query, "limit": MAX_CANDIDATES})
    hits = []
    if isinstance(searched, dict):
        hits = [h for h in searched.get("contacts") or [] if isinstance(h, dict) and h.get("id")]
        if searched.get("truncated"):
            notes.append("the search response was truncated by its byte budget")
    seen = {x["id"] for x in candidates}
    for hit in hits[:MAX_CANDIDATES]:
        if hit["id"] not in seen:
            seen.add(hit["id"])
            candidates.append(card(read_contact(portal, hit["id"]), hit))

    want = norm_name(query)
    for entry in candidates:
        if address:
            entry["match"] = "exact" if address in entry["addresses"] else "partial"
        else:
            entry["match"] = "exact" if norm_name(entry["name"]) == want else "partial"
        if entry.get("merged_into_contact_id"):
            entry["match"] = "merged"
    candidates.sort(key=lambda x: {"exact": 0, "partial": 1, "merged": 2}[x["match"]])
    exact = [x for x in candidates if x["match"] == "exact"]

    pinned = exact[0] if len(exact) == 1 else None
    if pinned:
        verdict, reason = "one", f"one contact matches {query!r} exactly"
    elif exact:
        verdict, reason = "several", f"{len(exact)} contacts match {query!r} exactly; the owner has to say which"
    elif candidates:
        verdict = "partial"
        reason = f"no contact matches {query!r} exactly; {len(candidates)} came close and none is chosen"
    else:
        verdict, reason = "none", f"no Portal contact matches {query!r}"
    return {"query": query, "verdict": verdict, "reason": reason,
            "pinned": {"contact_id": pinned["id"], "name": pinned["name"],
                       "addresses": pinned["addresses"]} if pinned else None,
            "exact_count": len(exact), "candidates": candidates, "notes": notes}


def main():
    parser = argparse.ArgumentParser(description="A name or email address to the Portal contacts it could "
                                                 "mean. Exit 0 one pinned, 3 none or several, 2 error.")
    parser.add_argument("query", help="a name or an email address")
    args = parser.parse_args()
    try:
        result = find(c.client(), args.query)
    except Exception as exc:  # a lookup that did not run is an error, never a "none"
        c.fail(exc if isinstance(exc, c.Failure) else f"find-contact could not complete: {type(exc).__name__}: {exc}")
    c.emit(result, c.OK if result["verdict"] == "one" else c.STOP)


if __name__ == "__main__":
    main()
