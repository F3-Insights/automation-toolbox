---
name: <skill-name>
description: <What the procedure does, in one or two sentences.> Use for <the request>. Not for <the nearest thing it does not do>; use <the skill or agent that does>.
---

# <Title>

<One paragraph: what this procedure produces and who uses it.>

## Inputs

- **<Input>** (required): <what it is, in plain words; never a hard-coded path>.
- **<Input>** (optional): <what it is>. Default: <the default>.

## Steps

<A job's skill carries its steps in the format Sentinel draws: `N. [kind] text`, the kind one of
`script`, `judgment`, `hand-off: <department>-worker` or `<department>-reviewer`, and `ask`; a
script step names its command in backticks. A branch is an indented line `→ condition:
step N`, `stop`, `ask` or `done`, optionally with `(max N)`.>

1. [script] <Run `<department>-<command> ARGS`. Say what its first line means.>
   → <nothing to do>: done
2. [judgment] <Do this. Say what to check before moving on.>
3. [hand-off: <department>-reviewer] <Check the result (section <Check name>), with the sources only.>
   → FAIL: step 2 (max 1)
4. [judgment] <Write the result and report.>
   → written: done

## Done when

<What must be true, and the evidence to show.>

## Output

<The exact shape of the result.>
