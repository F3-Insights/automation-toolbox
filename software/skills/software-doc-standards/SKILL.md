---
name: software-doc-standards
description: "Reference loaded by software-clean-docs and any repository documentation work, not for a user request: the target documentation structure and quality bar for a repository (what belongs in CLAUDE.md, what belongs in docs/, how README and archive files are shaped). Consult it before proposing or writing repository documentation."
user-invocable: false
---

# Documentation standards

Reference material. It defines the target documentation structure and the quality bar for any repository. The `software-clean-docs` skill audits and restructures against it.

## CLAUDE.md Standards

### Purpose
CLAUDE.md is a **lean context hub** for Claude Code. It should contain only what Claude needs to work effectively in this repo, with links to detailed docs elsewhere.

### Target Size
- **Ideal**: 40-80 lines
- **Hard limit**: 100 lines
- If over 100 lines, it's trying to do too much

### Required Sections (in order)
1. **Build & Run**: How to install deps, build, and start the project (exact commands)
2. **Code Conventions**: Naming, formatting, import style, error handling patterns
3. **Architecture Overview**: 3-5 sentences max, link to docs/ARCHITECTURE.md for details
4. **Testing**: How to run tests, test file naming, what to test
5. **Known Gotchas**: Things that will trip Claude up (max 5 items)

### What Does NOT Belong in CLAUDE.md
- Detailed architecture explanations (→ docs/ARCHITECTURE.md)
- Deployment instructions (→ docs/DEPLOYMENT.md)
- API documentation (→ docs/API.md or auto-generated)
- One-off debug notes from specific sessions
- Static file/directory trees (Claude can run `ls` and `Glob`)
- Full dependency lists (Claude can read package.json)
- Version history or changelog content
- Copy of README.md content

## Standard docs/ Structure

```
docs/
├── ARCHITECTURE.md   : Conceptual architecture (WHY, not WHAT)
├── DEPLOYMENT.md     : Deployment process, env vars, infrastructure
├── CONVENTIONS.md    : Detailed coding conventions (if CLAUDE.md section isn't enough)
└── archive/          : Superseded documentation with date prefixes
    └── YYYY-MM-DD-filename.md
```

### Optional docs/ files (create only if needed):
- `API.md`: API documentation (if not auto-generated)
- `CONTRIBUTING.md`: Contribution guidelines (if open source)
- `DATABASE.md` or `DATABASE_SCHEMA.md`: Database documentation
- `TESTING.md`: Detailed testing guide (if testing is complex)

## ARCHITECTURE.md Standards

### MUST be conceptual (WHY)
- Why is the system structured this way?
- What are the key architectural decisions and their rationale?
- What are the boundaries between major components?
- What patterns are used and why?

### MUST NOT be a file tree (WHAT)
- Claude can run `ls`, `Glob`, and `find` anytime
- A static file tree is immediately stale after any file change
- File trees provide zero insight into architectural reasoning
- If someone needs to know what files exist, they should look at the actual files

### Good ARCHITECTURE.md example:
```
The system uses a feature-based architecture where each feature owns its
routes, components, and data access. This was chosen over layer-based
architecture because features change together and this minimizes cross-cutting
changes.

Auth is handled entirely by Supabase with RLS policies on every table.
Server-side operations use the service_role key only when RLS bypass is
explicitly needed (e.g., admin operations).
```

### Bad ARCHITECTURE.md example:
```
src/
├── components/
│   ├── Button.tsx
│   ├── Input.tsx
│   └── Modal.tsx
├── pages/
│   ├── Home.tsx
│   └── Login.tsx
```

## Anti-Patterns to Flag

| Anti-Pattern | Severity | Fix |
|-------------|----------|-----|
| CLAUDE.md > 100 lines | HIGH | Extract sections to docs/ |
| Static file tree in docs | MEDIUM | Replace with conceptual architecture |
| One-off debug notes in CLAUDE.md | HIGH | Delete: these are session-specific |
| README.md and CLAUDE.md duplicate content | MEDIUM | CLAUDE.md should link, not copy |
| Docs referencing nonexistent files | HIGH | Fix links or remove references |
| No CLAUDE.md at all | MEDIUM | Create a lean CLAUDE.md |
| CLAUDE.md is just a copy of README | HIGH | Rewrite for Claude's needs |
| Undated archived docs | LOW | Add YYYY-MM-DD prefix |
| docs/ with only one file | LOW | Consider if the file belongs elsewhere |

## README.md Standards

README.md is for **humans browsing the repo** (GitHub, etc.), not for Claude.

### Should contain:
- Project name and description
- Quick start / installation
- Basic usage examples
- Links to detailed documentation
- Contributing guidelines (or link to CONTRIBUTING.md)
- License

### Should NOT contain:
- Claude-specific instructions (that's CLAUDE.md)
- Detailed architecture (that's docs/ARCHITECTURE.md)
- Full API documentation (that's docs/API.md)
