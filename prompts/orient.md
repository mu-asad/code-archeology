# Prompt: Orient

> **Agent-agnostic version.** Works with any agent that has terminal access and can read/write files — Claude Code, GitHub Copilot agent, Codex, Cursor, etc.
>
> **How to use:**
> - *Claude Code:* use `.claude/skills/orient/SKILL.md` — invoked automatically via `/orient`
> - *Copilot agent / Cursor:* paste this prompt or reference it with `@workspace prompts/orient.md`, then say "run the orient analysis on [path]"
> - *Any other agent:* paste the prompt content directly and specify the target repo path
>
> **Requirements:** agent must be able to run terminal/bash commands and read/write files on the local filesystem.

---

Produce a plain-English product orientation for an unfamiliar codebase. Answer: **what is this, who is it for, and what does it actually do?** — in human terms, not technical ones.

This prompt is designed to work on large repos without choking on context. Read breadth-first, never exhaustively, and write all findings to a shared snapshot file before finishing.

**Target repo:** [specify path, or assume current working directory]

---

## Step 0 — Initialize or resume snapshot

Before reading any code, check if `.archeology/snapshot.json` already exists in the target repo.

- **If it exists:** load it. Check `meta.skills_run` — if `orient` is already listed, report the existing findings and ask if the user wants to re-run. If resuming an interrupted run, continue from `coverage.queued`.
- **If it doesn't exist:** create the `.archeology/` directory and initialize a fresh snapshot. Use the schema at `schema/snapshot.schema.json` in this repo as the structure. The very first write must already satisfy the schema's required top-level keys, so initialize all of them — not just `meta`:

  ```json
  {
    "meta": { "repo": "<abs-path>", "created_at": "<now>", "updated_at": "<now>", "skills_run": [] },
    "coverage": { "analyzed": [], "queued": [], "skipped": [] },
    "stack": {},
    "product": {}
  }
  ```

  `stack` and `product` have no required sub-fields, so empty objects are valid until you fill them in later steps.

**Write the snapshot to disk after every major step.** Do not wait until the end. If context runs out mid-run, the next invocation can resume from `coverage.queued`.

---

## Step 1 — Architecture skeleton (read first, always)

Read these files in order. They give you the shape of the application before touching a single line of business logic.

1. `docker-compose.yml`, `docker-compose.yaml`, `compose.yml` — services, ports, dependencies
2. Any `Dockerfile` or `Dockerfile.*` at root
3. `package.json` (root-level) — name, description, scripts, key dependencies
4. `pyproject.toml`, `setup.py`, `requirements.txt` — Python package identity
5. `.env.example`, `.env.sample` — reveals expected configuration and integrations
6. Root-level `README.md` — stated intent (treat as a claim to verify, not ground truth)

For each file: extract the signal, skip if absent, do not block.

After reading, populate `snapshot.stack` (languages, frameworks, services, external_dependencies) and write the snapshot.

---

## Step 2 — Entry points

Find where execution actually starts. This tells you what *kind* of thing this is.

Look for (priority order):
- `main.py`, `app.py`, `run.py`, `manage.py` (Python)
- `index.ts`, `server.ts`, `app.ts`, `main.ts` (TypeScript)
- `index.js`, `server.js`, `app.js` (JavaScript)
- Script entries in `package.json` `scripts` field (`start`, `dev`, `serve`)
- Procfile, systemd unit files
- Docker `CMD` / `ENTRYPOINT` directives

For each entry point: read the first 60–100 lines only. Identify the type (HTTP server, CLI, worker, cron?) and top-level wiring — not the full implementation.

Record each in `snapshot.structure.entry_points`. Write snapshot.

---

## Step 3 — Public surface area

Read route/endpoint definitions — the clearest signal of what the app *does*.

Look for:
- Express/Fastify/Hono router files: `routes/`, `api/`, `src/routes/`
- FastAPI/Flask/Django URL patterns: `urls.py`, `routes.py`, `views.py`, `routers/`
- Next.js: `app/` directory structure, `pages/api/`
- GraphQL: schema files (`*.graphql`, `schema.ts`)
- CLI commands: `commands/`, `cmd/`

**Do not read the handlers** — read only the route declarations. `GET /users/:id` tells you more than the implementation.

List the top 20 most interesting routes/endpoints in `snapshot.structure.public_surface`. Write snapshot.

Note: use `public_surface` — not `structure.layers`. The `layers` field is reserved for the map skill's logical architecture objects and has a different shape (`name/paths/responsibility`).

---

## Step 4 — Domain model

Find where core data shapes are defined. This reveals the mental model.

Look for:
- TypeScript: `types/`, `interfaces/`, `models/`, `schemas/`, `*.types.ts`, `*.interface.ts`
- Python: `models/`, `schemas.py`, `models.py`, Pydantic models, SQLAlchemy models, dataclasses
- Database: `migrations/`, `schema.sql`, ORM model definitions

Extract entity names and key fields. Flag any entity appearing in both TypeScript and Python — these are cross-language models worth a consistency check later.

Record in `snapshot.structure.domain_model`. Write snapshot.

---

## Step 5 — Synthesize

Without reading any more code, synthesize everything gathered:

1. What does this product do? (One sentence a non-technical person could understand)
2. Who is the intended user?
3. What problem does it solve?
4. What is its maturity level? (Prototype / MVP / Production / Legacy — and why)
5. What does it *not* do that you might have expected given the name/README?

Write a `summary` (2–4 sentences), `domain`, `audience`, `maturity`, and `confidence` into `snapshot.product`.

---

## Step 6 — Output

Print a human-readable orientation report:

```
## What is this?
[2-4 sentence plain-English description]

## Who is it for?
[audience + use case]

## Stack at a glance
[bullet list: language%, framework, key services, notable external deps]

## Domain model (key entities)
[bullet list of 5-10 core entities with one-line descriptions]

## Public surface
[bullet list of most important routes/endpoints/commands]

## Maturity assessment
[maturity level + 1-2 sentence justification]

## What to look at next
[2-3 recommended areas for deeper investigation]
```

---

## Context budget rules

- **Never read an entire large file.** Files >200 lines: read only the top 80 lines unless a specific section is needed.
- **Never read** `node_modules/`, `.venv/`, `__pycache__/`, `dist/`, `build/`, `.next/`, `coverage/`. Add them to `coverage.skipped`.
- **Write snapshot if context feels heavy.** Partial findings are better than lost findings.
- **Prefer listing over reading.** Understand a directory's shape before deciding to read it.
- **If reading implementation details**, stop — too deep. This is a breadth-first prompt.

---

## Failure modes to avoid

- **README trust**: READMEs lie, especially in AI codebases. Treat stated purpose as a hypothesis.
- **Framework assumption**: Don't assume a React app is a frontend just because it uses React.
- **Completeness pressure**: A confident partial picture beats an uncertain complete one.
- **Over-reading Python**: Python scripts in a mostly-TS codebase are often glue/tooling, not the main product.
