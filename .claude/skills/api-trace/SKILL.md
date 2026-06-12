---
name: api-trace
description: Trace API methods from external boundary to core business logic. For every route, resolver, handler, or RPC method — where does the request enter, what files does it pass through, where is the actual decision made, what side effects occur, and where does the response leave? Produces a method inventory, per-method traces with precise file:line references, optional Mermaid diagrams, and a .archeology/api-trace.md report. Use when the user wants to understand API behavior end-to-end, review whether routes preserve domain boundaries, find where auth/validation/persistence happen, or produce onboarding-quality documentation. Best after /orient and /map; reads and writes .archeology/snapshot.json.
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
  - Bash(git ls-files *)
  - Bash(git status *)
---

# api-trace

**Where `/map` shows the layers and `/quality` grades the craft, this skill follows the traffic.** For every API method, it traces the actual code path from the external boundary — the route, resolver, handler — through every file it touches, all the way to where the decision is made and the response is built.

The goal is to produce something genuinely useful for onboarding, code review, and trust assessment: **precise, evidence-backed traces**, not convention-guessed skeletons. Every layer included in a trace was actually read; every layer omitted is explicitly noted as untraced.

---

## How to invoke

```
/api-trace [path-to-repo]
/api-trace [path-to-repo] --api users         # limit to one API group
/api-trace [path-to-repo] --diagram           # emit Mermaid flowchart per traced method
/api-trace [path-to-repo] --max-methods 15    # cap full traces (default: 20)
```

If no path is given, use the current working directory.

**Resolve the target root first.** If a path *is* given — or the repo lives somewhere other than your cwd — `cd` into it before running any steps. Every step below assumes commands run **inside the target repo**.

**Prerequisite**: run `/orient` first. Runs better after `/map` (which identifies layers), but works without it.

---

> **Start this skill in a fresh conversation.** Load the snapshot, do the work, end the session. The snapshot has everything prior skills found — there is no need to carry their context forward. Chaining skills in one conversation bloats context; on large repos it will exhaust it.

## Step 0 — Load context

Load `.archeology/snapshot.json`. If it doesn't exist, tell the user to run `/orient` first.

When citing repo-wide aggregate facts (commit counts, date span, tracked files, entry point counts), use `snapshot.meta.stats` from `/orient`. Before citing a value, confirm the specific needed field is present and non-null. Do not recompute or publish alternate counts. If `meta.stats` is missing, or any needed field is absent/null, treat stats as unavailable and recommend re-running `/orient` rather than guessing.

Pull in prior analysis:
- `snapshot.structure.public_surface` — `/orient`'s discovered routes/endpoints (use as seed list)
- `snapshot.structure.layers` — `/map`'s logical layers (avoids re-deriving the architecture)
- `snapshot.structure.domain_model` — key entities (helps identify where the real business logic lives)
- `snapshot.quality.structural.complexity_hotspots` — large/complex files (likely candidates for core logic)

If `api-trace` is already in `meta.skills_run`, report the existing findings and ask if the user wants to re-run.

**Write snapshot after every major step.**

---

## Step 1 — Discover API boundaries

Identify every file that acts as an external-facing entry point. This is the boundary layer — where the outside world enters the codebase.

### What to look for

**HTTP frameworks:**
- Express/Fastify/Hono: `routes/`, `api/`, `src/routes/`, `src/api/`, router files with `.get(`, `.post(`, `.put(`, `.delete(`, `.patch(`
- FastAPI/Flask/Django: `routers/`, `views.py`, `urls.py`, files with `@app.route`, `@router.get`, `@api_view`
- Next.js: `app/` directory with `route.ts`/`route.js`, `pages/api/`

