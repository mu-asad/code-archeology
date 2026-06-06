# code-archeology

A collection of Claude Code skills for understanding large, unfamiliar codebases — including AI-generated ones. The goal is clarity in both technical and human terms: not just *what the code does*, but *what the product is*, *who it's for*, and *whether it's actually well-built*.

> Working shit code is still shit. These skills are designed to tell you the difference — to separate "this runs" from "this is good."

---

## Quick start

**1. Install the skills** so Claude Code can find them. Copy both the skills **and** the bundled `settings.json` (it allowlists the git commands the skills run, so you don't get repeated permission prompts):

```bash
# Option A — global (available in every project)
cp -r .claude/skills/* ~/.claude/skills/
# merge the permission allowlist into your global settings (or copy if you have none)
cp .claude/settings.json ~/.claude/settings.json

# Option B — per-project (copy the whole .claude/ so settings come along)
cp -r .claude <target-repo>/
```

> The allowlist only covers read-only git commands. Standard UNIX tools the skills use (`find`, `grep`, `wc`, `sort`, `head`, `tail`, etc.) are already auto-allowed by Claude Code, so no extra config is needed for them.

**2. Run the skills** from inside the target repo, in order:

```
/orient      # start here — always
/map         # then any of these, in any order
/quality
/story
```

**3. Read the report** printed to your conversation, and find the saved artifacts in `.archeology/` (see [What you get](#what-you-get)).

> Not using Claude Code? See [Agent compatibility](#agent-compatibility) — the same skills run as plain prompts in Copilot agent, Cursor, Codex, etc.

---

## Skills

| Skill | Answers | Prereq |
|-------|---------|--------|
| `/orient` | What is this, who is it for, what does it do? | none |
| `/map` | How is it structured — layers, data flow, cross-cutting concerns? | `/orient` |
| `/quality` | Is it actually well-built — structurally, intentionally, and in craft? | `/orient` |
| `/story` | How did it evolve — origins, pivots, abandoned work? | `/orient` |

Start with `/orient` (it builds the shared snapshot everything else reads). After that, run whichever skills answer your question — they're independent.

---

## What you get

Each skill prints a human-readable report **and** writes structured artifacts into an `.archeology/` directory in the analyzed repo:

```
.archeology/
  snapshot.json     # shared structured findings — all skills read & write this
  map.mmd           # Mermaid architecture diagram (from /map)
  story.md          # prose development narrative (from /story)
```

### Example: what `/orient` prints

```
## What is this?
A self-hosted invoicing tool for freelancers. Users connect a Stripe
account, generate branded invoices, and track payment status. Built as a
single-tenant app — one deployment per user.

## Who is it for?
Solo freelancers and very small agencies who want to avoid SaaS invoicing
fees. Technical enough to self-host via Docker.

## Stack at a glance
- TypeScript (62%), Python (24%), Docker, HTML
- Next.js frontend + Express API; Python service for PDF generation
- Services: web, api, pdf-worker, postgres, redis
- External: Stripe (payments), SendGrid (email)

## Maturity assessment
MVP. Core invoice flow is complete and tested, but no multi-tenancy,
thin error handling on the payment webhook, and a half-built "recurring
invoices" feature behind a disabled flag.

## What to look at next
- The Stripe webhook handler (api/webhooks/stripe.ts) — payment-critical,
  lightly tested
- The cross-language Invoice model (TS + Python) — likely drift risk
```

### Example: what `/quality` prints

```
## Quality Assessment: C

### The verdict
This codebase has the personality of a confident first draft. The happy
path is clean and the type definitions are genuinely good, but the error
handling is theater — try/catch blocks that swallow failures and log
nothing. It reads like it was built fast by someone competent who never
came back to harden it...

### If I had to fix one thing first
The payment webhook silently swallows Stripe signature-verification
failures. That's a correctness and security hole, not a style nit.
```

The point: you get a **narrative verdict** a human can act on, not just a pile of metrics.

---

## How it works

Each skill reads from and writes to `.archeology/snapshot.json`. This shared artifact is the backbone:

- **No re-reading** — skills consume prior analysis instead of re-scanning the codebase
- **Resumable** — if a run is interrupted (large repos can exhaust context), the next run picks up from where it stopped via the snapshot's coverage map
- **Context-aware** — later skills inherit domain context from earlier ones, so judgments like "this is a bad abstraction" are grounded in what the domain actually needs

The `.archeology/` directory is local to the analyzed repo. **Add it to that repo's `.gitignore`** — it's analysis output, not source.

---

## Designed for large codebases

Built with strict context discipline so they don't choke on big repos:

- **Breadth-first, not exhaustive** — reads the boundary layer (entry points, routes, types, infra) before any implementation
- **Progressive snapshot writes** — findings are persisted incrementally, after every step, not just at the end
- **Coverage tracking** — the snapshot records what's been read, queued, and skipped, enabling clean resumption
- **File-size limits** — no skill reads a complete large file when the first 80 lines answer the question

---

## Stack support

Tuned for the modern polyglot stack:

- **TypeScript / JavaScript** — framework detection, type quality, `any`/`@ts-ignore` analysis
- **Python** — async patterns, type-annotation coverage, module structure
- **Docker / Compose** — service architecture, build quality, security signals
- **HTML / static assets** — mined as signal for domain and audience

---

## Agent compatibility

The `.claude/skills/` versions are Claude Code-native — auto-discovered and invoked via `/orient` etc.

The `prompts/` directory mirrors the same skills — same steps, same snapshot contract, same output format — repackaged for **any agent with terminal + file access**. (The wording differs slightly: the prompt versions add agent-agnostic framing and drop Claude Code-specific phrasing, so they're parallel rather than byte-for-byte identical.)

| Agent | How to use |
|-------|-----------|
| Claude Code | `/orient` — auto-invoked from `.claude/skills/` |
| GitHub Copilot agent | `@workspace prompts/orient.md` → "run this on [path]" |
| Cursor | Reference `prompts/orient.md` in your prompt |
| Any other agent | Paste the prompt content directly |

The snapshot file is the same regardless of which agent runs the skill, so agents can **hand off between steps** — run `/orient` in one tool, `/quality` in another, against the same `.archeology/snapshot.json`.

---

## Schema

The snapshot contract lives at [`schema/snapshot.schema.json`](schema/snapshot.schema.json) — a JSON Schema defining the shared artifact all skills read from and write to. If you're building tooling on top of the output, validate against this.
