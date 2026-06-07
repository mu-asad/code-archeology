---
name: orient
description: Produce a plain-English product orientation for an unfamiliar codebase — what it is, who it's for, what it does, and how mature it is. The entry-point skill for code-archeology analysis; run before map, quality, or story. Use when the user wants to understand a large or AI-generated codebase, or runs /orient. Writes findings to .archeology/snapshot.json.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash(ls *)
  - Bash(cat *)
  - Bash(find *)
  - Bash(wc *)
  - Bash(head *)
  - Bash(tail *)
  - Bash(sort *)
  - Bash(uniq *)
  - Bash(grep *)
  - Bash(git log *)
  - Bash(git diff *)
  - Bash(git show *)
  - Bash(git for-each-ref *)
  - Bash(git shortlog *)
  - Bash(git rev-list *)
  - Bash(git status *)
---

# orient

Produce a plain-English product orientation for an unfamiliar codebase. Answer: **what is this, who is it for, and what does it actually do?** — in human terms, not technical ones.

This skill is designed to work on large repos without choking on context. It reads breadth-first, never exhaustively, and writes all findings to a shared snapshot file before finishing.

---

## How to invoke

```
/orient [path-to-repo]
```

If no path is given, use the current working directory.

**Resolve the target root first.** If a path *is* given — or the repo lives somewhere other than your cwd (e.g. you launched from the code-archeology repo and passed the target via `--add-dir`) — treat that path as the target root and `cd` into it before running any steps, so every command (including bare `git`) operates on that repo. Every step below assumes commands run **inside the target repo**; don't analyze your current directory by accident.

---

## Step 0 — Initialize or resume snapshot

Before reading any code, check if `.archeology/snapshot.json` already exists in the target repo.

- **If it exists**: load it. Check `meta.skills_run` — if `orient` is already in there, report the existing findings and ask the user if they want to re-run. If resuming an interrupted run, continue from `coverage.queued`.
- **If it doesn't exist**: create `.archeology/` directory and initialize a fresh snapshot using the structure below. (The canonical contract is `schema/snapshot.schema.json` in the code-archeology repo — you do **not** need that file present in the target repo; the skeleton here is sufficient to initialize.) The very first write must already satisfy the required top-level keys, so initialize all of them — not just `meta`:

  ```json
  {
    "meta": { "repo": "<abs-path>", "created_at": "<now>", "updated_at": "<now>", "skills_run": [] },
    "coverage": { "analyzed": [], "queued": [], "skipped": [] },
    "stack": {},
    "product": {}
  }
  ```

  `stack` and `product` have no required sub-fields, so empty objects are valid until you fill them in later steps.

**Write the snapshot to disk after every major step below.** Do not wait until the end. If the agent runs out of context mid-run, the next invocation can resume from where it left off.

---

## Step 1 — Architecture skeleton (read first, always)

Read these files in order. They give you the shape of the application before you read a single line of business logic.

1. `docker-compose.yml`, `docker-compose.yaml`, `compose.yml` — services, ports, dependencies
2. Any `Dockerfile` or `Dockerfile.*` at the root
3. `package.json` (root-level) — name, description, scripts, key dependencies
4. `pyproject.toml`, `setup.py`, `requirements.txt` — Python package identity
5. `.env.example`, `.env.sample` — reveals expected configuration and integrations
6. Root-level `README.md` — stated intent (treat as a claim to verify, not ground truth)

For each file found: extract the signal, skip if absent, do not block.

After reading these, update `snapshot.stack` (languages, frameworks, services, external_dependencies) and write the snapshot.

---

## Step 2 — Entry points

Find where execution actually starts. This tells you what *kind* of thing this is.

Look for (in priority order):
- `main.py`, `app.py`, `run.py`, `manage.py` (Python)
- `index.ts`, `server.ts`, `app.ts`, `main.ts` (TypeScript)
- `index.js`, `server.js`, `app.js` (JavaScript)
- Script entries in `package.json` `scripts` field (`start`, `dev`, `serve`)
- Procfile, systemd unit files
- Docker `CMD` / `ENTRYPOINT` directives

For each entry point found: read the first 60–100 lines only. You want to know the type (HTTP server? CLI? worker? cron?) and the top-level wiring — not the full implementation.

Record each in `snapshot.structure.entry_points`. Write snapshot.

---

## Step 3 — Public surface area

Read route/endpoint definitions — this is the clearest signal of what the app *does*.

Look for:
- Express/Fastify/Hono router files: `routes/`, `api/`, `src/routes/`
- FastAPI/Flask/Django URL patterns: `urls.py`, `routes.py`, `views.py`, `routers/`
- Next.js: `app/` directory structure, `pages/api/`
- GraphQL: schema files (`*.graphql`, `schema.ts`)
- CLI commands: `commands/`, `cmd/`

