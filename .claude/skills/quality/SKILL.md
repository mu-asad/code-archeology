---
name: quality
description: Assess whether a codebase is actually well-built — not just whether it works. Produces structural, intentional, and craft-quality signals plus a human-readable verdict and grade, with attention to AI-generation patterns. Use when the user asks how good, well-built, or trustworthy a codebase is, or runs /quality. Requires /orient first; reads and writes .archeology/snapshot.json.
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
  - Bash(git shortlog *)
  - Bash(git rev-list *)
  - Bash(git status *)
---

# quality

Assess the craft and quality of a codebase. Not just "does it work" — **is it well-built?** This skill produces three distinct signals: structural quality (measurable), intentional quality (does it do what it claims?), and craft quality (the human verdict).

**Prerequisite**: Run `/orient` first. This skill reads from the existing snapshot for domain context — calling something a bad abstraction means more when you know what the domain vocabulary should be.

---

## How to invoke

```
/quality [path-to-repo]
```

If no path is given, use the current working directory.

**Resolve the target root first.** If a path *is* given — or the repo lives somewhere other than your cwd (e.g. you launched from the code-archeology repo and passed the target via `--add-dir`) — treat that path as the target root and `cd` into it before running any steps, so every command (including bare `git`) operates on that repo. Every step below assumes commands run **inside the target repo**; don't analyze your current directory by accident.

---

## Step 0 — Load snapshot

Load `.archeology/snapshot.json`. If it doesn't exist, tell the user to run `/orient` first.

Check `snapshot.product.summary` and `snapshot.structure` — you need these for context throughout this skill. A God object is only a problem if the domain doesn't justify it.

If `quality` is already in `meta.skills_run`, report existing findings and ask if the user wants to re-run.

**Write snapshot after every major step.**

---

## Step 1 — Structural quality

### 1a. Complexity hotspots

Find the largest, most complex files. Don't read them yet — identify them first.

```bash
# Use git's own tracked-file list — it respects .gitignore, so vendored and
# generated files (node_modules, dist, .venv, build, etc.) are already excluded.
# `IFS= read -r` keeps it correct for paths containing spaces.
git ls-files '*.ts' '*.tsx' '*.py' \
  | while IFS= read -r f; do wc -l "$f"; done \
  | sort -rn | head -20
```

For the top 5 largest files: read the first 80 lines and skim the structure. Are they large because the domain demands it, or because no one bothered to decompose them?

Record in `snapshot.quality.structural.complexity_hotspots` with a reason for each.

### 1b. Test coverage assessment

Check if tests exist and whether they cover the right things:

- Look for `__tests__/`, `tests/`, `*.test.ts`, `*.spec.ts`, `test_*.py`
- Check `jest.config.*`, `pytest.ini`, `vitest.config.*` for test setup
- Spot-check: does the complexity hotspot you found in 1a have tests?
- Look for the ratio of test files to source files — a rough proxy

**Key question**: Are the complex/risky parts tested, or only the easy parts?

Write a narrative assessment to `snapshot.quality.structural.test_coverage_assessment`.

### 1c. Dead code indicators

Signs that code exists but isn't used:

- Exported functions/classes with no imports found via grep
- TODO/FIXME comments that are old or aspirational
- Feature flags that are permanently `false`
- Commented-out code blocks
- Files in `old/`, `_backup/`, `deprecated/`
- Packages in `package.json` / `requirements.txt` not imported anywhere

Don't exhaustively grep everything — spot-check 3–5 suspicious areas based on what you've seen.

Record in `snapshot.quality.structural.dead_code_indicators`.

### 1d. Duplication areas

Look for:
- Utility functions copy-pasted across modules (date formatting, API calls, validation patterns)
- Similar route handlers with nearly identical logic
- Python and TypeScript versions of the same logic (cross-language duplication)

Record in `snapshot.quality.structural.duplication_areas`.

---

## Step 2 — Intentional quality

**This is the most important section.** AI-generated code often *looks* correct but has subtle gaps between what it claims to do and what it actually does.

### 2a. Silent failure patterns

Read 3–5 error handling sections. Look for:

**TypeScript/JavaScript:**
- `try { ... } catch (e) { }` — swallowed errors
- `.catch(console.log)` — logged but not handled
- Promises not awaited in fire-and-forget patterns that should not be
- Optional chaining (`?.`) masking null states that should be validated

**Python:**
- `except Exception: pass`
- `except Exception as e: print(e)` in production paths
- `try/except` around code that can't actually fail (false safety theater)

Record in `snapshot.quality.intentional.silent_failures`.

### 2b. Fake validation

Code that looks like it validates but doesn't actually guard anything:

- Validation that always passes (checking the wrong field, wrong condition)
- Schema validation on input that was already processed upstream
- Type assertions (`as SomeType`, Python `cast()`) used to bypass actual checks
- Auth middleware that's present but not applied to sensitive routes

To find these: look at the validation layer identified in `/orient`'s domain model, then read 2–3 validators and trace whether their results are actually used.

Record in `snapshot.quality.intentional.fake_validation`.

### 2c. Mismatched abstractions

Where the abstraction layer doesn't match the actual complexity:

- A "service" that's just a thin wrapper with no logic (over-abstracted)
- Business logic living in a route handler or model (under-abstracted)
- A complex generic/utility that's only used once
- Config objects with 20 fields when 3 are ever set

Record in `snapshot.quality.intentional.mismatched_abstractions`.

---

