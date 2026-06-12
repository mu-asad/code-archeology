# code-archeology

A collection of Claude Code skills for understanding large, unfamiliar codebases — including AI-generated ones. The goal is clarity in both technical and human terms: not just *what the code does*, but *what the product is*, *who it's for*, and *whether it's actually well-built*.

> Working shit code is still shit. These skills are designed to tell you the difference — to separate "this runs" from "this is good."

---

## Repository layout

```
.claude/skills/<name>/SKILL.md   # the skills (orient, map, api-trace, quality, the-finder-outer, story)
.claude/settings.json            # git-command allowlist bundled with the skills
schema/snapshot.schema.json      # the shared .archeology/snapshot.json contract
```

Each skill is a directory with a `SKILL.md` (the format Claude Code auto-discovers) — not a flat file.

---

## Quick start

**1. Copy the skills into the repo you want to analyze.** Copy the whole `.claude/` directory so the bundled `settings.json` (which allowlists the git commands the skills run) comes along — otherwise you'll get repeated permission prompts:

```bash
# from inside this repo, with <target-repo> = the codebase you want to understand
cp -r .claude <target-repo>/
```

Claude Code auto-discovers `<target-repo>/.claude/skills/`, so the next time you launch `claude` from inside `<target-repo>`, the `/orient`, `/map`, `/api-trace`, `/quality`, `/the-finder-outer`, and `/story` commands are available — no global install, nothing in `~/.claude/`.

> **Tip:** add `/.claude/skills/` and `/.archeology/` to the target repo's `.gitignore` so you don't commit the tooling or its output into someone else's project.
>
> The allowlist only covers read-only git commands. Standard UNIX tools the skills use (`find`, `grep`, `wc`, `sort`, `head`, `tail`, etc.) are already auto-allowed by Claude Code, so no extra config is needed for them.
>
> **Prefer not to copy at all?** Launch from *this* repo and point the skills at the target instead: `cd code-archeology && claude --add-dir <target-repo>`, then `/orient <target-repo>`. The skills load from here and write `.archeology/` into the target.

**2. Run each skill in its own fresh conversation** — do not chain them in a single session:

```
/orient            # session 1 — always start here
/map               # session 2
/api-trace         # session 3
/quality           # session 4
/the-finder-outer  # session 5
/story             # session 6
```

Each skill writes its findings to `.archeology/snapshot.json` when it finishes. The next skill opens a fresh conversation, loads the snapshot, and picks up from there — no prior context needed.

> **Why separate sessions?** Each skill reads a lot of files. Running them all in one conversation carries every file read from `/orient` through to `/story`, bloating context unnecessarily — and on large repos, exhausting it. The snapshot is the handoff; the conversation is not.
>
> You don't have to run all of them. Run only the skills that answer your current question.

**Want to run them all automatically?** Use the included script — it fires each skill as a separate `claude` process so sessions stay isolated:

```bash
./scripts/run.sh ../my-repo                        # run all skills
./scripts/run.sh ../my-repo --skills orient,quality # subset
./scripts/run.sh ../my-repo --from map              # resume after orient
./scripts/run.sh ../my-repo --diagram               # api-trace with Mermaid
```

