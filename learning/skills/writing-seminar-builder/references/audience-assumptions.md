# Audience Assumptions

The default audience profile for this seminar series, plus the menu of platform and skill assumptions to draw from when drafting Slide 2.

---

## Default audience profile

Use this unless the user overrides in Step 1.

- **Roles:** Mid-level managers through C-suite at small-to-midmarket businesses
- **Business literacy:** High: they read P&Ls, they've run projects, they've managed people
- **Technical depth:** Low to moderate; cannot read code, may not know what an API is
- **AI exposure:** Mixed. Some use ChatGPT or Copilot casually, few have enterprise deployments, very few have touched APIs or built agents
- **Decision posture:** They are deciders or strong influencers on AI spend, not implementers
- **Disposition:** Skeptical of hype. Many have seen a failed pilot or two. Time-poor and allergic to fluff.
- **Attention budget:** 30–45 minutes, with moderate engagement. They will skim if the first three slides don't earn their time.

---

## Slide 2 assumption menu

Slide 2 names what the audience needs to already have for the seminar's content to be actionable. Pick from these categories and be specific. Vagueness here makes the rest of the deck land softer.

### Platform stack

Name the platform(s) at a specific tier:

- **Claude.ai**: Free, Pro, Max, Team, or Enterprise (each has different feature availability: Projects, Connectors, Skills, etc.)
- **ChatGPT**: Free, Plus, Team, Enterprise
- **Microsoft Copilot**: Copilot for Microsoft 365, Copilot Studio, or Copilot in specific apps
- **Google Gemini**: Free, AI Pro, AI Ultra, Workspace integration
- **API access**: Direct API use via a harness or custom app (rare for this audience; flag if assumed)
- **No-code/low-code harness**: n8n, Make, Zapier with AI nodes, custom GPTs, Claude Projects/Skills, etc.

When in doubt, the safest default for this audience is **Claude Team or ChatGPT Team**: enough capability to do real work, low enough barrier that companies of this audience's size have actually deployed it (check this default against the `audience` setting; a large enterprise audience may sit on an enterprise tier, a very small one on individual plans).

### Data and system access

What the audience needs to be able to reach:

- **Read access to a structured data source**: CRM, ERP, finance system, ticketing system, file shares
- **Exportable data**: at minimum, the ability to pull CSVs or reports out of their systems
- **A document repository**: SharePoint, Google Drive, Dropbox, etc., where institutional knowledge lives
- **Email/calendar integration**: for workflows that touch communications
- **A connection to a specific category of system**: name it (e.g., "your finance ERP," "your project management tool")

### Organizational readiness

What the business needs to have in place:

- **Executive sponsorship**: at least one decision-maker willing to back a pilot
- **A named owner**: someone internal who can carry the work, not just a steering committee
- **A defined use case or pain point**: not "let's explore AI"
- **Tolerance for iteration**: willingness to refine, not expecting perfection on day one
- **Basic data hygiene**: the underlying data isn't so chaotic that no tool could help

### Skill floor

What the person operating the workflow needs to be able to do:

- **Write a thoughtful email**: can express intent clearly in writing
- **Use a spreadsheet competently**: formulas, filtering, basic structure
- **Follow a documented workflow**: can be trained on a process and execute it
- **Comfortable with prompting**: has used AI chat tools beyond a few one-off questions *(stretch)*
- **Can build a GPT, Claude Project, or equivalent**: entry-level configuration *(stretch)*
- **Can use MCP, agents, or write code**: flag explicitly if assumed; rarely true for this audience

---

## How to draft Slide 2

Pick one item from each of the four categories above and write them as plain-language bullets. End the slide on the last assumption. Do not add a call to action here; the only selling slide is the closing offer.
