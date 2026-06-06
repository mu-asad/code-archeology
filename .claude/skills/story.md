# story

Tell the story of how this codebase evolved. What was built first? Where did the pivots happen? What was abandoned? Git history is an archaeological record — this skill reads it like one.

Works best on codebases with meaningful commit history. On AI-generated repos with single-commit history, it falls back to inferring the story from code structure and naming patterns.

---

## How to invoke

```
/story [path-to-repo]
```

If no path is given, use the current working directory.

---

## Step 0 — Load snapshot

Load `.archeology/snapshot.json`. If it doesn't exist, run `/orient` first.

`/story` works without `/map` or `/quality` but benefits from both — domain context makes the narrative richer.

**Write snapshot after every major step.**

---

## Step 1 — Read the git record

Run these commands to understand the history shape:

```bash
# Overall timeline
git log --oneline --all | wc -l              # total commits
git log --format="%ad" --date=short | tail -1  # first commit
git log --format="%ad" --date=short | head -1  # most recent commit

# Contributor shape
git shortlog -sn --all | head -10

# Commit velocity (activity by month)
git log --format="%ad" --date=format:"%Y-%m" | sort | uniq -c

# Files with most change history (churn)
git log --name-only --format="" | grep -v "^$" | sort | uniq -c | sort -rn | head -15

# Largest single commits (potential pivots or bulk-generation)
git log --oneline --shortstat | grep -E "files? changed" | \
  awk '{print $1, $4, $7}' | sort -k2 -rn | head -10
```

From this, identify:
- **Timeline span**: days, months, years?
- **Contributor count**: solo? small team? large org?
- **Velocity pattern**: steady, burst-then-quiet, or single big dump?
- **Churn hotspots**: files edited most — these are either the core of the product or the biggest source of problems

---

## Step 2 — Read commit messages

```bash
git log --oneline -50
```

Read the last 50 commit messages. Look for:
- **Pivots**: messages like "rewrite", "switch to", "replace X with Y", "remove", "migrate"
- **Struggle signals**: messages like "fix", "fix fix", "actually fix", "working now", "debug", "temp", "hack", "wip"
- **Feature arcs**: a sequence of commits around a single feature reveals what the author considered hard
- **AI generation signals**: messages like "initial commit" with a massive changeset, extremely uniform message style, no typos ever, overly descriptive commit messages

If there are >100 commits, read the first 10, last 10, and skim the middle for pivot-shaped messages.

---

## Step 3 — Read the founding commit(s)

Find the earliest commits and inspect what was in them:

```bash
# List the first 5 commits chronologically
git log --oneline --reverse --max-count=5

# Inspect the root commit's file manifest
git show --stat $(git rev-list --max-parents=0 HEAD)

# Diff of what the first commit introduced
git show $(git rev-list --max-parents=0 HEAD)
```

**What to look for:**
- Was this bootstrapped from a template/boilerplate, or built from scratch?
- What did the author consider important enough to build first?
- Is the initial structure similar to today's, or has it changed fundamentally?

---

## Step 4 — Identify the pivots

A pivot is a point in history where the direction noticeably changed. Evidence:
- Large deletions followed by additions in similar areas
- Dependency changes (new framework added, old one removed)
- Directory renames or restructures
- Long gaps in commit history followed by a burst

For each identified pivot, read the commit(s) and write a one-sentence description:
> "Around [date], the project switched from [X] to [Y], likely because [inference]."

---

## Step 5 — Infer what was abandoned

Look for:
- Directories that exist but have no recent commits (`git log --after="[6 months ago]" -- path/`)
- Files with TODO/FIXME comments that reference features never completed
- Branches that were never merged (`git branch -a | grep -v HEAD`)
- Packages in dependencies that aren't imported anywhere (found in `/quality`)

These are the fossils — they tell you what the author intended to build but didn't finish.

---

## Step 6 — Single-commit fallback

If the repo has 1–3 commits (common for AI-generated codebases), git history is thin. Fall back to structural archaeology:

- **Naming patterns**: inconsistent naming conventions suggest different "eras" of generation
- **Import patterns**: some modules import others in ways that suggest build order
- **Comment dates** or version strings in code
- **Complexity distribution**: the most complex, most polished areas are usually "first built"
- **Dead code**: unfinished features are often more raw than completed ones

Note in the output that the history is sparse and you're inferring from structure.

---

## Step 7 — Write the narrative

Write the codebase story as **prose**, not bullet points. 3–5 paragraphs. Think of it as the opening section of an engineering post-mortem or a "how we got here" section of a tech spec.

Structure:
1. **Origins**: what this started as, when, by whom
2. **The main arc**: what was built and in what order
3. **The pivots** (if any): what changed and why
4. **The fossils**: what was tried and abandoned
5. **Where it is now**: what the current state reflects about the project's trajectory

If the history is AI-generated or synthetic, say so plainly. The story is still useful.

Save the narrative to `.archeology/story.md`. Record key timeline events in a `timeline` array in the snapshot under a top-level `story` key.

---

## Step 8 — Output

```
## The Story

[prose narrative — 3-5 paragraphs]

### Timeline
[key events as a chronological bullet list with dates]

### Hottest files (most churned)
[top 5 files by change frequency with one-line note on why this might be]

### Fossils (abandoned work)
[bullet list of incomplete/abandoned areas]

### What the history says about quality
[1-2 sentences connecting the development story to the quality picture]
```

---

## Context budget rules

- **Git commands are cheap — use them freely.** You're reading metadata, not file contents.
- **Only read file contents for Step 3 (founding commits) and specific pivots.** Everything else is metadata.
- **Don't read more than 5 actual source files in this skill.** The story lives in git, not the code.
- Write snapshot after Steps 1, 4, and 7.