**Other API styles:**
- GraphQL: `resolvers/`, files with `Query`, `Mutation`, `Subscription` resolver maps, `*.graphql` schema
- gRPC/RPC: `*.proto`, handler files that implement generated service interfaces
- Webhooks: files named `webhook*`, handlers registered with Stripe/GitHub/etc callback patterns
- Queue consumers acting as API boundaries: `consumer*`, `subscriber*`, `handler*`, `processor*` in a `queues/` or `workers/` dir
- Serverless: `functions/`, `lambdas/`, `handler.ts`, files exporting a handler function
- CLI: `commands/`, `cmd/`, files using `yargs`, `commander`, `argparse`, `click`

### How to discover

Start with what `/orient` already found in `snapshot.structure.public_surface`. Then verify and extend:

```bash
# Find route/controller files (git ls-files respects .gitignore; no xargs —
# it's deliberately not in the allowlist)
git ls-files '*.ts' '*.js' '*.py' | while IFS= read -r f; do
  grep -qE "\.get\(|\.post\(|\.put\(|\.delete\(|@router\.|@app\.route|@api_view" "$f" 2>/dev/null && echo "$f"
done | head -30
```

Or grep directly across the tracked files:
```bash
grep -rEl "\.get\(|\.post\(|\.put\(|\.delete\(|@router\." --include="*.ts" --include="*.js" --include="*.py" . \
  | grep -vF node_modules | grep -vF dist | grep -vF /.venv/ | head -30
```

Group boundary files by **API domain** (e.g. `users`, `payments`, `auth`, `webhooks`) if the structure makes that natural.

If `--api <name>` was passed, filter to only boundary files matching that group.

Record discovered boundary files in `snapshot.api_trace.boundaries`. Write snapshot.

---

## Step 2 — Build the method inventory

For each boundary file, read the route/handler declarations (not the implementations). Extract:
- HTTP method + path, or resolver/operation name, or RPC method name
- Handler function name
- File path + line number (grep for the declaration line)
- Auth/middleware wiring visible at the route level

Build the inventory table — this is the output of Step 2:

```
| Method | Path / Operation | Boundary File | Handler | Auth / Middleware | Trace Status |
|--------|------------------|---------------|---------|-------------------|--------------|
| POST   | /users           | src/routes/users.ts:42 | createUser | requireAuth | pending |
```

`Trace Status` starts as `pending` and gets updated in Step 3 to one of: `traced`, `partial`, `ambiguous`, `generated-from-convention`.

Cap at `--max-methods` (default: 20). If there are more methods than the cap, note the total count, apply the cap, and favor: methods in high-complexity areas (from `/quality` hotspots), methods in the targeted `--api` group, methods with the most middleware/complexity visible at declaration.

Record the inventory in `snapshot.api_trace.inventory`. Write snapshot.

---

## Step 3 — Trace each method (the core)

This is the skill's core step. For each method in the inventory, **follow the actual code path** — don't assume layers from naming conventions.

### What to trace

For each method, read the handler function and follow every call outward:

1. **Request parsing & validation** — where is the incoming body/params read? Is there schema validation (Zod, Joi, Pydantic, class-validator, manual)? Does it actually gate the handler, or happen after?
2. **Auth / permission checks** — middleware at the route level, guards, `req.user` checks inside the handler. Is auth actually enforced, or wired but not checked?
3. **Service / application layer** — the first function outside the handler. What does it do? Does it coordinate multiple domain calls?
4. **Core logic / domain decision** — where is the actual business rule? This is NOT the controller and NOT the repository — it's where the decision about the domain entity is made. If you can't find a distinct domain layer, note it.
5. **Persistence** — database queries, ORM calls, cache reads/writes. Which repository/query file? What operation?
6. **External side effects** — emails, events, webhooks, external API calls, queue messages. What triggers them? Are they in the happy path or the error path?
7. **Response construction** — where is the response shaped? Is there a serializer/transformer between the domain object and the response?
8. **Error handling** — does the handler have try/catch? Are errors typed? Are errors returned as structured responses or thrown as exceptions that bubble to a global handler?
9. **Tests** — `grep -rn` for the handler name or route path in test files. What do the tests actually assert?

