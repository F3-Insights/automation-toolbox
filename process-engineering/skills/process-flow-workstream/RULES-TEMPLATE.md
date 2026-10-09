# Process flow rules: <engagement>

Copy this file to the engagement's rules folder (the Context's `rules` Source, else its working folder) as `PROCESS-FLOW-RULES.md` and fill it in. The tools read the `- Key: value` lines; the prose is for people. It overrides the agents' and skills' instructions.

## Defaults

- Default process: <slug, e.g. quote-to-order>
- Scope: as-is-and-to-be
- Audience: <who reads the map, e.g. the client's leadership team, for validation>
- Client: <the client's name as it appears on the map>
- Prepared by: <the firm's name for the footer, or leave the line out>
- Lanes: <the functional lanes the map may use, comma-separated; leave out to let the mapper choose>
- Transcript files: <patterns of first-person sources in the transcripts folder: *transcript*, *.srt, *survey*>
- Exclude: <patterns never read: *invoice*, *.zip>
- Reference model: <order-to-cash | procure-to-pay | proposal-to-contract | record-to-report | a file beside this one>
- Red team bar: B-
- Screenshot: yes

## The four stakeholder decisions

The method asks these of the stakeholder; record the answers here. Until one is answered the orchestrator asks it through comms-confirm and maps with the default in brackets.

- Sections: <the process sections, matched to the proposal's capability areas> [the mapper proposes]
- Swim lanes: <functional roles, external actors as lanes> [the Lanes line above]
- Audience: <internal design input, client validation, or presentation> [client validation]
- Pain policy: <neutral, subtle markers, or full overlay> [subtle markers with the footer]

## What may be shown

- Names: roles only (never a person's name on the map or in the narrative)
- To-be may show: <proposed capabilities agreed with the owner; anything else is TBD>
- Numbers: only with a first-person quote; an estimate is labelled as one

## Process: <slug>

Per-process overrides go in a section like this one, with the same `- Key: value` lines.

- Reference model: order-to-cash