**Do not read the handlers** — read only the route declarations. The pattern `GET /users/:id` tells you more than the implementation.

List the top 20 most interesting routes/endpoints in `snapshot.structure.public_surface`. Write snapshot.

Note: use `public_surface` — not `structure.layers`. The `layers` field is reserved for the map skill's logical architecture objects and has a different shape (`name/paths/responsibility`).

---

## Step 4 — Domain model

Find where the core data shapes are defined. This reveals the mental model.

Look for:
- TypeScript: `types/`, `interfaces/`, `models/`, `schemas/`, `*.types.ts`, `*.interface.ts`
- Python: `models/`, `schemas.py`, `models.py`, Pydantic models, SQLAlchemy models, dataclasses
- Database: `migrations/`, `schema.sql`, ORM model definitions

Read these files. Extract entity names and their key fields. Flag any entity that appears in both TypeScript and Python — these are cross-language models worth a consistency check later.

Record in `snapshot.structure.domain_model`. Write snapshot.

---

## Step 5 — Synthesize the product understanding

Now, without reading any more code, synthesize everything you've gathered:

**Answer these questions:**
1. What does this product do? (One sentence a non-technical person could understand)
2. Who is the intended user? (Developer? Consumer? Internal ops team? ML engineer?)
3. What problem does it solve?
4. What is its maturity level? (Prototype / MVP / Production / Legacy — and why you think so)
5. What does it *not* do that you might have expected given the name/README?

Write a `summary` (2–4 sentences), `domain`, `audience`, `maturity`, and `confidence` into `snapshot.product`.

---

## Step 6 — Output

Print a human-readable orientation report. Use this format — a single `## Orientation` title with `###` subsections (matching the shape of map/quality/story), so it nests correctly when embedded in the aggregated report in Step 7:

```
## Orientation

### What is this?
[2-4 sentence plain-English description]

### Who is it for?
[audience + use case]

### Stack at a glance
[bullet list: language%, framework, key services, notable external deps]

### Domain model (key entities)
[bullet list of 5-10 core entities with one-line descriptions]

### Public surface
[bullet list of the most important routes/endpoints/commands]

### Maturity assessment
[maturity level + 1-2 sentence justification]

### What to look at next
[2-3 recommended areas for deeper investigation — informed by what you found interesting or suspicious]
```

---

## Step 7 — Append to the aggregated report

Besides printing to the console, write the **same** human-readable content into a single aggregated file at `.archeology/report.md`, so the user can read every skill's output in one place instead of scrolling the console.

The file uses marker-delimited sections so skills can run in any order and re-runs stay idempotent:

- **If `.archeology/report.md` does not exist**, create it with this header:
  ```markdown
  # Code Archeology Report — <repo name>

  _Generated by [code-archeology](https://github.com/mu-asad/code-archeology) · last updated <UTC timestamp>_
  ```
- **Write your section** between markers, just after the header. If the block already exists, replace its contents; otherwise insert it. Keep sections in this order: `orient`, `map`, `quality`, `story`.
  ```markdown
  <!-- section:orient -->
  <the exact content you printed to the console in Step 6, verbatim — it already begins with `## Orientation`, so do not add another heading>
  <!-- /section:orient -->
  ```
- **Update** the `last updated` timestamp in the header on every write.

Then write the snapshot one final time with `orient` recorded in `meta.skills_run`.

---

## Context budget rules

This skill operates under strict context discipline. Follow these rules:

- **Never read an entire large file.** If a file is >200 lines, read only the top 80 lines unless a specific section is needed.
- **Never read `node_modules/`, `.venv/`, `__pycache__/`, `dist/`, `build/`, `.next/`, `coverage/`**. Add them to `coverage.skipped` immediately.
- **Stop and write snapshot if context feels heavy.** Better to write partial findings than lose them. The next run will resume from `coverage.queued`.
- **Prefer file listings over file reads.** `ls` and `find` are cheap. Understand the shape of a directory before deciding whether to read it.
- **If you find yourself reading implementation details**, stop — you're going too deep. Orient is a breadth-first skill.

---

## Failure modes to avoid

- **README trust**: READMEs lie, especially in AI codebases. Treat stated purpose as a hypothesis, verify against entry points and routes.
- **Framework assumption**: Don't assume a React app is a frontend just because it uses React — it might be a static site generator, an email renderer, etc.
- **Completeness pressure**: A confident partial picture is more useful than an uncertain complete one. Say what you don't know.
- **Over-reading Python**: Python scripts in a mostly-TS codebase are often glue/tooling, not the main product. Don't over-index on them.