## Step 3 — Craft quality

This is the qualitative, human verdict. You've now seen enough of the codebase to form an opinion.

### 3a. AI generation signals

Look for patterns common in AI-generated code (not inherently bad — just worth noting):

- Suspiciously uniform docstring style across files
- Every function has a comment; no function is self-explanatory
- Overly verbose variable names (`userAuthenticationToken` vs `token`)
- Boilerplate-heavy setup with thin actual logic
- Inconsistencies that suggest different "sessions" of generation (naming conventions shift mid-codebase, two approaches to the same problem coexist)
- Generic error messages that don't help with debugging
- Test files that test the happy path only, in a very regular pattern

Record patterns found in `snapshot.quality.craft.ai_generation_signals`.

### 3b. Language-specific craft tells

**TypeScript:**
- `any` count: run `grep -r ": any" src/ --include="*.ts" | wc -l` — anything over 10–15 in a typed codebase is a smell
- `@ts-ignore` usage
- Interfaces vs types used correctly, or mixed randomly
- Generics: used to solve actual problems, or cargo-culted?

**Python:**
- Type annotations: present? consistent? or only on some functions?
- `async/await` used correctly vs mixed sync/async antipatterns
- Module structure: flat scripts or proper packages?
- `if __name__ == "__main__"` in files that aren't entry points (suggests copy-paste from tutorials)

**Docker:**
- `latest` tags on base images (non-reproducible builds)
- Secrets or credentials in `ENV` or `ARG` statements
- Single-stage builds when multi-stage would dramatically reduce image size
- Running as root unnecessarily

### 3c. Write the craft narrative

Write a 2–4 paragraph narrative that answers:
1. What is the overall "personality" of this codebase? (Cautious? Hasty? Over-engineered? Pragmatic?)
2. Where does the craft break down most noticeably?
3. What does this codebase's quality say about the team/process that produced it?
4. If you had to take it to production, what's the first thing you'd fix?

Do not write bullet points for this section. Write prose. This is the human verdict.

Record in `snapshot.quality.craft.narrative`.

---

## Step 4 — Overall grade

Assign a grade using this rubric:

| Grade | Meaning |
|-------|---------|
| A | Production-ready craft. Abstractions are honest, errors are handled, tests cover risk, code communicates intent. |
| B | Solid but imperfect. A few rough areas but fundamentally trustworthy. Ships to production with minor cleanup. |
| C | Working but concerning. Significant gaps in error handling or testing. Requires real work before production. |
| D | Functional in the happy path, brittle everywhere else. Significant rework needed. |
| F | The tests pass but don't trust it. Fundamental quality problems throughout. |

Set `snapshot.quality.overall_grade`. Write snapshot.

---

## Step 5 — Output

Print the quality report in this format:

```
## Quality Assessment: [overall_grade]

### The verdict
[craft narrative — your human prose assessment]

### Where it breaks down

**Structural issues**
[complexity hotspots, dead code, duplication — bullet list, 3-5 items max]

**Intentional gaps**  
[silent failures, fake validation, mismatched abstractions — bullet list, 3-5 items]

**Language-specific signals**
[TypeScript: X `any`s, Y `@ts-ignore`s | Python: [findings] | Docker: [findings]]

**AI generation signals** (if present)
[bullet list of patterns observed]

### Strengths
[what's actually done well — be honest, there's usually something]

### If I had to fix one thing first
[single most impactful improvement, in plain English]
```

---

## Step 6 — Append to the aggregated report

Besides printing to the console, write the **same** content into the shared `.archeology/report.md` so the user can read every skill's output in one place.

- If `.archeology/report.md` does not exist yet, create it with this header first:
  ```markdown
  # Code Archeology Report — <repo name>

  _Generated by [code-archeology](https://github.com/mu-asad/code-archeology) · last updated <UTC timestamp>_
  ```
- Insert or replace your marker-delimited section. Keep section order `orient`, `map`, `api-trace`, `quality`, `the-finder-outer`, `story`:
  ```markdown
  <!-- section:quality -->
  <the same content you printed to the console, verbatim (including the craft narrative in full) — it already begins with `## Quality Assessment: [overall_grade]`, so do not add another heading>
  <!-- /section:quality -->
  ```
- Update the `last updated` timestamp in the header.

Then write the snapshot one final time with `quality` added to `meta.skills_run`.

---

## Context budget rules

- **Never read entire files for this skill.** Read the first 80 lines to understand structure, then grep for specific patterns.
- **Prefer grep over reading.** Most signals in this skill can be found with targeted searches.
- **Write snapshot frequently.** Each sub-step should trigger a snapshot write.
- **Stop after 3–5 examples of any pattern.** You don't need to catalog every `catch (e) {}` — 3 examples prove the point. Record "pattern found in X+ places" rather than listing all of them.
- **Skip vendored/generated code**: `node_modules/`, `.venv/`, `dist/`, `build/`, `generated/`, `*.pb.ts`, `*.generated.ts`

---

## Failure modes to avoid

- **Score inflation**: Be honest. "Working shit is still shit." A C is not an insult — it's useful information.
- **Nitpick spiral**: Don't spend 10 paragraphs on naming conventions. The grade should reflect what would actually matter in production.
- **Missing the forest**: If the whole validation layer is fake, that's an F-level finding. Don't bury it in a list of minor issues.
- **Punishing AI generation**: AI-generated code can be good code. Flag AI patterns as signals to verify, not automatic demerits.
