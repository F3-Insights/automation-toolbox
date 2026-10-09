"""What the process-flow scripts share: settings, the engagement and its folders, the source
register, the map file and the claim ledger.

An engagement is named by a Context: a YAML file with a `name` and a `sources:` list of
`{name, kind: folder, path}`. A Context name is looked up in the folder the owner setting
`contexts_dir` names (`<name>.yaml`, then `<subfolder>/<name>.yaml`); a value with a `/` or a
`.yaml` suffix is the path to a Context file. The folder Sources read here, by name:

- `engagement` (or `working`): the working folder, holding PROCESS-FLOW-RULES.md, BACKGROUND.md
  and one folder per process, `process-flows/<process>/`.
- `transcripts*`: first-person evidence. Without one, the working folder's `transcripts/`.
- `background*`: documents the mapper and fact-checkers read.
- `delivery`: where first drafts go, as new files only (see resolve_delivery).
- `rules`: a folder holding the rules file and BACKGROUND.md when they are kept apart.
- `engagement-*`: the client's own folders, read only.

A staged work folder is what process_flow_prepare.py writes into a Run folder: the process
folder's state plus `engagement.json` and the converted sources. Nothing about any one
engagement lives here; the rules file and the Context hold it.
"""

import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import tomllib
import zipfile
from pathlib import Path
from xml.etree import ElementTree

SKILL = "process-flow-workstream"
RULES_FILE = "PROCESS-FLOW-RULES.md"
BACKGROUND_FILE = "BACKGROUND.md"
PROCESS_ROOT = "process-flows"
STAGED_MARKER = "engagement.json"
SOURCES_FILE = "sources.json"
LEDGER_FILE = "CLAIM-LEDGER.csv"
SCOPES = ("as-is", "as-is-and-to-be")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,59}$")

TRANSCRIPT_EXT = (".srt", ".vtt", ".txt", ".md", ".docx")
TEXT_EXT = (".txt", ".md", ".csv")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")
DOC_EXT = (".docx", ".pptx", ".xlsx", ".xlsm", ".pdf")
SKIP_NAMES = ("desktop.ini", ".ds_store", "thumbs.db")
IMAGE_WEIGHT = 20_000  # an image read as a source is about this much reading


class EngagementError(ValueError):
    """A Context, folder, setting or argument that cannot be used: exit 2."""


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


# --------------------------------------------------------------------------- small helpers


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path, data):
    """Write JSON through a temporary file, so a reader never sees half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_text(path):
    """A text file in UTF-8, UTF-16 or, failing both, Windows-1252."""
    data = Path(path).read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):  # a byte-order mark some editors put first
        data = data[3:]
    for enc in ("utf-8", "utf-16"):
        try:
            text = data.decode(enc)
            if enc == "utf-16" and "\x00" in text:
                continue
            return text
        except UnicodeDecodeError:
            continue
    return data.decode("cp1252", errors="replace")


def latest(folder, pattern):
    """(version, path) of the highest-numbered file in folder named by pattern ({v} the
    version), or (0, None)."""
    rx = re.compile("^" + re.escape(pattern).replace(re.escape("{v}"), r"(\d+)") + "$")
    found = []
    if Path(folder).is_dir():
        for p in Path(folder).iterdir():
            m = rx.match(p.name)
            if m and p.is_file():
                found.append((int(m.group(1)), p))
    return max(found) if found else (0, None)


def free_name(path):
    """path if it does not exist, else 'name (2).ext', 'name (3).ext' ..."""
    path, n = Path(path), 2
    candidate = path
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    return candidate


def blank(value):
    """A launch form leaves a field blank as --x=: an empty value is not given."""
    value = (value or "").strip()
    return value or None


def is_staged(ref):
    p = Path(ref).expanduser()
    return p.is_dir() and (p / STAGED_MARKER).is_file()


# --------------------------------------------------------------------------- the rules file

FIELD_RE = re.compile(r"^\s*(?:[-*]\s+)?\**([A-Za-z][A-Za-z /-]{1,40}?)\**\s*:\s+(.+?)\s*$")
PROCESS_HEAD_RE = re.compile(r"^#{2,3}\s+Process:\s*([a-z0-9-]+)\s*$", re.I)


def parse_rules(text):
    """The rules file's '- Key: value' lines, keys lowercased; '## Process: <slug>' sections
    hold per-process overrides under 'processes'. The first line of a key wins."""
    out = {"processes": {}}
    target = out
    for line in text.splitlines():
        head = PROCESS_HEAD_RE.match(line)
        if head:
            target = out["processes"].setdefault(head.group(1).lower(), {})
            continue
        m = FIELD_RE.match(line)
        if m and m.group(1).strip().lower() not in target:
            target[m.group(1).strip().lower()] = m.group(2).strip()
    return out


def rule_list(value):
    return [v.strip() for v in re.split(r"[,;]", value or "") if v.strip()]


def load_rules(folder, process=None):
    """(fields for this process, whole parsed file, path or None). A process's own section
    overrides the file's defaults."""
    path = Path(folder) / RULES_FILE if folder else None
    parsed = parse_rules(read_text(path)) if path and path.is_file() else {"processes": {}}
    fields = {k: v for k, v in parsed.items() if k != "processes"}
    if process and process in parsed["processes"]:
        fields.update(parsed["processes"][process])
    return fields, parsed, path if path and path.is_file() else None


