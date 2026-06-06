# code-archeology

A collection of Claude Code skills for understanding large, unfamiliar codebases — including AI-generated ones. The goal is clarity in both technical and human terms: not just *what the code does*, but *what the product is*, *who it's for*, and *whether it's actually well-built*.

## Skills

| Skill | Purpose | Prereqs |
|-------|---------|---------|
| `/orient` | Plain-English product orientation — what is this, who is it for, what does it do | none |
| `/map` | Logical architecture map — layers, data flow, cross-cutting concerns, Mermaid diagram | `/orient` |
| `/quality` | Craft assessment — structural, intentional, and human-verdict quality | `/orient` |
| `/story` | Development narrative — how the codebase evolved, pivots, fossils | `/orient` |

Run them in order for a full picture, or run any individually for a focused view.

## How it works

Each skill writes its findings to `.archeology/snapshot.json` in the analyzed repo. This shared artifact means:

- Skills don't re-read what previous skills already processed
- Analysis is resumable if interrupted (large codebases can exhaust context)
- Later skills have domain context from earlier ones — calling something a bad abstraction means more when you already know the domain vocabulary

The `.archeology/` directory is local to the analyzed repo and should be added to that repo's `.gitignore`.

## Designed for large codebases

These skills are built with strict context discipline:
- Breadth-first, not exhaustive — reads the boundary layer before diving into implementation
- Progressive snapshot writes — findings are persisted incrementally, not just at the end
- Coverage tracking — the snapshot records what's been read and what's queued, enabling clean resumption
- File-size limits — no skill reads a complete large file when the first 80 lines will do

## Stack support

Optimized for the modern polyglot stack:
- **TypeScript / JavaScript** — framework detection, type quality, `any` analysis
- **Python** — async patterns, type annotation coverage, module structure
- **Docker / Compose** — service architecture, build quality, security signals
- HTML and static assets as signal sources for domain and audience

## Agent compatibility

The `.claude/skills/` versions are Claude Code-native — auto-discovered and invoked via `/orient` etc.

The `prompts/` directory contains identical content packaged for **any agent with terminal + file access**:

| Agent | How to use |
|-------|-----------|
| Claude Code | `/orient` — auto-invoked from `.claude/skills/` |
| GitHub Copilot agent | `@workspace prompts/orient.md` → "run this on [path]" |
| Cursor | Reference `prompts/orient.md` in your prompt |
| Any other agent | Paste the prompt content directly |

The snapshot file (`.archeology/snapshot.json`) is the same regardless of which agent runs the skill — two agents can hand off between steps.

## Schema

The snapshot schema lives at [`schema/snapshot.schema.json`](schema/snapshot.schema.json). It defines the shared artifact all skills read from and write to.