### Tracing mechanics

- Read the handler function first (not the full file — find the function, read 50–100 lines around it).
- For each outbound function call, `grep -rn` for its definition if it's in a different file. Read that function too.
- If a call is dynamically resolved (interface + DI container, strategy pattern, dynamic import), note it as a boundary of the trace and mark the method as `partial` or `ambiguous`.
- Stop tracing when you reach: a third-party library boundary, a raw DB driver call, an external HTTP call, or a queue publish. These are the leaf nodes of the trace.

### Confidence labels

Assign one of these per method:
- **`traced`** — you read and followed the actual code path end-to-end
- **`partial`** — you traced most of it but one or more layers are unread (out of context budget) or behind dynamic dispatch
- **`ambiguous`** — routing is dynamic, handler is resolved at runtime, or the codebase uses deep abstraction that makes the path unclear
- **`generated-from-convention`** — no code was traced; the trace was inferred from naming/directory conventions (flag these prominently — they are not real traces)

For each finding: note the **file path and line number** where you read it.

Write snapshot after each completed trace.

---

## Step 4 — Flag boundary concerns

After tracing, assess each method for:

- **Validation gaps** — request data used before validation, or validation present but result not checked
- **Auth gaps** — route lacks auth middleware, or auth check is present but bypassable
- **Leaked domain logic** — business rules sitting in the controller/handler
- **Untestable paths** — error paths, external calls, or edge cases with no test coverage
- **Missing error handling** — handler has no try/catch and no global error boundary
- **Side-effect surprise** — side effects (emails, events, external calls) happening in unexpected layers

Record per-method concerns in `snapshot.api_trace.methods[].boundary_concerns`. Write snapshot.

---

## Step 5 — Output (console summary)

Print a concise summary to the console:

```
## API Trace

### Discovered [N] API methods across [M] boundary files

[Method inventory table — trimmed if over 20 rows]

### Traced [X] / [N] methods
- traced: [count]
- partial: [count]
- ambiguous: [count]
- generated-from-convention: [count, with warning if > 0]

### Key findings
[3-5 bullet points: the most important things discovered during tracing — auth gaps, validation mismatches, test coverage holes, leaked domain logic, surprise side effects]

### Full traces
[see .archeology/api-trace.md]
```

Keep the console output scannable. The full per-method detail goes in the file output in Step 6.

---

## Step 6 — Write .archeology/api-trace.md

Create or update `.archeology/api-trace.md` with the full traced output:

```markdown
# API Trace

_Generated by [code-archeology](https://github.com/mu-asad/code-archeology) · last updated <UTC timestamp>_

## Method Inventory

| Method | Path / Operation | Boundary File | Handler | Auth / Middleware | Trace Status |
|--------|-----------------|---------------|---------|-------------------|--------------|
[full table]

---

## Method Details

### [METHOD] [path/operation]

**Status:** [traced | partial | ambiguous | generated-from-convention]
**Handler:** `path/to/handler.ts:lineN`

#### Trace

- **Validation:** `src/schemas/create-user.ts:12` — Zod schema, result checked before handler continues
- **Auth:** `src/middleware/requireAuth.ts:8` — JWT verified, user attached to req.user
- **Service:** `src/services/UserService.ts:55` — UserService.create, coordinates policy + repo
- **Core logic:** `src/domain/users/create-user.ts:88` — checks uniqueness policy, emits domain event
- **Persistence:** `src/db/UserRepository.ts:31` — INSERT via Prisma, returns created record
- **Side effects:** `src/events/UserCreated.ts:12` — publishes UserCreated to event bus
- **Response:** handler returns 201 with serialized user object
- **Error handling:** try/catch in handler; maps DomainError to 400, unknown to 500

#### Boundary Concerns

[any flags from Step 4, or "None identified."]

#### Tests

- `tests/users/create-user.test.ts:17` — covers happy path and duplicate-email error
- Note: external event publishing is mocked; the test does not verify the event payload shape

[if --diagram flag was passed:]
#### Diagram

\`\`\`mermaid
flowchart TD
  A["POST /users"] --> B["routes/users.ts:createUser"]
  B --> C["validateCreateUser · schemas/create-user.ts:12"]
  C --> D["UserService.create · services/UserService.ts:55"]
  D --> E["UserPolicy.canCreate · domain/users/policy.ts:14"]
  D --> F["UserRepository.insert · db/UserRepository.ts:31"]
  D --> G["UserCreated event · events/UserCreated.ts:12"]
  F --> H["201 response"]
\`\`\`

---

### [next method]
```

