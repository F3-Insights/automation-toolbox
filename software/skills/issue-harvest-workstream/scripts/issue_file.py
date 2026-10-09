#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""File a harvest Run's decided issues and comments on GitHub: the one writer, run after the session.

The session writes RUN/decisions.json, one decision per queued source item (new, comment,
duplicate, not-software, ask). This script makes the `new` and `comment` decisions real and
nothing else: it creates issues and adds comments. There is no path that edits, relabels,
closes, reopens or deletes anything.

Each write is refused, with the reason, unless all of these hold:
- the repository is in the repo map with `harvest: true` (read fresh from the settings, never
  from the Run folder);
- the source item was queued by this Run's harvest.json;
- the checker passed it (`"check": "PASS"`);
- the title and body carry no home-folder path, nothing shaped like a secret and, on every
  repository, none of the owner's private terms (setting `private_terms`, a list, matched as
  whole words ignoring case); and, for a `public: true` repository, none of the owner's private
  names (setting `public_denylist_files`; a public repository with no readable list is refused);
- a new issue's title fits the repository's `title.pattern` when the map gives one;
- a comment's issue exists;
- the Run has not reached --max-writes (30).

One source item filed in several parts carries `part` on each decision; each part is marked
`<key>#<part>`. Before writing, the repository is searched for the item's marker and for an open
issue with the same title; either answers `already` and writes nothing, so a re-run never files
twice. Labels are the decision's, the kind's and the map's `always` labels, kept only when the
map allows them and the repository has them (no label is ever created). Every body ends with the
source line and the markers; each write is read back and must show its marker (`verified`).

Writes RUN/filed.json (RUN/filed-dry-run.json on a dry run), never overwriting one, and the intent
record RUN/filing.json before the first write and after each. A decisions.json with
`"dry_run": true` is always a dry run. Prints `FILED: 3 issue(s), 1 comment(s); 2 already on
GitHub; 1 refused; 0 failed` (`WOULD FILE: ...`). Exit 0 when it ran, 3 when a write failed or
was not found back, 2 when RUN is not a folder or the settings are unusable.

Example:
    python3 issue_file.py --run /runs/2030-01-07 --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import _common as c

WRITES = ("new", "comment")
MAX_WRITES_DEFAULT = 30
URL_NUMBER = re.compile(r"/issues/(\d+)")


class Refused(Exception):
    """A guard said no to one write."""


def source_line(item, cfg):
    templates = cfg.get("source_links") or {}
    ident = str(item.get("key") or "").split(":", 1)[-1]
    link = str(templates.get(item.get("source")) or "").replace("{id}", ident) or str(item.get("ref") or item.get("key"))
    title = " ".join(str(item.get("title") or item.get("source") or "").split())[:120]
    return f"- {title} ({item.get('date') or 'undated'}): {link}"


def compose(body, items, cfg, keys):
    """The body, one source line per item carried, and one marker per key."""
    lines = [body.strip(), "", "---", "Harvested by the issue harvest from:"]
    lines += [source_line(i, cfg) for i in items]
    lines += [""] + [c.marker(k) for k in keys]
    return "\n".join(lines) + "\n"


def wanted_labels(decision, entry, existing):
    """The labels to apply (allowed by the map and present on the repository), and those dropped."""
    allowed = {lb for labels in entry["labels"].values() for lb in labels}
    asked = [str(x) for x in decision.get("labels") or []]
    asked += entry["labels"].get(str(decision.get("kind") or ""), []) + entry["labels"].get("always", [])
    have = {e.lower(): e for e in existing}
    keep, dropped = [], []
    for lb in dict.fromkeys(asked):
        if lb in allowed and lb.lower() in have:
            keep.append(have[lb.lower()])
        else:
            dropped.append(lb)
    return keep, dropped


