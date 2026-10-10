# Scanned with NVIDIA SkillSpector

Every skill in this toolbox is scanned with [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector), and this page publishes what it found: the scores, the skills it rated highest risk, and what each kind of finding means here. Nothing is hidden or suppressed.

## What SkillSpector is

SkillSpector is NVIDIA's open-source (Apache 2.0) security scanner for AI agent skills: the `SKILL.md` folders that Claude Code, Codex, Gemini CLI and other agents load and run. It is part of the [NVIDIA Verified Skills pipeline](https://docs.nvidia.com/skills/), which scans, evaluates and signs skills before NVIDIA publishes them.

It checks a skill's instructions and code against 71 vulnerability patterns in 17 categories, including prompt injection, data exfiltration, privilege escalation, supply-chain risk, excessive agency, dangerous code (by parsing the Python), taint tracking from secrets to the network, and least-privilege gaps. Each skill gets a risk score from 0 to 100 and a severity: LOW, MEDIUM, HIGH or CRITICAL. An optional second stage has a language model review the skill's intent.

- Project: https://github.com/NVIDIA/SkillSpector
- Guide to scanning skills before you install them: https://docs.nvidia.com/skills/scanning-agent-skills

## Why it matters

A skill is code and instructions an agent follows with your permissions: it can read your files, run commands and call the network. Skills are shared like any other software, but they are rarely reviewed like it. SkillSpector's own research found vulnerabilities in 26.1% of the 31,132 public skills it analysed, and signs of malicious intent in 5.2%.

These skills handle financial records, mail, calendars and client work, so the bar is higher. Scanning every skill, publishing the results and explaining each high-risk rating lets you decide what to install with the evidence in front of you, instead of on trust.

## Results

Scanned 152 of 152 skills on 2026-10-10 with SkillSpector v2.12.0, static analysis (`--no-llm`): 386 findings. These are the numbers the [workflow](../../.github/workflows/skillspector.yml) produces with the pinned release, so you get the same result when you rerun it.

| Severity | Skills |
|---|---:|
| CRITICAL | 7 |
| HIGH | 12 |
| MEDIUM | 32 |
| LOW | 101 |

The 19 skills rated CRITICAL or HIGH:

| Skill | Department | Score | Severity | Findings |
|---|---|---:|---|---:|
| `client-update-workstream` | reporting | 100 | CRITICAL | 16 |
| `report-weekly` | reporting | 100 | CRITICAL | 27 |
| `skills-extract` | toolbox-maintenance | 100 | CRITICAL | 15 |
| `software-factory-workstream` | software | 97 | CRITICAL | 16 |
| `chief-of-staff-cycle` | chief-of-staff | 95 | CRITICAL | 15 |
| `process-flow-workstream` | process-engineering | 91 | CRITICAL | 13 |
| `orchestrator-scaffold` | software | 89 | CRITICAL | 12 |
| `software-portfolio-review` | software | 78 | HIGH | 10 |
| `board-package-workstream` | reporting | 77 | HIGH | 7 |
| `month-end-accrual-drafts` | accounting | 75 | HIGH | 14 |
| `writing-seminar-builder` | learning | 71 | HIGH | 7 |
| `erp-ledger-pull` | accounting | 66 | HIGH | 11 |
| `comms-confirm` | productivity | 65 | HIGH | 8 |
| `comms-reply-to-email` | productivity | 64 | HIGH | 8 |
| `meeting-scheduled-worker` | productivity | 63 | HIGH | 7 |
| `toolbox-audit-workstream` | toolbox-maintenance | 58 | HIGH | 11 |
| `report-time-study` | productivity | 56 | HIGH | 8 |
| `recording-harvest` | decision-playbooks | 51 | HIGH | 4 |
| `weekly-review-workstream` | productivity | 51 | HIGH | 8 |

## What the high ratings mean

No single finding in this scan is rated CRITICAL. A skill reaches CRITICAL because many HIGH and MEDIUM findings add up, and the score stops at 100. SkillSpector rates what a skill *can* do, not what it was meant to do, so a skill that legitimately calls an API or writes a draft looks much like one built to misuse that ability. Here is what drives the ratings above, checked against the code:

- **Capabilities not declared (LP1, HIGH, 31 in these skills; LP3).** Scripts read environment variables, run other scripts, read and write files or call the network, and the `SKILL.md` does not list those capabilities in `allowed-tools`. The skills that call an authenticated API read a credential and send it with the request: a token from an environment variable for Sage Intacct (`erp-ledger-pull`) and the Insights Portal MCP server (the Portal-backed skills), and a browser cookies file you export for private Loom videos (`recording-harvest`). The destination is fixed (Intacct's and Loom's APIs) or is the server named in your own MCP config, and these scripts refuse HTTP redirects, so a server cannot bounce the credential elsewhere. Declaring each skill's tool scope is on the [roadmap](../roadmap.md).
- **Files only partly analysed (AE1, HIGH).** A skill points to a reference file or script SkillSpector read only in part, so it cannot vouch for the rest. It flags this as possible evasion; here they are long reference files such as `report-weekly`'s `gates.md`.
- **Environment copied (E2, HIGH).** Test helpers copy `os.environ` to run a script with fake settings, and the toolbox audit copies it to run Python with one extra variable. None of them send it anywhere.
- **Hidden-looking comments (P2, HIGH).** HTML comments in the seminar deck kit (`writing-seminar-builder`) that label icons and slide parts.
- **Instructions that sound like jailbreaks (AR2, EA2, RA2).** Phrases such as "without asking" (for writes the owner pre-approved, such as a draft), "do not judge" (in an intake step that records items and leaves ranking to a later reviewer), and the many places a skill tells an agent to write something: a draft, a reply it never sends, or a file in its Run folder.
- **Other agents' folders and git (AS1, AS3, TM1).** `skills-extract` reads past Claude Code and Codex sessions on purpose, to suggest new skills; skills name the shared `orchestration-workstream` skill by path; and the software factory's rules mention `--force` only to forbid it except in one named case.
- **Running other programs (AST4, TT2, MEDIUM).** Scripts run the skill's own sibling scripts and named tools such as `git` and `pdftotext`, and the tests run the scripts under test, with `subprocess.run` and an argument list. No script uses `shell=True`.

Treat this as a review checklist, not a clean bill of health. Every finding is in the reports the scan writes, with its file and line. Newer SkillSpector code than the v2.12.0 release scores some skills differently (for example, it rates sending a credential over the network as CRITICAL on its own), so the workflow pins the release to keep results comparable from scan to scan.

## Run it yourself

```bash
uv tool install git+https://github.com/NVIDIA/skillspector.git@v2.12.0
python3 scripts/skillspector_scan.py --out skillspector-report        # static analysis
python3 scripts/skillspector_scan.py --out skillspector-report --llm  # plus LLM review
```

Or scan one skill, from this repository or any other, before you install it:

```bash
skillspector scan path/to/skill --no-llm
```

The [SkillSpector workflow](../../.github/workflows/skillspector.yml) runs the same scan on every push and pull request and once a week, and attaches the full reports to the run.