def default_process(parsed):
    if parsed.get("default process"):
        return parsed["default process"].strip().lower()
    if len(parsed.get("processes") or {}) == 1:
        return next(iter(parsed["processes"]))
    return None


# --------------------------------------------------------------------------- the engagement


def find_context(ref):
    """The Context file a name or path refers to."""
    name = blank(ref)
    if not name:
        raise EngagementError("ENGAGEMENT is required: a Context name or the path to a Context YAML file")
    if name.endswith((".yaml", ".yml")) or "/" in name or name.startswith("."):
        path = Path(name).expanduser()
        if not path.is_file():
            raise EngagementError(f"no Context file at {path}")
        return path
    library = settings().get("contexts_dir")
    if not library:
        raise EngagementError("the owner setting contexts_dir is needed to find a Context by name "
                              "(or pass the path to the Context file)")
    library = Path(library).expanduser()
    for candidate in [library / f"{name}{s}" for s in (".yaml", ".yml")] + \
            sorted(library.glob("*/*.yaml")) + sorted(library.glob("*/*.yml")):
        if candidate.is_file() and candidate.stem == name:
            return candidate
    raise EngagementError(f"no Context named {name!r} in {library}")


def load_engagement(ref):
    """The engagement a Context names, as a dict of its folders."""
    import yaml  # only a Context needs it; a staged folder does not

    path = find_context(ref)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise EngagementError(f"{path} could not be read as YAML: {type(exc).__name__}") from None
    if not isinstance(data, dict):
        raise EngagementError(f"{path} is not a Context: the top level is not a mapping")
    folders = []
    for s in data.get("sources") or []:
        if isinstance(s, dict) and str(s.get("kind") or "folder") == "folder":
            name, where = str(s.get("name") or "").strip(), str(s.get("path") or "").strip()
            if name and where and not where.startswith("portal://"):
                folders.append((name, Path(where).expanduser()))
    by = {}
    for n, p in folders:
        by.setdefault(n, p)
    label = str(data.get("name") or path.stem)
    working = by.get("engagement") or by.get("working")
    if working is None:
        raise EngagementError(f"Context '{label}' has no folder Source named 'engagement' (the working folder)")
    transcripts = [(n, p) for n, p in folders if n.startswith("transcripts")]
    if not transcripts:
        if not (working / "transcripts").is_dir():
            raise EngagementError(f"Context '{label}' has no folder Source named 'transcripts' and the "
                                  "working folder has no transcripts/ folder")
        transcripts = [("transcripts", working / "transcripts")]
    clients = list(dict.fromkeys(p for n, p in folders if n.lower().startswith("engagement-")))
    rules_dir = by.get("rules")
    standing = rules_dir if rules_dir and (rules_dir / RULES_FILE).is_file() else working
    return {"name": label, "context": str(path), "working": working, "standing": standing,
            "transcripts": transcripts, "background": [(n, p) for n, p in folders if n.startswith("background")],
            "delivery": by.get("delivery"), "client_folders": clients}


def describe(eng):
    return {"name": eng["name"], "context": eng["context"], "working": str(eng["working"]),
            "standing": str(eng["standing"]), "delivery": str(eng["delivery"]) if eng["delivery"] else None,
            "client_folders": [str(p) for p in eng["client_folders"]],
            "transcripts": [{"source": n, "path": str(p)} for n, p in eng["transcripts"]],
            "background": [{"source": n, "path": str(p)} for n, p in eng["background"]]}


