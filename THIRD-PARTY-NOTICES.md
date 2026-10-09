# Third-party notices

Parts of this toolbox are adapted from other people's published work. Each piece below names its upstream, the upstream license, and where the copyright and permission notice travels with the copy.

## mattpocock/skills

Upstream: https://github.com/mattpocock/skills. License: MIT, "Copyright (c) 2026 Matt Pocock". The full license text is in a `LICENSE` file inside each adapted skill's folder, and the last line of each adapted `SKILL.md` names its upstream path.

| Piece in this repository | Upstream path | What was taken | Notice |
|---|---|---|---|
| `software/skills/software-diagnose-bugs` | `skills/engineering/diagnosing-bugs` (SKILL.md and `scripts/hitl-loop.template.sh`) | The whole skill, renamed, with the description rewritten | `software/skills/software-diagnose-bugs/LICENSE` |
| `software/skills/software-grill-with-docs` | `skills/engineering/grill-with-docs` (SKILL.md, CONTEXT-FORMAT.md, ADR-FORMAT.md; the two format files now live upstream in `skills/engineering/domain-modeling`) | The whole skill, renamed, with the description rewritten and em dashes replaced | `software/skills/software-grill-with-docs/LICENSE` |
| `software/skills/software-improve-architecture` | `skills/engineering/improve-codebase-architecture` (SKILL.md, LANGUAGE.md, DEEPENING.md, INTERFACE-DESIGN.md; upstream has since moved DEEPENING.md and INTERFACE-DESIGN.md to `skills/engineering/codebase-design`) | The whole skill, renamed, with the description rewritten, references to its sibling made by name, and em dashes replaced | `software/skills/software-improve-architecture/LICENSE` |
| `software/skills/software-deep-spec` | `skills/engineering/to-spec` | Three parts: the seam sketch in Phase 2, the ban on file paths and code snippets, and the shape of dimension 8 | `software/skills/software-deep-spec/LICENSE` |
