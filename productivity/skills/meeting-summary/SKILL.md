---
name: meeting-summary
description: Summarizes a meeting's materials (transcript, chat log, emails, notes) into a one-to-two page summary in the house style, with the anonymization mode chosen, renders it as a PDF and saves it as a Portal note. Use when a meeting or session needs a polished written summary to share, for "write up the session". Not for filing tasks and follow-ups (meeting-followup) or several interviews (interview-synthesis).
model: claude-haiku-4-5-20251001
context: fork
allowed-tools: mcp__insights-portal__*, Read, Write, Bash, AskUserQuestion
---

# Meeting Summary Skill

Generate professional meeting summaries from raw materials (transcripts, chat logs, emails, presentation content) and convert them to polished PDFs.

---

## Before You Start

1. **Load the style guide**: Load the meeting-summary-style-guide skill. It contains the house formatting preferences, anonymization rules, section catalog, and quality checklist. Follow it exactly.
2. **Gather all input materials**: Read everything provided: `.vtt` transcripts, `.txt` chat logs, `.md` files, email text. For `.pptx` files, ask the user to paste or describe the content.

---

## Input Format Handling

| Format | How to Process |
|--------|---------------|
| `.vtt` (WebVTT) | Transcript with timestamps and speaker names. Extract speaker changes, topics discussed, key statements. Ignore timestamps in output. |
| `.txt` (chat log) | Zoom/Teams chat. Extract shared links, key comments, questions asked. |
| `.txt` (emails) | Pre/post meeting emails. Extract agenda items, context, follow-up commitments. |
| `.md` (notes) | Existing notes or outlines. Incorporate relevant content. |
| `.pptx` (slides) | Cannot read directly. Ask user to describe slide content or paste text. |
| Pasted text | Treat as raw notes. Parse for structure, entities, action items. |

---

## Content Analysis Process

### Step 1: Read Everything
Read all provided materials completely before writing anything.

### Step 2: Identify Major Sections (First Pass)

Scan through the transcript and other materials to identify the **major topics and sections** covered. For each section, note:
- A descriptive title (e.g., "Live Demo - Insights Portal", not just "Demo")
- Approximate timestamps if available from a `.vtt` transcript
- 1-sentence summary of what was covered

**Present the section list to the user for confirmation.** Output it conversationally, like:

```
Here are the major sections I found in the transcript:

0:00:00  Introduction & Agenda
         Opening remarks, agenda overview, attendee introductions
0:05:32  Project Status Update
         Q1 progress review, budget discussion
0:19:46  Live Demo - New Dashboard
         Walkthrough of the redesigned analytics dashboard
...

Does this look right? Any sections to add, remove, rename, or merge?
```

**Why this matters:** Long transcripts (60+ minutes) cover many topics, and the model may misjudge which topics deserve emphasis. Getting user confirmation ensures the summary focuses on the right things.

**If the user modifies the list**, use their updated sections as the structural backbone of the summary. If they confirm as-is, proceed with your identified sections.

**Short meetings or simple materials** (under 30 minutes, or just chat logs/emails with no transcript) can skip this confirmation step and go directly to writing.

### Step 3: Extract Key Content

For each confirmed section, extract:
- **Topics discussed**: what subjects came up and how deeply
- **Decisions made**: any conclusions the group reached
- **Tools/resources mentioned**: specific products, platforms, links
- **Action items**: who committed to doing what
- **Notable insights**: interesting points, frameworks, philosophies
- **Poll/survey data**: if any polls were conducted
- **Demo content**: if someone demonstrated something
- **Links shared**: URLs from chat or presentations

### Step 4: Choose Summary Sections
Map the confirmed topic sections to 4-6 sections from the style guide's Section Catalog. Multiple transcript sections may merge into a single summary section. Don't force sections that don't have substance. Adapt to the content.

### Step 5: Apply Anonymization

Apply the anonymization mode chosen during context confirmation (see style guide for full rules):

**Mode A (Full Anonymize):** Replace ALL participant names with varied attributions:
- "one participant noted...", "a member suggested...", "the group discussed...", "several attendees agreed..."

**Mode B (Anonymize Except Me):** Keep only the named user's identity. Replace all other names with varied attributions as in Mode A.

**Mode C (No Anonymization):** Use names/initials freely. Still paraphrase for flow.

For Modes A and B, scan the final output to verify no unintended names leaked through.

---

## Writing the Summary

### Structure
Follow the style guide's Document Structure section exactly:
1. Title line with group/meeting name and topic
2. Metadata line (Date, Duration)
3. Sections flow directly; NO horizontal rules (`---`) between sections

### Style Rules
- **Paragraph-driven format** with bold lead phrases, NOT bullet-point lists
- Each content paragraph starts with a **bolded key phrase** followed by a colon
- Tables only for genuinely tabular data (polls, structured comparisons)
- NO horizontal rules between sections; headers alone separate them
- Executive Summary: exactly 2-4 sentences
- Resources go at the end as a **bold label + bullet list** with current, actionable URLs (not inline pipe-separated text)
- IMPORTANT: A blank line is required between `**Resources:**` and the first `- ` bullet, otherwise markdown renders it as one paragraph

### Length Target
- Main content: 1-2 pages in PDF (letter size, 0.5" margins, 9.5pt body)
- If content is too long, merge related points into fewer paragraphs and trim low-value details
- If an appendix is needed, mark it with `## Appendix: [Topic]`; the PDF converter will force a page break before it

---

## Generating the PDF

### Step 1: Save the Markdown
Write the summary to the session folder as:
```
Meeting Summary - [Short Title].md
```

### Step 2: Run the Converter
```bash
meeting-summary-to-pdf "path/to/Meeting Summary - Title.md"
```
This produces a PDF in the same directory with the same base name. The command is not yet ported to this toolbox; without it, render the Markdown to a letter-size PDF with 0.5" margins and 9.5pt body text by any converter you have, keeping tables sized to content and a page break before `## Appendix:`.

### Step 3: Verify the PDF
Read the generated PDF and check:
1. **Page count**: main content fits 1-2 pages
2. **Tables**: sized to content, not stretched full width
3. **Page breaks**: appendix (if any) starts on its own page
4. **No orphan text**: no stray lines bleeding onto an extra page
5. **Headers**: not orphaned at bottom of a page
6. **Anonymization**: verify the chosen mode was applied correctly; scan for leaked names if Mode A or B
7. **Resources list**: renders as a proper bullet list, not a run-on paragraph

### Step 4: Iterate if Needed
If the PDF has issues:
- Content too long: merge paragraphs, trim low-value content, tighten wording
- Tables stretched: the CSS handles this; if still an issue, simplify table structure
- Orphan text: tighten a paragraph or remove a low-value sentence
- Page break wrong: ensure `## Appendix:` heading is present

Regenerate the PDF after each adjustment.

---

## Saving to the Portal

After the PDF is verified, create a meeting note in the Insights Portal. Before this or any other create/update call, load the portal-write-safety skill and follow it: propose by default, resolve entities by UUID never by name, `CANCELLED` with evidence never `DONE`, `sync_health` first.

```
create_note(
    title="[Group Name] - [Topic] Summary",
    content=[the markdown content],
    note_type="episodic"
)
```

Associate with relevant contacts or companies if applicable.

---

## Offering Follow-Up

After completing the summary, offer to:
1. Create tasks from any action items identified
2. Create draft emails if the summary should be sent to attendees
3. Associate the note with specific contacts or domains in the Portal
