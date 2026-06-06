# Prompt: Story

> **Agent-agnostic version.** Works with any agent that has terminal access and can read/write files — Claude Code, GitHub Copilot agent, Codex, Cursor, etc.
>
> **How to use:**
> - *Claude Code:* use `.claude/skills/story.md` — invoked automatically via `/story`
> - *Copilot agent / Cursor:* paste this prompt or reference it with `@workspace prompts/story.md`, then say "run the story analysis on [path]"
> - *Any other agent:* paste the prompt content directly and specify the target repo path
>
> **Requirements:** agent must be able to run terminal/bash commands and read/write files. Git must be available.
> **Prerequisite:** run the `orient` prompt first. Works without `map` or `quality` but benefits from both.

---

Tell the story of how this codebase evolved. What was built first? Where did the pivots happen? What was abandoned? Git history is an archaeological record — read it like one.

Works best on repos with meaningful commit history. On AI-generated repos with single-commit history, falls back to inferring the story from code structure and naming patterns.

**Target repo:** [specify path, or assume current working directory]

---

## Step 0 — Load snapshot

Load `.archeology/snapshot.json`. If it doesn't exist, run the `orient` prompt first.

**Write snapshot after every major step.**

---

## Step 1 — Read the git record

Run these to understand the history shape:

```bash
# Overall timeline
git log --oneline --all | wc -l
git log --format="%ad" --date=short | tail -1   # first commit date
git log --format="%ad" --date=short | head -1   # most recent commit date

# Contributor shape
git shortlog -sn --all | head -10

# Commit velocity by month
git log --format="%ad" --date=format:"%Y-%m" | sort | uniq -c

# Files with most change history (churn)
git log --name-only --format="" | grep -v "^$" | sort | uniq -c | sort -rn | head -15

# Largest single commits (potential pivots or bulk AI generation)
git log --oneline --shortstat | grep -E "files? changed" | \
  awk '{print $1, $4, $7}' | sort -k2 -rn | head -10
```

Identify:
- **Timeline span**: days, months, years?
- **Contributor count**: solo, small team, large org?
- **Velocity pattern**: steady, burst-then-quiet, or single dump?
- **Churn hotspots**: files edited most — core of the product or biggest source of problems?

---

## Step 2 — Read commit messages

```bash
git log --oneline -50
```

Look for:
- **Pivots**: "rewrite", "switch to", "replace X with Y", "remove", "migrate"
- **Struggle signals**: "fix fix", "actually fix", "working now", "debug", "temp", "hack", "wip"
- **Feature arcs**: sequence of commits around one feature reveals what the author found hard
- **AI generation signals**: single massive "initial commit", uniform message style, no typos, overly descriptive messages

If >100 commits: read first 10, last 10, skim middle for pivot-shaped messages.

---

## Step 3 — Read the founding commit(s)

```bash
# List the first 5 commits chronologically
git log --oneline --reverse --max-count=5

# Inspect the root commit's file manifest
git show --stat $(git rev-list --max-parents=0 HEAD)

# Diff of what the first commit introduced
git show $(git rev-list --max-parents=0 HEAD)
```

What to look for:
- Bootstrapped from a template/boilerplate, or built from scratch?
- What did the author consider important enough to build first?
- Is the initial structure similar to today's, or fundamentally changed?

---

## Step 4 — Identify the pivots

Evidence of a pivot:
- Large deletions followed by additions in similar areas
- Dependency changes (new framework added, old one removed)
- Directory renames or restructures
- Long gaps in commit history followed by a burst

For each pivot, write one sentence:
> "Around [date], the project switched from [X] to [Y], likely because [inference]."

---

## Step 5 — Infer what was abandoned

```bash
# Directories with no recent activity
git log --after="6 months ago" --name-only --format="" | sort -u > /tmp/recent_files.txt
# then compare against find . -type f

# Unmerged branches
git branch -a | grep -v HEAD
```

Also look for:
- TODO/FIXME comments referencing unfinished features
- Packages in dependencies not imported anywhere
- Files in `old/`, `_backup/`, `deprecated/`

---

## Step 6 — Single-commit fallback

If the repo has 1–3 commits (common for AI-generated codebases), fall back to structural archaeology:

- **Naming patterns**: inconsistent conventions suggest different generation sessions
- **Import patterns**: some modules import others in ways that suggest build order
- **Comment dates** or version strings in code
- **Complexity distribution**: most complex, most polished areas were usually built first
- **Dead code**: unfinished features are typically more raw than completed ones

Note in the output that history is sparse and you're inferring from structure.

---

## Step 7 — Write the narrative

Write the codebase story as **prose**, not bullet points. 3–5 paragraphs:

1. **Origins**: what this started as, when, by whom
2. **The main arc**: what was built and in what order
3. **The pivots** (if any): what changed and why
4. **The fossils**: what was tried and abandoned
5. **Where it is now**: what the current state reflects about the project's trajectory

If history is AI-generated or synthetic, say so plainly. The story is still useful.

Save narrative to `.archeology/story.md`. Record key timeline events in `snapshot.story.timeline`. Write snapshot.

---

## Step 8 — Output

```
## The Story

[prose narrative — 3-5 paragraphs]

### Timeline
[key events as chronological bullet list with dates]

### Hottest files (most churned)
[top 5 by change frequency + one-line note on why]

### Fossils (abandoned work)
[bullet list of incomplete/abandoned areas]

### What the history says about quality
[1-2 sentences connecting the development story to the quality picture]
```

---

## Context budget rules

- **Git commands are cheap — use them freely.** Reading metadata, not file contents.
- **Only read file contents for Step 3 and specific pivots.** Everything else is metadata.
- **Don't read more than 5 actual source files.** The story lives in git, not the code.
- Write snapshot after Steps 1, 4, and 7.