def process_dir(eng, process):
    return eng["working"] / PROCESS_ROOT / process


def resolve_delivery(eng, process, client=None):
    """Where this process's drafts go, by the first rule that applies:

    1. the Context's `delivery` Source;
    2. the client's folder (the first `engagement-*` Source that exists), under the setting
       `client_subfolder` (default 'Process Flows') and the process;
    3. the setting `delivery_dir`, under the engagement's name and the process;
    4. nowhere, when none is set.

    The anchor is the folder that must already exist; publish creates folders below it, never
    it. A named client folder that is missing, or a delivery_dir that does not exist, is an
    error: drafts never go to a guessed folder."""
    own = settings(SKILL)
    if eng["delivery"]:
        return {"delivery": str(eng["delivery"]), "delivery_anchor": str(eng["delivery"].parent),
                "delivery_basis": "the Context's delivery Source"}
    if eng["client_folders"]:
        found = next((p for p in eng["client_folders"] if p.is_dir()), None)
        if found is None:
            raise EngagementError("the Context names client folder(s) "
                                  + ", ".join(str(p) for p in eng["client_folders"])
                                  + " but none exists; fix the engagement-* Source (no folder is guessed)")
        sub = str(own.get("client_subfolder") or "Process Flows").strip().strip("/")
        if any(part in ("", ".", "..") for part in sub.split("/")):
            raise EngagementError(f"setting [{SKILL}] client_subfolder {sub!r} is not a relative folder")
        return {"delivery": str(found / sub / process), "delivery_anchor": str(found),
                "delivery_basis": "the client's folder"}
    root = blank(str(own.get("delivery_dir") or ""))
    if root:
        base = Path(root).expanduser()
        if not base.is_dir():
            raise EngagementError(f"the process delivery folder {base} (setting [{SKILL}] delivery_dir) "
                                  "does not exist; create it or fix the setting")
        why = "the owner's process delivery folder (no client folder in the Context"
        why += f"; the rules name the client {client!r})" if client else ")"
        folder = re.sub(r"[\\/:*?\"<>|]+", "-", eng["name"]).strip().strip(".") or "engagement"
        return {"delivery": str(base / folder / process), "delivery_anchor": str(base), "delivery_basis": why}
    return {"delivery": None, "delivery_anchor": None,
            "delivery_basis": "none: no delivery Source, no client folder and no process delivery folder set"}


# --------------------------------------------------------------------------- sources


def _matches(name, patterns):
    return any(fnmatch.fnmatch(name.lower(), p.lower()) for p in patterns)


def scan_sources(eng, rules):
    """Every usable source file, as dicts {folder, rel, path, kind, key}. Hidden files, Office
    lock files and what the rules file's Exclude names are skipped; in a transcripts folder a
    file is a transcript when it matches 'Transcript files' (or, with none listed, by type)."""
    excludes = rule_list(rules.get("exclude"))
    patterns = rule_list(rules.get("transcript files"))
    out, seen = [], set()
    for group, in_transcripts in ((eng["transcripts"], True), (eng["background"], False)):
        for name, folder in group:
            if not folder.is_dir():
                continue
            for p in sorted(folder.rglob("*")):
                rel = p.relative_to(folder).as_posix()
                if (not p.is_file() or any(part.startswith(".") for part in Path(rel).parts)
                        or p.name.startswith("~$") or p.name.lower() in SKIP_NAMES
                        or _matches(rel, excludes) or _matches(p.name, excludes) or p.resolve() in seen):
                    continue
                seen.add(p.resolve())
                ext = p.suffix.lower()
                if ext not in TRANSCRIPT_EXT + TEXT_EXT + IMAGE_EXT + DOC_EXT:
                    continue
                transcript = in_transcripts and ext in TRANSCRIPT_EXT and (not patterns or _matches(p.name, patterns))
                out.append({"folder": name, "rel": rel, "path": p, "key": f"{name}/{rel}",
                            "kind": "transcript" if transcript else "background"})
    return out


