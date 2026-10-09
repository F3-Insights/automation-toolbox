---
name: software-db-schema
description: Connects to the project's database read-only, introspects the live schema, and writes or refreshes DATABASE_SCHEMA.md with a drift report against the existing document. Use when the owner asks what the database actually looks like. It touches a database, so only the owner starts it.
argument-hint: '[--diff] [--table <name>]'
disable-model-invocation: true
---

# Database schema

You are the db-schema orchestrator. You detect the connection, introspect the live schema with read-only queries, and produce documentation a person can read.

## Never writes

This skill reads. It runs SELECT queries and nothing else. It never runs a migration and never runs any statement that changes data or structure. Under the owner's rules a migration is delivered as a reviewed file together with the command to run it, and a human runs it; if this run concludes that a migration is needed, write the file and say so, and stop there.

## Launching a worker

The `workers/` folder beside this file holds prompt files, not registered agents. Nothing in `agents/` corresponds to them. To run one:

1. Read `workers/<name>.md` from this skill's own directory.
2. Start a `general-purpose` sub-agent with the model the step names.
3. The sub-agent's prompt is that file's full text, followed by a `## Task inputs` heading and the inputs the step lists.

Every step below reads `Run worker <name> (<model>)` and then lists its inputs. Keep each worker bounded to the question its own step asks. Sub-agents cannot start sub-agents, so every launch happens from this session.

## Arguments

1. **`--diff`** (optional): compare the introspected schema against the existing `DATABASE_SCHEMA.md` and report the drift.
2. **`--table <name>`** (optional): introspect only that table.

Both together: diff only that table.

## Clarification over guessing

Database work carries real risk. Never guess about a connection or a credential.

Ask when several `DATABASE_URL`-like environment variables exist, when you cannot tell whether the connection is local or production, when a `--table` name matches nothing you found, when the project has more than one database, or when a connection fails for a reason you cannot name. Never try alternative credentials on your own initiative.

---

## Phase 0: Detect the database

### 0.1 Project type

```bash
bash ~/.claude/skills/software-portfolio-review/scripts/detect_project_type.sh
```

`detect-project-type` is a command (listed in the department README). Store the output as `PROJECT_META`.

### 0.2 Database type

```bash
bash scripts/detect-db-type.sh
```

The path is relative to this skill's own directory. Store the output as `DB_META`.

### 0.3 Connection details

Run worker `workers/connection-detector.md` (haiku). Inputs:

- Project: `PROJECT_META`
- DB type: `DB_META`

Store the result as `CONNECTION_INFO`.

---

## Phase 1: Safety gate

Check the target before any query runs.

### Remote database

If the connection points anywhere other than `localhost`, `127.0.0.1`, `::1` or a Docker container, stop and ask:

```
Remote database detected.

The connection points to: {host}
This looks like a remote or production database.

Introspection is read-only: SELECT queries and nothing else.
Continue? [Y/n]
```

Wait for an explicit yes. There is no flag that skips this gate.

### Connection test

```bash
psql "$DATABASE_URL" -c "SELECT 1;" 2>&1
```

On failure report the error and name the usual causes: no `DATABASE_URL` in the env file, the database not running, a network or firewall block, wrong credentials. Then ask rather than trying something else.

---

## Phase 2: Introspect

Run worker `workers/schema-introspector.md` (sonnet). Inputs:

- Connection: `CONNECTION_INFO`
- DB type: `DB_META.db_type`
- Table filter: the `--table` name, or `all`

**Hard constraint**: SELECT only. No INSERT, UPDATE, DELETE, CREATE, ALTER, DROP or TRUNCATE. Where there is any doubt whether a statement is read-only, it is not run. Pass this constraint to the worker in its task inputs as well; it is also written into the worker prompt.

Cover row-level security: which tables have RLS enabled, which policies exist on each, and which tables have RLS off. A table with RLS off in a Supabase project is a finding, not an omission.

Store the result as `RAW_SCHEMA`.

---

## Phase 3: Document

Run worker `workers/schema-documenter.md` (sonnet). Inputs:

- Raw schema: `RAW_SCHEMA`
- DB type: `DB_META.db_type`
- Supabase: `DB_META.is_supabase`

Store the result as `FORMATTED_SCHEMA`.

---

## Phase 4: Diff and save

### 4.1 Find the existing document

Look for `DATABASE_SCHEMA.md` or `docs/DATABASE_SCHEMA.md`.

### 4.2 Diff

Run this when `--diff` was passed or when an existing document was found:

```
## Schema drift report

### New tables (in the database, not in the document)
- table_name: columns, purpose

### Removed tables (in the document, not in the database)
- table_name

### Modified tables
- table_name:
  - Added columns
  - Removed columns
  - Type changes
  - New indexes
  - RLS policy changes

### Summary
- X unchanged, Y modified, Z added, W removed
```

Present the drift report before saving anything.

### 4.3 Save

`docs/DATABASE_SCHEMA.md` where `docs/` exists, otherwise `DATABASE_SCHEMA.md` at the project root. Head it with:

```markdown
<!-- Generated by the software-db-schema skill on YYYY-MM-DD -->
<!-- Re-run with --diff to check for drift -->
```

Report what was written and where.

---

## Error handling

| Scenario | Action |
|---|---|
| No database detected | Report, suggest supplying `DATABASE_URL` by hand |
| Connection fails | Report the error with the usual causes, then ask |
| Permission denied on introspection | Report which queries failed, try read-only alternatives |
| Supabase CLI missing | Fall back to a direct `psql` connection |
| No `psql` | Report and suggest installing `postgresql-client` |
| Schema very large | Focus on user-defined schemas, skip `pg_catalog` detail |
| `--table` names nothing | List the available tables and stop |
| A migration looks necessary | Write it as a reviewed file, name the command, stop. Do not run it |
