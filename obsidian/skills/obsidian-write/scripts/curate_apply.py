"""obsidian-curate-apply: the one writer of the vault curator's changes, with backups and undo.

The curator decides its changes in a session and its reviewer checks each one; this script
makes the ones marked "check": "PASS" after the session, and nothing else. It is the only way
an existing note in the vault changes (obsidian-write, rule 2).

    curate_apply.py --run RUN [--dry-run]          RUN/proposals.json; results to RUN/apply.json
    curate_apply.py --undo RUN_ID [--id c1] [--dry-run]

THE CHANGE SET (RUN/proposals.json)
  {"tool": "obsidian-curate", "version": 1, "mode": "curate", "dry_run": false,
   "changes": [
    {"id": "c1", "op": "splice", "target": "Area/Note.md", "hash": "<sha256 of the file as read>",
     "heading": "## Section", "text": "Lines to add at the end of that section", "check": "PASS",
     "source": "Inbox/Clip.md", "reason": "..."},
    {"id": "c2", "op": "replace", "kind": "link", "target": "...", "hash": "...",
     "old": "[[Old title]]", "new": "[[New title]]", "check": "PASS", "reason": "..."},
    {"id": "c3", "op": "move", "target": "Inbox/Clip.md", "hash": "...", "to": "Area/Sub", ...},
    {"id": "c4", "op": "mark_merged", "target": "Inbox/Clip.md", "hash": "...", "into": "Note",
     "to": "Inbox/merged", ...}]}

  splice       adds `text` at the end of the section under `heading` (an exact heading line that
               occurs once), or at the end of the note when `heading` is absent. Adds only.
  replace      `old` occurs exactly once and becomes `new`. `kind` says what may change:
               link         only wikilinks differ between old and new;
               frontmatter  old lies inside the frontmatter block, or, in a note with
                            none, old is its first line and new is a block followed by it;
               fact         new keeps the old text struck through (~~old~~).
  move         the note moves into folder `to`; an existing note there is never replaced.
  mark_merged  an inbox note gets `merged-into: "[[into]]"` in its frontmatter and moves to
               `to` (default <vault_inbox>/merged). Nothing is ever deleted.

THE RULES (a change that breaks one is refused; the others go on)
- Only changes with "check": "PASS" are made; any other is skipped as unchecked.
- The target is a note inside a curate folder (setting vault_curate_dirs) or the inbox
  (vault_inbox), never in a private folder, Obsidian's own folders or the trash. An inbox note
  takes only move and mark_merged. A move lands in a curate folder or the inbox.
- The target's sha256 is still `hash`, or the hash this script left after an earlier change to
  it in the same Run: a note the owner edited since it was read is refused.
- At most vault_curate_max_changes (default 25) changes are made per Run; the rest are skipped.
- Before each write the original goes to <state_dir>/obsidian-curate/<run id>/backup/, and the
  change is logged in undo.jsonl beside it. A line per change is appended to the inbox note
  "Curator log" (created on first use).

--undo restores each change of that Run, newest first, from its backup, and refuses a note
changed since the Run wrote it. --dry-run reads everything and writes nothing (results go to
RUN/apply-dry-run.json).

Prints one JSON object: a result per change (applied, refused or skipped, with a reason).
Exit 0 when it ran; 2 on a missing setting or a bad change set.

    python3 curate_apply.py --run /path/to/run --dry-run
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from _common import ALWAYS_SKIPPED, Vault, fail, settings

LOG_TITLE = "Curator log"
DEFAULT_CAP = 25
OPS = {"splice", "replace", "move", "mark_merged"}
HEADING_RE = re.compile(r"^(#{1,6})\s")
LINK_RE = re.compile(r"!?\[\[[^\]]*\]\]")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(folder):
    return os.path.normpath(str(folder).strip().replace("\\", "/")).strip("/")


class Scope:
    """Where the curator may write: the curate folders and the inbox, never a private folder."""

    def __init__(self, vault, curate_dirs, inbox):
        self.v = vault
        self.curate = [norm(d) for d in curate_dirs]
        self.inbox = norm(inbox) if inbox else None

    def _inside(self, rel, folders):
        low = rel.lower()
        return any(low == f.lower() or low.startswith(f.lower() + "/") for f in folders if f)

    def where(self, rel):
        """'curate', 'inbox' or None for a vault-relative path (file or folder)."""
        rel = norm(rel)
        if rel.startswith("..") or set(Path(rel).parts) & ALWAYS_SKIPPED or self.v.is_private(rel):
            return None
        real = (self.v.root / rel).resolve()
        if not real.is_relative_to(self.v.root) or self.v.is_private(real.relative_to(self.v.root).as_posix()):
            return None
        if self.inbox and self._inside(rel, [self.inbox]):
            return "inbox"
        return "curate" if self._inside(rel, self.curate) else None


def section_end(lines, heading):
    """Index after the last non-blank line of the section under `heading`, or None when the
    heading is not there exactly once."""
    hits = [i for i, line in enumerate(lines) if line.strip() == heading.strip()]
    if len(hits) != 1 or not HEADING_RE.match(lines[hits[0]]):
        return None
    level = len(HEADING_RE.match(lines[hits[0]]).group(1))
    end = next((j for j in range(hits[0] + 1, len(lines))
                if HEADING_RE.match(lines[j]) and len(HEADING_RE.match(lines[j]).group(1)) <= level), len(lines))
    while end > hits[0] + 1 and not lines[end - 1].strip():
        end -= 1
    return end


def frontmatter_span(text):
    """(start, end) character offsets of the frontmatter block, or None."""
    if not text.startswith("---\n"):
        return None
    m = re.search(r"^(---|\.\.\.)[ \t]*$", text[4:], re.MULTILINE)
    return (0, 4 + m.end()) if m else None


def do_splice(text, ch):
    add = ch.get("text", "").strip("\n")
    if not add.strip():
        return None, "empty text"
    if not ch.get("heading"):
        return text.rstrip("\n") + "\n\n" + add + "\n", None
    lines = text.split("\n")
    end = section_end(lines, ch["heading"])
    if end is None:
        return None, "heading not found exactly once"
    rest = lines[end:]
    while rest and not rest[0].strip():
        rest = rest[1:]
    tail = "\n\n" + "\n".join(rest) if rest else "\n"
    return "\n".join(lines[:end] + ["", add]) + tail, None


def do_replace(text, ch):
    old, new = ch.get("old", ""), ch.get("new", "")
    if not old or text.count(old) != 1:
        return None, "old text not found exactly once"
    kind = ch.get("kind")
    if kind == "link":
        if LINK_RE.sub("", old) != LINK_RE.sub("", new) or old == new:
            return None, "a link fix may change only wikilinks"
    elif kind == "frontmatter":
        span = frontmatter_span(text)
        if not span:  # a note without frontmatter gets a block in front of its first line
            block = new[:-len(old)] if new.endswith(old) else ""
            block_span = frontmatter_span(block)
            if not text.startswith(old) or not block_span or block[block_span[1]:].strip():
                return None, "a new frontmatter block goes in front of the note's first line, unchanged"
        else:
            at = text.index(old)
            if at < span[0] or at + len(old) > span[1] or "---" in new:
                return None, "old text is not inside the frontmatter"
    elif kind == "fact":
        if f"~~{old.strip()}~~" not in new:
            return None, "a fact fix keeps the old text struck through (~~old~~)"
    else:
        return None, "kind must be link, frontmatter or fact"
    return text.replace(old, new, 1), None


def set_merged_into(text, into):
    line = f'merged-into: "[[{into.strip("[]")}]]"'
    span = frontmatter_span(text)
    if not span:
        return f"---\n{line}\n---\n{text}"
    head = text[:span[1]]
    head = re.sub(r"^merged-into:.*$\n?", "", head, flags=re.MULTILINE)
    close = head.rstrip("\n").rfind("\n")
    return head[:close + 1] + line + "\n" + head[close + 1:] + text[span[1]:]


class Applier:
    def __init__(self, vault, scope, run_id, state, dry_run, cap):
        self.v, self.scope, self.run_id, self.dry, self.cap = vault, scope, run_id, dry_run, cap
        self.home = state / "obsidian-curate" / run_id
        self.left = {}  # target rel -> sha256 this Run left it with
        self.made = 0

    def check(self, ch):
        """The reason a change may not be made, or None."""
        if ch.get("check") != "PASS":
            return "skipped", "unchecked: the reviewer did not pass it"
        if ch.get("op") not in OPS:
            return "refused", f"unknown op {ch.get('op')!r}"
        if self.made >= self.cap:
            return "skipped", f"over the cap of {self.cap} changes per Run"
        rel = norm(ch.get("target", ""))
        where = self.scope.where(rel)
        path = self.v.root / rel
        if where is None:
            return "refused", "target is outside the curate folders and the inbox"
        if not rel.endswith(".md") or not path.is_file() or path.is_symlink():
            return "refused", "target is not a note"
        if where == "inbox" and ch["op"] not in ("move", "mark_merged"):
            return "refused", "an inbox note is only moved or marked merged"
        if ch["op"] == "mark_merged" and where != "inbox":
            return "refused", "only an inbox note is marked merged"
        current = sha256(path)
        if current != ch.get("hash") and current != self.left.get(rel):
            return "refused", "the note changed since it was read"
        return None

    def destination(self, ch, rel):
        to = norm(ch.get("to") or (f"{self.scope.inbox}/merged" if ch["op"] == "mark_merged" else ""))
        if not to or self.scope.where(to) is None:
            return None, "destination is outside the curate folders and the inbox"
        folder = self.v.root / to
        if not folder.is_dir() and not (ch["op"] == "mark_merged" and self.scope.where(to) == "inbox"):
            return None, "destination folder does not exist"
        dest = folder / Path(rel).name
        if dest.exists():
            return None, "a note of that name is already there"
        return dest, None

    def apply(self, ch):
        verdict = self.check(ch)
        if verdict:
            return {"id": ch.get("id"), "op": ch.get("op"), "target": ch.get("target"), "status": verdict[0],
                    "reason": verdict[1]}
        rel = norm(ch["target"])
        path = self.v.root / rel
        text = path.read_text(encoding="utf-8")
        dest, why = None, None
        if ch["op"] == "splice":
            new, why = do_splice(text, ch)
        elif ch["op"] == "replace":
            new, why = do_replace(text, ch)
        elif ch["op"] == "move":
            new = text
            dest, why = self.destination(ch, rel)
        else:
            new = set_merged_into(text, ch.get("into", ""))
            dest, why = self.destination(ch, rel) if ch.get("into", "").strip("[] ") else (None, "no into")
        out = {"id": ch["id"], "op": ch["op"], "target": rel}
        if why:
            return {**out, "status": "refused", "reason": why}
        final = dest or path
        out_rel = final.relative_to(self.v.root).as_posix()
        if self.dry:
            self.made += 1
            return {**out, "status": "applied", "reason": "dry run: would apply", "now_at": out_rel}
        backup = self.home / "backup" / ch["id"] / Path(rel).name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        if dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "x", encoding="utf-8", newline="") as fh:
                fh.write(new)
            path.unlink()
        else:
            path.write_text(new, encoding="utf-8", newline="")
        after = sha256(final)
        self.left[out_rel] = after
        self.made += 1
        with open(self.home / "undo.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": ch["id"], "op": ch["op"], "target": rel, "now_at": out_rel,
                                 "backup": str(backup), "hash_after": after}) + "\n")
        return {**out, "status": "applied", "reason": ch.get("reason", ""), "now_at": out_rel}


def log_lines(run_id, mode, results):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"## {stamp} {run_id} ({mode})", ""]
    for r in results:
        if r["status"] == "skipped" and r["reason"].startswith("unchecked"):
            continue
        link = f"[[{Path(r.get('now_at') or r['target']).with_suffix('').as_posix()}]]"
        undo = f" (undo: {run_id} {r['id']})" if r["status"] == "applied" else ""
        lines.append(f"- {r['status']} {r['op']} {link}: {r['reason']}{undo}")
    return lines


def append_log(vault, inbox, lines):
    if len(lines) <= 2:
        return None
    path = vault.root / inbox / f"{LOG_TITLE}.md"
    body = "\n".join(lines) + "\n"
    if not path.exists():
        with open(path, "x", encoding="utf-8") as fh:
            fh.write(f"# {LOG_TITLE}\n\nWhat the vault curator changed, newest last. Undo a change with "
                     f"`obsidian-curate-apply --undo <run> --id <id>`.\n\n" + body)
    else:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n" + body)
    return str(path)


def load_settings(vault_arg):
    conf = settings()
    vault = Vault(vault_arg)
    curate, inbox, state = conf.get("vault_curate_dirs"), conf.get("vault_inbox"), conf.get("state_dir")
    missing = [k for k, val in (("vault_curate_dirs", curate), ("vault_inbox", inbox), ("state_dir", state)) if not val]
    if missing:
        fail(f"Missing setting(s): {', '.join(missing)}; nothing was changed.", 2)
    cap = int(conf.get("vault_curate_max_changes", DEFAULT_CAP))
    return vault, Scope(vault, curate, inbox), Path(state).expanduser(), cap


def undo(vault, scope, state, run_id, only, dry):
    log = state / "obsidian-curate" / run_id / "undo.jsonl"
    if not log.is_file():
        fail(f"No undo log for Run {run_id} at {log}.", 2)
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    for row in reversed(rows):
        if only and row["id"] not in only:
            continue
        now, orig = vault.root / row["now_at"], vault.root / row["target"]
        out = {"id": row["id"], "op": row["op"], "target": row["target"]}
        if row.get("undone"):
            results.append({**out, "status": "skipped", "reason": "already undone"})
        elif not now.is_file() or sha256(now) != row["hash_after"]:
            results.append({**out, "status": "refused", "reason": "the note changed since the Run wrote it"})
        elif now != orig and orig.exists():
            results.append({**out, "status": "refused", "reason": "a note is back at the original path"})
        else:
            if not dry:
                orig.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(row["backup"], orig)
                if now != orig:
                    now.unlink()
                row["undone"] = True
            results.append({**out, "status": "applied", "reason": "restored from backup" + (" (dry run)" if dry else "")})
    if not dry:
        log.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        undone = [r for r in results if r["status"] == "applied"]
        append_log(vault, scope.inbox, [f"## Undo of {run_id}", ""] + [
            f"- undone {r['op']} [[{Path(r['target']).with_suffix('').as_posix()}]]" for r in undone])
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make the curator's reviewed changes, with backups and undo.")
    ap.add_argument("--run", help="the Run folder holding proposals.json")
    ap.add_argument("--undo", metavar="RUN_ID", help="undo the changes of this Run (its folder name)")
    ap.add_argument("--id", action="append", default=[], help="with --undo: only this change (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="read everything, write nothing")
    ap.add_argument("--vault", help="vault root (default: setting vault_dir)")
    args = ap.parse_args(argv)
    if bool(args.run) == bool(args.undo):
        fail("Give --run RUN or --undo RUN_ID.", 2)
    vault, scope, state, cap = load_settings(args.vault)

    if args.undo:
        results = undo(vault, scope, state, args.undo, set(args.id), args.dry_run)
        print(json.dumps({"undo": args.undo, "dry_run": args.dry_run, "results": results}, indent=1))
        return 0

    run = Path(args.run).expanduser().resolve()
    try:
        data = json.loads((run / "proposals.json").read_text(encoding="utf-8"))
        changes = data["changes"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        fail(f"Cannot read {run / 'proposals.json'}: {exc}", 2)
    ids = [c.get("id") for c in changes]
    if any(not i for i in ids) or len(set(ids)) != len(ids):
        fail("Every change needs a unique id; nothing was changed.", 2)
    dry = args.dry_run or bool(data.get("dry_run"))
    applier = Applier(vault, scope, run.name, state, dry, cap)
    results = [applier.apply(ch) for ch in changes]
    log = None if dry else append_log(vault, scope.inbox, log_lines(run.name, data.get("mode", "curate"), results))
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    out = {"run": run.name, "dry_run": dry, "counts": counts, "log_note": log, "results": results}
    (run / ("apply-dry-run.json" if dry else "apply.json")).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