def assign_ids(found, registry):
    """Match found files to the register by key and give new ones the next free id (T01 a
    transcript, B01 background). Ids never change or get reused; a file that went away stays
    on the register as not present."""
    entries = {e["key"]: dict(e) for e in registry.get("sources") or [] if e.get("key")}
    used = {e["id"] for e in entries.values()}
    top = {"T": 0, "B": 0}
    for e in entries.values():
        m = re.match(r"^([TB])(\d+)$", e["id"])
        if m:
            top[m.group(1)] = max(top[m.group(1)], int(m.group(2)))
    out = []
    for f in found:
        e = entries.get(f["key"])
        if e is None:
            prefix = "T" if f["kind"] == "transcript" else "B"
            while True:
                top[prefix] += 1
                new_id = f"{prefix}{top[prefix]:02d}"
                if new_id not in used:
                    break
            used.add(new_id)
            e = {"id": new_id, "key": f["key"], "kind": f["kind"]}
        e.update({"folder": f["folder"], "file": f["rel"], "name": Path(f["rel"]).name,
                  "sha256": sha256_file(f["path"]), "bytes": f["path"].stat().st_size, "present": True})
        out.append(e)
    known = {e["key"] for e in out}
    for key, e in entries.items():
        if key not in known:
            e["present"] = False
            out.append(e)
    return sorted(out, key=lambda e: (e["id"][0], int(e["id"][1:]) if e["id"][1:].isdigit() else 0))


# --------------------------------------------------------------------------- conversion to text

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
TIMING_RE = re.compile(r"^\s*(?:(\d{1,2}):)?(\d{2}):(\d{2})[.,](\d{3})\s*-->")
VOICE_TAG_RE = re.compile(r"^<v\s+([^>]+)>\s*(.*)$", re.S)
PREFIX_RE = re.compile(r"^([A-Z][\w.'\- ]{0,60}?)\s*:\s+(.*)$", re.S)
HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


def subtitle_text(text):
    """An SRT or WebVTT export as '[MM:SS] Speaker: text' turns, consecutive cues of one speaker
    merged. The speaker is the <v Name> voice tag or a 'Name: ' prefix, else the previous one."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    turns, prev, i = [], None, 0
    while i < len(lines):
        m = TIMING_RE.match(lines[i])
        i += 1
        if not m:
            continue
        start = int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        body = []
        while i < len(lines) and lines[i].strip():
            body.append(lines[i].strip())
            i += 1
        raw = " ".join(body)
        v, p = VOICE_TAG_RE.match(raw), PREFIX_RE.match(raw)
        speaker, said = (v.group(1).strip(), v.group(2)) if v else (p.group(1).strip(), p.group(2)) if p else (prev, raw)
        said = HTML_TAG_RE.sub("", said).strip()
        if not said:
            continue
        if turns and turns[-1][1] == speaker:
            turns[-1][2] += " " + said
        else:
            turns.append([start, speaker, said])
        prev = speaker
    out = []
    for start, speaker, said in turns:
        h, mi, s = start // 3600, start % 3600 // 60, start % 60
        stamp = f"{h}:{mi:02d}:{s:02d}" if h else f"{mi:02d}:{s:02d}"
        out.append(f"{stamp} {speaker + ': ' if speaker else ''}{said}")
    return "\n".join(out) + "\n"


def docx_text(path):
    """Paragraph text of a .docx, tables as 'a | b' rows."""
    with zipfile.ZipFile(path) as z:
        body = ElementTree.fromstring(z.read("word/document.xml")).find(f"{W_NS}body")

    def para(p):
        parts = []
        for node in p.iter():
            if node.tag == f"{W_NS}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{W_NS}tab":
                parts.append("\t")
            elif node.tag in (f"{W_NS}br", f"{W_NS}cr"):
                parts.append("\n")
        return "".join(parts)

    lines = []
    for child in (body if body is not None else []):
        if child.tag == f"{W_NS}p":
            lines.append(para(child))
        elif child.tag == f"{W_NS}tbl":
            for row in child.iter(f"{W_NS}tr"):
                lines.append(" | ".join(" ".join(para(p) for p in tc.iter(f"{W_NS}p")).strip()
                                        for tc in row.iter(f"{W_NS}tc")))
    return "\n".join(lines).strip() + "\n"


def pptx_text(path):
    with zipfile.ZipFile(path) as z:
        names = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                       key=lambda n: int(re.findall(r"\d+", n)[-1]))
        slides = [[t.text for t in ElementTree.fromstring(z.read(n)).iter(f"{A_NS}t") if t.text] for n in names]
    return "\n\n".join(f"## Slide {i}\n" + "\n".join(t) for i, t in enumerate(slides, 1)).strip() + "\n"


def xlsx_text(path):
    try:
        import openpyxl
    except ImportError:
        return None
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"## Sheet {ws.title}")
        for row in ws.iter_rows():
            cells = [f"{c.coordinate}: {c.value}" for c in row if c.value not in (None, "") and hasattr(c, "coordinate")]
            if cells:
                out.append(" | ".join(cells))
    wb.close()
    return "\n".join(out).strip() + "\n"


def pdf_text(path):
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    try:
        res = subprocess.run([exe, "-layout", str(path), "-"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout if res.returncode == 0 else None


def convert(path):
    """(text or None, the staged file's extension, a note). Images are copied, not converted."""
    ext = path.suffix.lower()
    try:
        if ext in (".srt", ".vtt"):
            return subtitle_text(read_text(path)), ".txt", "collapsed from subtitles"
        if ext in TEXT_EXT:
            return read_text(path), ext if ext != ".csv" else ".txt", ""
        if ext == ".docx":
            return docx_text(path), ".md", "text of a Word document"
        if ext == ".pptx":
            return pptx_text(path), ".md", "text of a slide deck"
        if ext in (".xlsx", ".xlsm"):
            text = xlsx_text(path)
            return (text, ".md", "cells of a workbook") if text is not None else (None, "", "openpyxl not installed")
        if ext == ".pdf":
            text = pdf_text(path)
            return (text, ".txt", "text of a PDF") if text is not None else (None, "", "pdftotext not available")
        if ext in IMAGE_EXT:
            return None, ext, "image, copied"
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError, ValueError, KeyError) as exc:
        return None, "", f"could not convert: {exc}"
    return None, "", "unsupported format"