Run it from inside the code-archeology repo (skills are loaded from here). Requires the [Claude Code CLI](https://claude.ai/code).

**3. Read the report** printed to your conversation, and find the saved artifacts in `.archeology/` (see [What you get](#what-you-get)).

> Not using Claude Code? See [Agent compatibility](#agent-compatibility) — the same `SKILL.md` files work directly in Copilot agent, Cursor, Codex, etc.

---

## Skills

| Skill | Answers | Prereq |
|-------|---------|--------|
| `/orient` | What is this, who is it for, what does it do? | none |
| `/map` | How is it structured — layers, data flow, cross-cutting concerns? | `/orient` |
| `/api-trace` | For every API method — where does the request enter, what files does it touch, where is the decision made, what are the side effects? Produces a method inventory, per-method traces with `file:line` references, and optional Mermaid diagrams. | `/orient` (uses `/map` if present) |
| `/quality` | Is it actually well-built — structurally, intentionally, and in craft? | `/orient` |
| `/the-finder-outer` | Where is this code *pretending* to be good? Adversarial, evidence-based review of the gap between "passes checks" and "trustworthy." | `/orient` (uses `/map`, `/quality` if present) |
| `/story` | How did it evolve — origins, pivots, abandoned work? | `/orient` |

Start with `/orient` (it builds the shared snapshot everything else reads). After that, run whichever skills answer your question — they're independent.

`/quality` and `/the-finder-outer` are complementary, not redundant: `/quality` gives a balanced craft assessment and a grade; `/the-finder-outer` is the skeptical senior reviewer that hunts for locally-polished, systemically-untrustworthy code and refuses to grade — every finding stands on traced evidence.

`/api-trace` sits between `/map` and `/quality` in the workflow: `/orient` identifies the product, `/map` identifies the layers, `/api-trace` follows concrete API methods through those layers, and `/quality` + `/the-finder-outer` assess whether the resulting structure is sound and trustworthy.

---

## What you get

Each skill prints a human-readable report **and** writes structured artifacts into an `.archeology/` directory in the analyzed repo:

```
.archeology/
  report.md         # ← aggregated human-readable report — every skill's output in one file
  snapshot.json     # shared structured findings — all skills read & write this
  map.mmd           # standalone Mermaid architecture diagram (from /map)
  api-trace.md      # full per-method API traces with file:line references (from /api-trace)
  story.md          # standalone prose development narrative (from /story)
```

**`report.md` is the one to read.** Instead of scrolling the console, open it for a single document that aggregates each skill's output — the orientation, the system map (with the Mermaid diagram embedded inline), the API trace summary, the quality verdict, the finder-outer's adversarial findings, and the development story. Each skill writes its own marker-delimited section, so it fills in as you run more skills and updates cleanly on re-runs, in any order.

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
- **Single-source facts** — `/orient` records canonical repo stats (`meta.stats`) so later skills cite the same commit counts, dates, tracked-file counts, and entry-point counts instead of recomputing slightly different numbers
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

There is **one copy of each skill** — the `SKILL.md` in `.claude/skills/<name>/` — and it works across agents. The body of a `SKILL.md` is plain step-by-step markdown; the YAML frontmatter at the top (`name`, `description`, `allowed-tools`) is metadata that Claude Code and Copilot consume natively, and any other agent can simply ignore.

| Agent | How to use |
|-------|-----------|
| Claude Code | `/orient` — auto-discovered from `.claude/skills/` |
| GitHub Copilot coding agent | Reads `.claude/skills/` natively — same `SKILL.md` format (see below) |
| Cursor | Reference the file in your prompt: `@.claude/skills/orient/SKILL.md` + *"run this on [path]"* |
| Any other agent with terminal + file access | Paste the `SKILL.md` body and specify the target repo path — the frontmatter can stay or go |

Requirements for non-Claude agents: the agent must be able to run terminal commands and read/write files in the target repo. Where a skill says "the user runs `/orient`", read it as "the user asks for the orient analysis" — invocation phrasing is the only Claude-specific part.

The snapshot file is the same regardless of which agent runs the skill, so agents can **hand off between steps** — run `/orient` in one tool, `/quality` in another, against the same `.archeology/snapshot.json`.

### Using with the GitHub Copilot coding agent

Good news: **no conversion needed.** Copilot's coding agent uses the same agent-skill format as Claude Code — a directory per skill with a `SKILL.md` and `name`/`description` frontmatter — and it reads project skills from [`.claude/skills`](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills) (alongside `.github/skills` and `.agents/skills`). So copying `.claude/` into your target repo makes these skills available to Copilot too.

Two differences from Claude Code to know:

- **Invocation is contextual, not a slash command.** Copilot picks a skill from your prompt and the skill's `description` — it has no typed `/orient`. Just ask naturally: *"orient this codebase"*, *"assess the code quality"*. (The `user-invocable: true` field is Claude-specific and Copilot ignores it.)
- **Tool approval is via frontmatter, not `settings.json`.** Copilot doesn't read `.claude/settings.json`. Each `SKILL.md` instead carries an `allowed-tools` list pre-approving **read-only** commands (git read subcommands, `grep`, `find`, `wc`, etc.). We deliberately do **not** pre-approve blanket `bash`/`shell` — [the docs warn](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills) that doing so lets prompt-injection run arbitrary commands — so Copilot will still ask before anything outside that read-only set.

---

## Schema & validation

The snapshot contract lives at [`schema/snapshot.schema.json`](schema/snapshot.schema.json) — a JSON Schema defining the shared artifact all skills read from and write to. If you're building tooling on top of the output, validate against this.

The contract is **enforced, not just documented**: [`.claude/skills/validate.py`](.claude/skills/validate.py) checks a snapshot against the schema and lints `report.md` marker structure (balanced markers, canonical section order, no duplicates). It travels with `cp -r .claude`, uses the `jsonschema` package when installed, and falls back to built-in structural checks when not.

```bash
python3 .claude/skills/validate.py <target-repo>     # validate snapshot + report
python3 .claude/skills/validate.py --self-test        # verify the validator itself
```

`scripts/run.sh` runs it automatically after every skill and fails loudly on violations — a deterministic check outside the agent's discretion, which is the point: skills are asked to follow the contract, but the runner verifies it.