If the diagram flag was not passed, omit the `#### Diagram` section entirely. Do not generate placeholder diagrams.

---

## Step 7 — Snapshot + aggregated report

Record findings under `snapshot.api_trace`:
- `inventory` — array of `{ method, path, boundary_file, handler, auth_middleware, trace_status }`
- `methods` — array of per-method detail objects (see schema)
- `boundaries` — array of discovered boundary files
- `untraced_or_ambiguous` — array of method identifiers that could not be fully traced, with reason
- `output_path` — `".archeology/api-trace.md"`

Then append to `.archeology/report.md` (create with standard header if absent):

- Insert or replace the marker-delimited section. Keep section order `orient`, `map`, `api-trace`, `quality`, `the-finder-outer`, `story`:
  ```markdown
  <!-- section:api-trace -->
  <the same console summary from Step 5, verbatim — it already begins with `## API Trace`, so do not add another heading>
  <!-- /section:api-trace -->
  ```
- Update the `last updated` timestamp in the header.

Then write the snapshot one final time with `api-trace` added to `meta.skills_run`.

Optionally, if `.claude/skills/validate.py` is available and you have permission to run `python3`, validate your output: `python3 .claude/skills/validate.py <target-repo>`. Do not add interpreters to any allowlist for this — when in doubt, skip it; the run.sh wrapper performs this check deterministically anyway.

---

## Context budget rules

- **Inventory is cheap; tracing is expensive.** Step 1–2 cost almost nothing. Step 3 is where context goes — spend it on the most important methods.
- **Cap traces at `--max-methods` (default 20).** A well-traced subset beats a table of guesses.
- **Trace one method fully before starting the next.** Don't skim all handlers first — you'll run out of budget before going deep on any.
- **Stop the trace at the leaf node.** Don't read into third-party libraries, raw DB drivers, or HTTP client internals.
- **Write snapshot and api-trace.md after every completed trace.** If context runs out mid-run, the next invocation finds completed traces already persisted.
- **Prefer grep + head over full-file reads.** Read the specific function you need, not the entire file.
- **Never read:** `node_modules/`, `.venv/`, `dist/`, `build/`, `generated/`, `*.generated.*`, `*.pb.*`, `coverage/`.

---

## Failure modes to avoid

- **Convention-guessing as tracing.** Do not write "validation likely happens in the schema layer" unless you read it. That's `generated-from-convention` — label it, don't present it as a trace.
- **Stopping at the controller.** The controller is not the core. Follow the service call. Follow it again. Stop only when you've reached the actual decision.
- **Omitting error paths.** API behavior includes failures. A handler that swallows errors silently is a finding.
- **Omitting tests.** Note what's tested, even if the answer is "nothing traces to a real test."
- **Inventing Mermaid layers.** Only include nodes you actually traced. A diagram with placeholder boxes is misleading.
- **Over-tracing.** If you're 6 function calls deep into a logging utility, stop. The trace is about the domain path, not infrastructure plumbing.
- **Treating auth as present when it's only wired.** Middleware registered at the router level but not applied to a specific route is not auth enforcement. Check the route, not just the router setup.
