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

Scanned 152 of 152 skills on 2026-10-09 with SkillSpector v2.12.0, static analysis (`--no-llm`): 318 findings.

| Severity | Skills |
|---|---:|
| CRITICAL | 10 |
| HIGH | 9 |
| MEDIUM | 27 |
| LOW | 106 |

The 19 skills rated CRITICAL or HIGH:

| Skill | Department | Score | Severity | Findings |
|---|---|---:|---|---:|
| `client-update-workstream` | reporting | 100 | CRITICAL | 15 |
| `erp-ledger-pull` | accounting | 100 | CRITICAL | 12 |
| `goal-alignment-workstream` | strategy | 100 | CRITICAL | 7 |
| `meeting-portal-notes` | productivity | 100 | CRITICAL | 5 |
| `recording-harvest` | decision-playbooks | 100 | CRITICAL | 6 |
| `report-weekly` | reporting | 100 | CRITICAL | 17 |
| `skills-extract` | toolbox-maintenance | 100 | CRITICAL | 11 |
| `weekly-review-workstream` | productivity | 100 | CRITICAL | 8 |
| `software-factory-workstream` | software | 92 | CRITICAL | 13 |
| `chief-of-staff-cycle` | chief-of-staff | 89 | CRITICAL | 14 |
| `software-portfolio-review` | software | 78 | HIGH | 10 |
| `process-flow-workstream` | process-engineering | 76 | HIGH | 11 |
| `board-package-workstream` | reporting | 73 | HIGH | 6 |
| `writing-seminar-builder` | learning | 71 | HIGH | 7 |
| `meeting-scheduled-worker` | productivity | 59 | HIGH | 6 |
| `month-end-accrual-drafts` | accounting | 58 | HIGH | 12 |
| `toolbox-audit-workstream` | toolbox-maintenance | 58 | HIGH | 11 |
| `comms-confirm` | productivity | 56 | HIGH | 6 |
| `comms-reply-to-email` | productivity | 55 | HIGH | 6 |

## What the high ratings mean

SkillSpector rates what a skill *can* do, not what it was meant to do, so a skill that legitimately talks to an API looks the same as one built to steal a token. Here is what drives the CRITICAL and HIGH ratings above, checked against the code:

- **Secrets sent over the network (TT3, CRITICAL).** The skills that call an authenticated API read a credential and send it with the request: a token from an environment variable for Sage Intacct (`erp-ledger-pull`) and the Insights Portal MCP server (the Portal-backed skills), and a browser cookies file you export for private Loom videos (`recording-harvest`). That is how authenticated calls work, and it is also exactly what an exfiltrating skill looks like. Here, the destination is fixed (Intacct's and Loom's APIs) or is the server named in your own MCP config, and these scripts refuse HTTP redirects, so a server cannot bounce the credential elsewhere. Review these before you install them, and only give them the tokens they name.
- **Capabilities not declared (LP1 and LP3).** Many scripts read environment variables, run other scripts, read and write files or call the network, and the `SKILL.md` does not list them in `allowed-tools`. Declaring each skill's tool scope is on the [roadmap](../roadmap.md).
- **Running other programs (AST4, TT2).** Scripts run the skill's own sibling scripts and named tools such as `git`, `gh` and `pdftotext`, and the tests run the scripts under test, with `subprocess.run` and an argument list. No script uses `shell=True`.
- **Environment copied (E2).** Test helpers copy `os.environ` to run a script with fake settings, and the toolbox audit copies it to run Python with one extra variable. None of them send it anywhere.
- **Instructions that sound like jailbreaks (AR2, EA2, AE1).** Phrases such as "without asking" (for writes the owner pre-approved, such as a draft), "do not judge" (in an intake step that records items and leaves ranking to a later reviewer), and reference files SkillSpector only partly read.
- **Mentions of other agents' folders (AS1, AS3).** `skills-extract` reads past Claude Code and Codex sessions on purpose, to suggest new skills, and skills name the shared `orchestration-workstream` skill by path.

Treat this as a review checklist, not a clean bill of health. Every finding is in the reports the scan writes, with its file and line.

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