# --------------------------------------------------------------------------- duplicates and halves

STAMP_LINE_RE = re.compile(r"(?m)^\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\s")


def _shingles(text, k=8):
    text = re.sub(r"\[?\b\d{1,2}:\d{2}(?::\d{2})?(?:[,.]\d+)?\b\]?", " ", text)  # timestamps differ by format
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {" ".join(words[i:i + k]) for i in range(max(0, len(words) - k + 1))}


def find_duplicates(texts, exts):
    """Transcripts that record the same meeting (half or more of the smaller one's eight-word
    runs are in the other), as {duplicate_id: kept_id}. The one whose lines carry far more
    distinct timestamps is kept (a quote can be located in it); else a clean text over a
    subtitle export; else the larger."""
    ids = sorted(texts)
    sh = {i: _shingles(texts[i]) for i in ids}
    dup = {}
    for n, a in enumerate(ids):
        for b in ids[n + 1:]:
            if a in dup or b in dup or not sh[a] or not sh[b]:
                continue
            small, large = (a, b) if len(sh[a]) <= len(sh[b]) else (b, a)
            if len(sh[small] & sh[large]) / len(sh[small]) < 0.5:
                continue
            a_sub, b_sub = exts.get(a) in (".srt", ".vtt"), exts.get(b) in (".srt", ".vtt")
            a_loc, b_loc = len(set(STAMP_LINE_RE.findall(texts[a]))), len(set(STAMP_LINE_RE.findall(texts[b])))
            if a_loc != b_loc and max(a_loc, b_loc) >= 2 * max(1, min(a_loc, b_loc)):
                keep = a if a_loc > b_loc else b
            elif a_sub != b_sub:
                keep = b if a_sub else a
            else:
                keep = large
            dup[a if keep == b else b] = keep
    return dup


def balance_halves(entries):
    """Give each usable source a fact-check half, A or B: halves already given are kept, and
    each new source goes, largest first, into the lighter half by reading weight."""
    usable = [e for e in entries if e.get("present") and not e.get("duplicate_of") and e.get("evidence")]
    for e in entries:
        if e not in usable:
            e.pop("half", None)
    weight = {"A": 0, "B": 0}

    def load(e):
        return int(e.get("weight") or e.get("bytes") or 0)

    for e in usable:
        if e.get("half") in weight:
            weight[e["half"]] += load(e)
    for e in sorted((e for e in usable if e.get("half") not in weight), key=lambda e: (-load(e), e["id"])):
        e["half"] = "A" if weight["A"] <= weight["B"] else "B"
        weight[e["half"]] += load(e)