def load_names(paths):
    """Private names, one per line, from the denylist files; `#` lines and blanks skipped."""
    names = []
    for p in paths:
        try:
            lines = Path(str(p)).expanduser().read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        names += [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#") and len(ln.strip()) >= 3]
    return names


def private_terms(cfg):
    """The setting `private_terms`: under this skill's table, else at the top of the settings file."""
    raw = cfg.get("private_terms")
    if raw is None:
        raw = c.settings().get("private_terms")
    return [t.strip() for t in c.as_list(raw) if len(t.strip()) >= 3]


def whole_word(term, text):
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", text, re.I) is not None


def guard_text(title, body, entry, names, terms=()):
    text = f"{title}\n{body}"
    hits = [name for name, pattern in c.PRIVATE if pattern.search(text)]
    if any(whole_word(t, text) for t in terms):
        hits.append("a private term (setting private_terms)")
    if hits:
        raise Refused("private content: " + "; ".join(hits))
    if len(title) > c.TITLE_MAX:
        raise Refused(f"the title is longer than {c.TITLE_MAX} characters")
    if len(body) > c.BODY_MAX:
        raise Refused(f"the body is longer than {c.BODY_MAX} characters")
    if entry["public"]:
        if not names:
            raise Refused("a public repository, and no private-names list could be read to check against")
        found = sum(1 for n in names if whole_word(n, text))
        if found:
            raise Refused(f"a public repository, and the text carries {found} private name(s)")


def create(repo, title, body, labels):
    args = ["issue", "create", "-R", repo.name, "--title", title, "--body-file", "-"]
    for lb in labels:
        args += ["--label", lb]
    out = c.gh_ok("gh issue create", *args, input=body)
    m = URL_NUMBER.search(out)
    if not m:
        raise c.GitHubError("gh issue create did not return an issue URL; check the repository before filing again")
    return int(m.group(1))


def add_comment(repo, number, body):
    c.gh_ok("gh issue comment", "issue", "comment", str(number), "-R", repo.name, "--body-file", "-", input=body)


def comment_with_marker(view, key):
    return next((cm for cm in view.get("comments") or [] if isinstance(cm, dict) and c.has_marker(cm.get("body"), key)),
                None)


def act(d, items, repos, cfg, names, cache, dry, terms=()):
    """One decision: refused, already, would_file/would_comment, filed/commented, or failed."""
    key = str(d.get("source") or "")
    kind = str(d.get("decision") or "")
    mkey = c.part_key(key, d.get("part"))
    out = {"source": key, "decision": kind, "repo": d.get("repo"), "status": None, "key": mkey}
    if d.get("part"):
        out["part"] = str(d.get("part"))
    try:
        if key not in items:
            raise Refused("the source item was not queued by this Run's harvest.json")
        if str(d.get("check") or "").upper() != "PASS":
            raise Refused("the checker did not pass it")
        entry = c.repo_entry(repos, str(d.get("repo") or ""))
        if entry is None or not entry["harvest"]:
            raise Refused(f"{d.get('repo')!r} is not a repository the repo map lets the harvest file on")
        out["repo"] = entry["repo"]
        if not str(d.get("body") or "").strip():
            raise Refused("a body is required")
        carried = [items[key]] + [items[k] for k in d.get("also") or [] if k in items and k != key]
        keys = [mkey] + [i["key"] for i in carried[1:]]
        body = compose(str(d.get("body")), carried, cfg, keys)
        repo = cache.setdefault(entry["repo"], c.Repo(entry["repo"]))
        if kind == "new":
            title = " ".join(str(d.get("title") or "").split())
            if not title:
                raise Refused("a title is required")
            pattern = entry["title"]["pattern"]
            if pattern and not re.match(pattern, title):
                raise Refused(f"the title does not follow the repository's convention "
                              f"({entry['title']['convention'] or pattern})")
            guard_text(title, body, entry, names, terms)
            found = next((hit for k in keys if (hit := repo.with_marker(k))), None)
            if found:
                return dict(out, status="already", issue=found.get("number"), url=found.get("url"),
                            why="an issue already carries this source's marker")
            same = repo.open_titled(title)
            if same:
                return dict(out, status="already", issue=same.get("number"), url=same.get("url"),
                            why="an open issue has exactly this title")
            labels, dropped = wanted_labels(d, entry, repo.labels())
            out.update(title=title, labels=labels, labels_dropped=dropped, body_chars=len(body))
            if dry:
                return dict(out, status="would_file")
            number = create(repo, title, body, labels)
            back = repo.view(number)
            return dict(out, status="filed", issue=number, url=back.get("url"), verified=c.has_marker(back.get("body"), mkey))
        try:
            number = int(d.get("issue"))
        except (TypeError, ValueError):
            raise Refused("a comment needs the issue number") from None
        guard_text("", body, entry, names, terms)
        view = repo.view(number)
        if not view.get("number"):
            raise Refused(f"{entry['repo']}#{number} was not found")
        out.update(issue=number, body_chars=len(body))
        hit = comment_with_marker(view, mkey)
        if hit:
            return dict(out, status="already", url=hit.get("url"), why="the issue already has this source's comment")
        if dry:
            return dict(out, status="would_comment", url=view.get("url"))
        add_comment(repo, number, body)
        back = comment_with_marker(repo.view(number), mkey)
        return dict(out, status="commented", url=(back or {}).get("url") or view.get("url"), verified=bool(back))
    except Refused as exc:
        return dict(out, status="refused", why=str(exc))
    except c.GitHubError as exc:
        return dict(out, status="failed", why=c.safe(exc)[:400])


def journal(path, result, planned, state):
    """The intent record: what will be written and what has been, so a crash leaves a trace."""
    if path is None:
        return
    data = {"tool": "issue-file", "state": state, "at": c.now_iso(), "planned": planned, "results": result["results"]}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_failed(result):
    """True when a write failed or a write was not found back."""
    return any(r.get("status") == "failed" or (r.get("status") in ("filed", "commented") and not r.get("verified"))
               for r in result.get("results") or [])


def run(run_dir, cfg, repos, dry, max_writes):
    harvest = c.load_json(run_dir / "harvest.json")
    decisions = c.load_json(run_dir / "decisions.json")
    result = {"tool": "issue-file", "run": str(run_dir), "at": c.now_iso(), "dry_run": dry, "results": [],
              "counts": {}, "headline": ""}
    if harvest is None or decisions is None:
        result["headline"] = "NOTHING: no harvest.json or decisions.json in the Run folder; nothing to file"
        return result
    if decisions.get("dry_run") is True:
        dry = result["dry_run"] = True
    items = {str(i.get("key")): i for i in harvest.get("items") or [] if isinstance(i, dict)}
    writes = [d for d in decisions.get("decisions") or [] if isinstance(d, dict) and d.get("decision") in WRITES]
    names = load_names(c.as_list(cfg.get("public_denylist_files")))
    terms = private_terms(cfg)
    cache = {}
    jpath = None if dry or not writes else run_dir / "filing.json"
    planned = [{"source": d.get("source"), "decision": d.get("decision"), "repo": d.get("repo"),
                "key": c.part_key(str(d.get("source") or ""), d.get("part"))} for d in writes[:max_writes]]
    journal(jpath, result, planned, "filing")
    for n, d in enumerate(writes):
        if n >= max_writes:
            result["results"].append({"source": d.get("source"), "decision": d.get("decision"), "repo": d.get("repo"),
                                      "status": "refused", "why": f"past the cap of {max_writes} writes in one Run"})
            continue
        result["results"].append(act(d, items, repos, cfg, names, cache, dry, terms))
        journal(jpath, result, planned, "filing")
    journal(jpath, result, planned, "done")
    counts = {}
    for r in result["results"]:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    result["counts"] = counts
    tail = (f"{counts.get('already', 0)} already on GitHub; {counts.get('refused', 0)} refused; "
            f"{counts.get('failed', 0)} failed")
    if not writes:
        result["headline"] = "NOTHING: the session decided no new issue and no comment"
    elif dry:
        result["headline"] = (f"WOULD FILE: {counts.get('would_file', 0)} issue(s), "
                              f"{counts.get('would_comment', 0)} comment(s); {tail}")
    else:
        lost = sum(1 for r in result["results"] if r["status"] in ("filed", "commented") and not r.get("verified"))
        result["headline"] = (f"FILED: {counts.get('filed', 0)} issue(s), {counts.get('commented', 0)} comment(s); "
                              f"{tail}" + (f"; {lost} not found back" if lost else ""))
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="File the Run's decided issues and comments under the repo map's allowlist.")
    p.add_argument("--run", dest="run_dir", required=True, help="the Run folder (harvest.json and decisions.json)")
    p.add_argument("--dry-run", action="store_true", help="check and read everything; write nothing")
    p.add_argument("--dry-run-if", default="", help="a dry run when this is true (a launch form's dry_run)")
    p.add_argument("--max-writes", default="", help=f"the most writes in one Run (default {MAX_WRITES_DEFAULT})")
    p.add_argument("--repos-file", default="", help="the repo map (default: setting repos_file)")
    a = p.parse_args(argv)
    try:
        folder = Path(a.run_dir).expanduser()
        if not folder.is_dir():
            raise ValueError(f"{folder} is not a Run folder")
        cfg = c.harvest_settings()
        repos = c.load_repos(cfg, a.repos_file)
        cap = c.whole_number(a.max_writes, "max-writes", MAX_WRITES_DEFAULT, 1, 500)
        result = run(folder, cfg, repos, a.dry_run or c.truthy(a.dry_run_if), cap)
        c.write_new(folder / ("filed-dry-run.json" if result["dry_run"] else "filed.json"), result)
    except (c.ConfigError, ValueError, FileExistsError) as exc:
        print(f"issue-file: {exc}", file=sys.stderr)
        return 2
    print(result["headline"])
    for r in result["results"]:
        where = f"{r.get('repo')}#{r.get('issue')}" if r.get("issue") else str(r.get("repo"))
        print(f"  {r['status']}: {r['source']} -> {where}" + (f" ({r['why']})" if r.get("why") else ""))
    return 3 if write_failed(result) else 0


if __name__ == "__main__":
    sys.exit(main())
