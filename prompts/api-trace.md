# Prompt: API Trace

> **Agent-agnostic version.** Works with any agent that has terminal access and can read/write files — Claude Code, GitHub Copilot agent, Codex, Cursor, etc.
>
> **How to use:**
> - *Claude Code:* use `.claude/skills/api-trace/SKILL.md` — invoked automatically via `/api-trace`
> - *Copilot agent / Cursor:* paste this prompt or reference it with `@workspace prompts/api-trace.md`, then say "run the api-trace analysis on [path]"
> - *Any other agent:* paste the prompt content directly and specify the target repo path
>
> **Requirements:** agent must be able to run terminal/bash commands and read/write files.
> **Prerequisite:** run the `orient` prompt first. Runs better after `map`; works without it.

---

Trace every API method from its external boundary through the internal call path to the core business logic, then write a Markdown report with precise repository references and optional Mermaid diagrams.

The goal: **for every API method, where does the request enter, what files does it pass through, where is the actual decision made, what side effects occur, and where does the response leave?**

This is evidence-based tracing, not convention guessing. Every layer in a trace was read; every layer omitted is explicitly noted.

**Target repo:** [specify path, or assume current working directory]

> **Resolve the target root first.** If a path is given — or you launched the agent from a different directory — `cd` into the target repo before running any steps, so every command operates on that repo. Every step below assumes commands run **inside the target repo**.

**Options:**
- `--api <name>` — limit to one API group (e.g. `users`, `payments`)
- `--diagram` — emit a Mermaid flowchart per traced method
- `--max-methods N` — cap full traces at N (default: 20)

---

> **Start this skill in a fresh conversation.** Load the snapshot, do the work, end the session. The snapshot has everything prior skills found — there is no need to carry their context forward. Chaining skills in one conversation bloats context; on large repos it will exhaust it.

## Step 0 — Load context

Load `.archeology/snapshot.json`. If it doesn't exist, run the `orient` prompt first.

Pull in prior analysis:
- `snapshot.structure.public_surface` — discovered routes/endpoints (use as seed list)
- `snapshot.structure.layers` — logical layers from `map` (avoids re-deriving architecture)
- `snapshot.structure.domain_model` — key entities (helps identify where business logic lives)
- `snapshot.quality.structural.complexity_hotspots` — large/complex files

**Write snapshot after every major step.**

---

## Step 1 — Discover API boundaries

Identify every file that acts as an external-facing entry point.

**HTTP frameworks:**
- Express/Fastify/Hono: `routes/`, `api/`, router files with `.get(`, `.post(`, `.put(`, `.delete(`, `.patch(`
- FastAPI/Flask/Django: `routers/`, `views.py`, `urls.py`, `@app.route`, `@router.get`, `@api_view`
- Next.js: `app/` with `route.ts`/`route.js`, `pages/api/`

**Other API styles:**
- GraphQL: `resolvers/`, `Query`/`Mutation`/`Subscription` resolver maps, `*.graphql` schema
- gRPC/RPC: `*.proto`, handler files implementing generated service interfaces
- Webhooks: `webhook*` files, callback handler registrations
- Queue consumers: `consumer*`, `subscriber*`, `processor*` in `queues/` or `workers/`
- Serverless: `functions/`, `lambdas/`, exported `handler` functions
- CLI: `commands/`, `cmd/`, files using `yargs`, `commander`, `argparse`, `click`

Discover boundary files using git's tracked-file list (respects .gitignore):

```bash
grep -rEl "\.get\(|\.post\(|\.put\(|\.delete\(|@router\.|@app\.route|@api_view" \
  --include="*.ts" --include="*.js" --include="*.py" . \
  | grep -vF node_modules | grep -vF dist | grep -vF /.venv/ | grep -vF /build/ | head -30
```

Group boundary files by API domain if the structure makes that natural. If `--api <name>` was passed, filter to matching files.

Record in `snapshot.api_trace.boundaries`. Write snapshot.

---

## Step 2 — Build the method inventory

For each boundary file, read the route/handler declarations (not implementations). Extract:
- HTTP method + path, or resolver/operation name
- Handler function name
- File path + line number
- Auth/middleware visible at the route level

Build the inventory table:

```
| Method | Path / Operation | Boundary File | Handler | Auth / Middleware | Trace Status |
|--------|------------------|---------------|---------|-------------------|--------------|
| POST   | /users           | src/routes/users.ts:42 | createUser | requireAuth | pending |
```

Trace Status starts as `pending`. Cap at `--max-methods` (default 20) — prefer high-complexity areas and the targeted `--api` group.

Record in `snapshot.api_trace.inventory`. Write snapshot.

---

## Step 3 — Trace each method (the core)

For each method, **follow the actual code path** — don't assume layers from naming conventions.

**For each method, trace:**
1. **Validation** — where is the request body/params read and validated? Is the result actually checked before the handler continues?
2. **Auth / permissions** — middleware, guards, `req.user` checks. Is auth enforced at the route, or only wired?
3. **Service / application layer** — the first function outside the handler. What does it coordinate?
4. **Core logic / domain decision** — where is the actual business rule? Not the controller, not the repository — the decision point.
5. **Persistence** — ORM calls, DB queries, cache operations. Which file, what operation?
6. **External side effects** — emails, events, queue publishes, external HTTP calls. When do they trigger?
7. **Response construction** — where is the response shaped? Is there a serializer?
8. **Error handling** — try/catch in the handler? Typed errors? Global error boundary?
9. **Tests** — grep for the handler name or route path in test files. What do they assert?