# --------------------------------------------------------------------------- the map file
#
# maps/map v<N>.json, schema process-flow-map/1; the process-flow-workstream skill shows the
# whole form. Every as-is step and callout cites a claim id. A to-be step is either the same
# step as an as-is one ("same_as") or a change, which names the pain claims it answers
# ("answers") and says why in one sentence.

SCHEMA = "process-flow-map/1"
KINDS = ("step", "dec", "store", "doc")
ASIS_BADGES = ("PAIN", "DELAY")
TOBE_BADGES = ("NEW", "TBD")


def load_map(folder, version=None):
    """(version, path or None, the map or None when it is not a JSON object)."""
    if version:
        path = Path(folder) / "maps" / f"map v{version}.json"
        if not path.is_file():
            return version, None, None
    else:
        version, path = latest(Path(folder) / "maps", "map v{v}.json")
        if path is None:
            return 0, None, None
    data = read_json(path)
    return version, path, data if isinstance(data, dict) else None


def flows(m):
    for sec in m.get("sections") or []:
        for view in ("asis", "tobe"):
            if isinstance(sec.get(view), dict):
                yield sec, view, sec[view]


def validate(m, ledger_ids=None, scope=None, allowed_lanes=None):
    """(errors, warnings) for a map. Errors fail the map test; warnings are reported."""
    if not isinstance(m, dict):
        return ["the map is not a JSON object"], []
    errors, warnings = [], []
    if m.get("schema") != SCHEMA:
        errors.append(f"schema is {m.get('schema')!r}, not {SCHEMA!r}")
    lanes = [l for l in m.get("lanes") or [] if isinstance(l, dict)]
    lane_ids = [str(l["id"]) for l in lanes if l.get("id")]
    if not lane_ids:
        errors.append("no lanes")
    if len(set(lane_ids)) != len(lane_ids):
        errors.append("a lane id is used twice")
    if allowed_lanes:
        allowed = {a.lower() for a in allowed_lanes}
        errors += [f"lane '{l.get('label')}' is not one the rules file allows"
                   for l in lanes if str(l.get("label", "")).lower() not in allowed]
    if not m.get("sections"):
        errors.append("no sections")
    used_lanes = set()
    proposed = str(m.get("proposed_system") or "").upper()

    def need_claims(ids, where):
        ids = [str(i) for i in ids or []]
        if not ids:
            errors.append(f"{where} cites no claim")
        elif ledger_ids is not None:
            missing = [i for i in ids if i not in ledger_ids]
            if missing:
                errors.append(f"{where} cites {', '.join(missing)}, not in the claim ledger")

    for sec in m.get("sections") or []:
        num = str(sec.get("num") or "?")
        if not sec.get("title"):
            errors.append(f"section {num} has no title")
        if not isinstance(sec.get("asis"), dict):
            errors.append(f"section {num} has no as-is flow")
        if scope == "as-is-and-to-be":
            if not isinstance(sec.get("tobe"), dict):
                errors.append(f"section {num} has no to-be flow (scope is as-is and to-be)")
            delta = sec.get("delta") or {}
            if not delta.get("today") or not delta.get("proposed"):
                errors.append(f"section {num} has no delta strip (today and proposed)")
            else:
                need_claims(delta.get("claims"), f"section {num} delta strip")
        asis_ids = {str(n.get("id")) for n in (sec.get("asis") or {}).get("nodes") or []}
        for r in sec.get("removed") or []:
            if str(r.get("node")) not in asis_ids:
                errors.append(f"section {num} removes {r.get('node')}, not an as-is step")
            need_claims(r.get("answers"), f"section {num} removal of {r.get('node')}")
            if not str(r.get("why") or "").strip():
                errors.append(f"section {num} removal of {r.get('node')} says no why")
    for sec, view, flow in flows(m):
        num = str(sec.get("num") or "?")
        label = "as-is" if view == "asis" else "to-be"
        nodes = flow.get("nodes") or []
        if not nodes:
            errors.append(f"section {num} {label} has no steps")
            continue
        ids = [str(n.get("id")) for n in nodes]
        if len(set(ids)) != len(ids):
            errors.append(f"section {num} {label} uses a step id twice")
        asis_ids = {str(n.get("id")) for n in (sec.get("asis") or {}).get("nodes") or []}
        for n in nodes:
            nid = f"section {num} {label} step {n.get('id')} '{n.get('title', '')}'"
            lane = str(n.get("lane"))
            if lane not in lane_ids:
                errors.append(f"{nid} is in lane {lane}, which is not declared")
            used_lanes.add(lane)
            if n.get("kind", "step") not in KINDS:
                errors.append(f"{nid} has kind {n.get('kind')!r}")
            if not isinstance(n.get("col"), int) or n["col"] < 0:
                errors.append(f"{nid} has no column")
            if not str(n.get("title") or "").strip():
                errors.append(f"{nid} has no title")
            badge = n.get("badge")
            if view == "asis":
                if badge in TOBE_BADGES:
                    errors.append(f"{nid} carries {badge}: a to-be marker on the as-is map")
                elif badge not in (None, "", *ASIS_BADGES):
                    errors.append(f"{nid} has badge {badge!r}")
                if proposed and proposed in [str(s).upper() for s in n.get("systems") or []]:
                    errors.append(f"{nid} shows the proposed system {proposed} on the as-is map")
                need_claims(n.get("claims"), nid)
                continue
            if badge not in (None, "", *TOBE_BADGES):
                errors.append(f"{nid} has badge {badge!r} (to-be takes NEW or TBD)")
            if n.get("same_as"):
                if str(n["same_as"]) not in asis_ids:
                    errors.append(f"{nid} is the same as {n['same_as']}, not an as-is step of the section")
                if badge in TOBE_BADGES:
                    errors.append(f"{nid} is marked {badge} but is the same as an as-is step")
            else:
                need_claims(n.get("answers"), f"{nid} (the pain it answers)")
                if not str(n.get("why") or "").strip():
                    errors.append(f"{nid} is a change and says no why")
                errors += [f"{nid} replaces {r}, not an as-is step of the section"
                           for r in n.get("replaces") or [] if str(r) not in asis_ids]
        for e in flow.get("edges") or []:
            where = f"section {num} {label} edge {e.get('from')}->{e.get('to')}"
            if str(e.get("from")) not in ids or str(e.get("to")) not in ids:
                errors.append(f"{where} names an unknown step")
            if e.get("style", "solid") not in ("solid", "dash"):
                errors.append(f"{where} has style {e.get('style')!r}")
        notes = {n.get("note") for n in nodes if n.get("note")}
        for c in flow.get("callouts") or []:
            where = f"section {num} {label} callout {c.get('n')}"
            if c.get("type", "pain") not in ("pain", "new", "tbd", "info"):
                errors.append(f"{where} has type {c.get('type')!r}")
            if view == "asis" and c.get("type") in ("new", "tbd"):
                errors.append(f"{where} is a to-be callout on the as-is map")
            if view == "asis" or c.get("type") in ("pain", "info"):
                need_claims(c.get("claims"), where)
            if c.get("n") not in notes:
                warnings.append(f"{where} has no numbered step pointing at it")
    errors += [f"lane {lane} is orphaned: no step in any flow" for lane in lane_ids if lane not in used_lanes]
    return errors, warnings


def as_is_leaks(html):
    """To-be content found in an as-is-only page."""
    return [m for m in ("TO-BE", "PROPOSED", ">NEW<", ">TBD<", "setAll(") if m in html]


# --------------------------------------------------------------------------- the claim ledger


def read_ledger(work):
    import csv

    path = Path(work) / LEDGER_FILE
    if not path.is_file():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def cross_reference(a, b):
    """The two fact-check halves' verdicts per assertion key: CONTRADICTED if either half
    contradicts, VERIFIED if either verifies, else NOT IN SOURCES."""
    out = {}
    for rev in (a, b):
        for v in (rev or {}).get("verdicts") or []:
            cur = out.setdefault(v["key"], {"verdict": "NOT IN SOURCES", "evidence": []})
            if v["verdict"] != "NOT IN SOURCES":
                cur["evidence"].append(v)
            if v["verdict"] == "CONTRADICTED":
                cur["verdict"] = "CONTRADICTED"
            elif v["verdict"] == "VERIFIED" and cur["verdict"] != "CONTRADICTED":
                cur["verdict"] = "VERIFIED"
    return out