**Tracing mechanics:**
- Read the handler function first. For each outbound call, grep for its definition and read it too.
- If a call is dynamically resolved (DI container, strategy, dynamic import), note it as the trace boundary and mark the method `partial` or `ambiguous`.
- Stop at third-party library boundaries, raw DB driver calls, or external HTTP clients.

**Confidence labels:**
- `traced` — code path read end-to-end
- `partial` — most traced, but one or more layers unread or behind dynamic dispatch
- `ambiguous` — routing or handler resolution is dynamic; path unclear
- `generated-from-convention` — no code traced; inferred from naming (flag prominently — not a real trace)

Record per method: file:line for each layer touched. Write snapshot after each completed trace.

---

## Step 4 — Flag boundary concerns

For each traced method, assess:
- **Validation gaps** — data used before validation, or validation present but result not checked
- **Auth gaps** — missing auth enforcement, or auth wired at router but not applied to the route
- **Leaked domain logic** — business rules in the controller
- **Untestable paths** — error paths or edge cases with no test coverage
- **Missing error handling** — no try/catch, no global error boundary
- **Side-effect surprise** — side effects (emails, events) in unexpected layers

Record per-method concerns in `snapshot.api_trace.methods[].boundary_concerns`.

---

## Step 5 — Output (console summary)

Print to the console:

```
## API Trace

### Discovered [N] API methods across [M] boundary files

[Method inventory table]

### Traced [X] / [N] methods
- traced: [count]
- partial: [count]
- ambiguous: [count]
- generated-from-convention: [count, with warning if > 0]

### Key findings
[3-5 bullet points: auth gaps, validation mismatches, test holes, leaked domain logic, surprise side effects]

### Full traces
[see .archeology/api-trace.md]
```

---

## Step 6 — Write .archeology/api-trace.md

Create or update the file with full per-method detail:

```markdown
# API Trace

_Generated by [code-archeology](https://github.com/mu-asad/code-archeology) · last updated <UTC timestamp>_

## Method Inventory

[full table]

---

## Method Details

### [METHOD] [path/operation]

**Status:** [traced | partial | ambiguous | generated-from-convention]
**Handler:** `path/to/handler.ts:lineN`

#### Trace

- **Validation:** `src/schemas/create-user.ts:12` — Zod schema, result checked before handler continues
- **Auth:** `src/middleware/requireAuth.ts:8` — JWT verified, user attached to req.user
- **Service:** `src/services/UserService.ts:55` — coordinates policy + repo
- **Core logic:** `src/domain/users/create-user.ts:88` — uniqueness check, emits domain event
- **Persistence:** `src/db/UserRepository.ts:31` — Prisma INSERT
- **Side effects:** `src/events/UserCreated.ts:12` — publishes to event bus
- **Response:** 201 with serialized user
- **Error handling:** try/catch; DomainError → 400, unknown → 500

#### Boundary Concerns

[flags from Step 4, or "None identified."]

#### Tests

- `tests/users/create-user.test.ts:17` — happy path + duplicate-email error
- Note: event publishing is mocked; event payload shape not verified

[if --diagram was passed:]
#### Diagram

\`\`\`mermaid
flowchart TD
  A["POST /users"] --> B["routes/users.ts:createUser"]
  B --> C["validateCreateUser · schemas/create-user.ts:12"]
  C --> D["UserService.create · services/UserService.ts:55"]
  D --> E["UserPolicy.canCreate · domain/policy.ts:14"]
  D --> F["UserRepository.insert · db/UserRepository.ts:31"]
  D --> G["UserCreated event · events/UserCreated.ts:12"]
  F --> H["201 response"]
\`\`\`
```

Omit `#### Diagram` if `--diagram` was not requested.

---

## Step 7 — Snapshot + aggregated report

Record under `snapshot.api_trace`:
- `inventory` — array of `{ method, path, boundary_file, handler, auth_middleware, trace_status }`
- `methods` — array of per-method detail objects
- `boundaries` — array of discovered boundary files
- `untraced_or_ambiguous` — array of `{ identifier, reason }` for incomplete traces
- `output_path` — `".archeology/api-trace.md"`

Append to `.archeology/report.md` (create with standard header if absent):

- Insert or replace your marker-delimited section. Keep section order `orient`, `map`, `api-trace`, `quality`, `the-finder-outer`, `story`:
  ```markdown
  <!-- section:api-trace -->
  <the same console summary from Step 5, verbatim — it already begins with `## API Trace`, so do not add another heading>
  <!-- /section:api-trace -->
  ```
- Update the `last updated` timestamp in the header.

Then write the snapshot one final time with `api-trace` added to `meta.skills_run`.

---

## Context budget rules

- **Inventory is cheap; tracing is expensive.** Spend context on Step 3.
- **Cap at `--max-methods` (default 20).** A well-traced subset beats a table of guesses.
- **Trace one method fully before starting the next.**
- **Write snapshot and api-trace.md after each completed trace.** Enables resumption on context exhaustion.
- **Use grep + head to find specific functions** — read the function, not the whole file.
- **Skip:** `node_modules/`, `.venv/`, `dist/`, `build/`, `generated/`, `*.generated.*`, `*.pb.*`, `coverage/`.

---

## Failure modes to avoid

- **Convention-guessing as tracing.** "Validation likely happens in the schema layer" without reading is `generated-from-convention` — label it.
- **Stopping at the controller.** Follow the service call. Follow it again. Stop only at the actual decision.
- **Omitting error paths.** API behavior includes failures.
- **Omitting tests.** Note what's tested, even if the answer is "nothing."
- **Inventing Mermaid layers.** Only include nodes you actually traced.
- **Treating auth as present when only wired.** Middleware registered at the router but not applied to the route is not enforcement.
