# Prompt: Quality

> **Agent-agnostic version.** Works with any agent that has terminal access and can read/write files — Claude Code, GitHub Copilot agent, Codex, Cursor, etc.
>
> **How to use:**
> - *Claude Code:* use `.claude/skills/quality/SKILL.md` — invoked automatically via `/quality`
> - *Copilot agent / Cursor:* paste this prompt or reference it with `@workspace prompts/quality.md`, then say "run the quality analysis on [path]"
> - *Any other agent:* paste the prompt content directly and specify the target repo path
>
> **Requirements:** agent must be able to run terminal/bash commands and read/write files.
> **Prerequisite:** run the `orient` prompt first. This prompt reads domain context from the snapshot.

---

Assess the craft and quality of a codebase. Not just "does it work" — **is it well-built?** Three distinct signals: structural quality (measurable), intentional quality (does it do what it claims?), and craft quality (the human verdict).

**Target repo:** [specify path, or assume current working directory]

---

## Step 0 — Load snapshot

Load `.archeology/snapshot.json`. If it doesn't exist, run the `orient` prompt first.

Check `snapshot.product.summary` and `snapshot.structure` for domain context — a God object is only a problem if the domain doesn't justify it.

**Write snapshot after every major step.**

---

## Step 1 — Structural quality

### 1a. Complexity hotspots

Find the largest files without reading them first:

```bash
find . -name "*.ts" -o -name "*.tsx" -o -name "*.py" | \
  grep -v node_modules | grep -v .venv | grep -v dist | \
  xargs wc -l 2>/dev/null | sort -rn | head -20
```

For the top 5: read first 80 lines and skim structure. Large because domain demands it, or because no one decomposed it?

Record in `snapshot.quality.structural.complexity_hotspots`.

### 1b. Test coverage assessment

- Look for `__tests__/`, `tests/`, `*.test.ts`, `*.spec.ts`, `test_*.py`
- Check `jest.config.*`, `pytest.ini`, `vitest.config.*`
- Does the complexity hotspot found in 1a have tests?
- Ratio of test files to source files — a rough proxy

**Key question:** Are the complex/risky parts tested, or only the easy parts?

Write a narrative assessment to `snapshot.quality.structural.test_coverage_assessment`.

### 1c. Dead code indicators

- Exported functions/classes with no imports (spot-check via grep)
- TODO/FIXME comments that are aspirational rather than tracked
- Feature flags permanently set to `false`
- Commented-out code blocks
- Files in `old/`, `_backup/`, `deprecated/`
- Packages in `package.json`/`requirements.txt` not imported anywhere

Spot-check 3–5 suspicious areas, don't exhaustively grep everything.

Record in `snapshot.quality.structural.dead_code_indicators`.

### 1d. Duplication areas

- Utility functions copy-pasted across modules
- Similar route handlers with near-identical logic
- Same logic in both Python and TypeScript (cross-language duplication)

Record in `snapshot.quality.structural.duplication_areas`.

---

## Step 2 — Intentional quality

**Most important section.** AI-generated code often *looks* correct but has subtle gaps between what it claims to do and what it actually does.

### 2a. Silent failure patterns

Read 3–5 error handling sections. Look for:

**TypeScript/JavaScript:**
- `try { ... } catch (e) { }` — swallowed errors
- `.catch(console.log)` — logged but not handled
- Unawaited promises in paths that should be synchronous
- Optional chaining (`?.`) masking null states that should be validated

**Python:**
- `except Exception: pass`
- `except Exception as e: print(e)` in production paths
- `try/except` around code that cannot actually fail (false safety theater)

Record in `snapshot.quality.intentional.silent_failures`.

### 2b. Fake validation

Code that looks like it validates but doesn't actually guard anything:

- Validation that always passes (wrong field, wrong condition)
- Schema validation on input already processed upstream
- Type assertions (`as SomeType`, Python `cast()`) used to bypass actual checks
- Auth middleware present but not applied to sensitive routes

Trace 2–3 validators: is the result actually used downstream?

Record in `snapshot.quality.intentional.fake_validation`.

### 2c. Mismatched abstractions

- "Service" that's just a thin wrapper with no logic (over-abstracted)
- Business logic in a route handler or model (under-abstracted)
- Complex generic/utility used only once
- Config objects with 20 fields when 3 are ever set

Record in `snapshot.quality.intentional.mismatched_abstractions`.

---

## Step 3 — Craft quality

### 3a. AI generation signals

Patterns common in AI-generated code (not inherently bad — worth noting):

- Uniform docstring style across all files
- Every function has a comment; no function is self-explanatory
- Overly verbose variable names everywhere
- Boilerplate-heavy setup, thin actual logic
- Naming conventions shift mid-codebase (suggests different generation sessions)
- Generic error messages unhelpful for debugging
- Tests covering only the happy path in a very regular pattern

Record in `snapshot.quality.craft.ai_generation_signals`.

### 3b. Language-specific craft tells

**TypeScript:**
```bash
grep -r ": any" src/ --include="*.ts" | wc -l   # >10-15 is a smell
grep -r "@ts-ignore" src/ --include="*.ts" | wc -l
```
- Interfaces vs types: used correctly or mixed randomly?
- Generics: solving actual problems, or cargo-culted?

**Python:**
- Type annotations: present? consistent? or only on some functions?
- `async/await` used correctly vs mixed sync/async antipatterns
- `if __name__ == "__main__"` in files that aren't entry points (tutorial copy-paste)

**Docker:**
- `latest` tags on base images (non-reproducible builds)
- Secrets or credentials in `ENV` or `ARG`
- Single-stage build where multi-stage would reduce image size significantly
- Running as root unnecessarily

### 3c. Craft narrative

Write a 2–4 paragraph prose narrative:
1. What is the overall "personality" of this codebase? (Cautious? Hasty? Over-engineered? Pragmatic?)
2. Where does the craft break down most noticeably?
3. What does this codebase's quality say about the process that produced it?
4. If you had to take it to production, what's the first thing you'd fix?

**Write prose, not bullet points.** This is the human verdict.

Record in `snapshot.quality.craft.narrative`.

---

## Step 4 — Overall grade

| Grade | Meaning |
|-------|---------|
| A | Production-ready craft. Abstractions honest, errors handled, tests cover risk. |
| B | Solid but imperfect. Ships to production with minor cleanup. |
| C | Working but concerning. Requires real work before production. |
| D | Functional in the happy path, brittle everywhere else. |
| F | Tests pass but don't trust it. Fundamental quality problems throughout. |

Set `snapshot.quality.overall_grade`. Write snapshot.

---

## Step 5 — Output

```
## Quality Assessment: [grade]

### The verdict
[craft narrative — prose]

### Where it breaks down

**Structural issues**
[3-5 bullet points max]

**Intentional gaps**
[3-5 bullet points max]

**Language-specific signals**
[TypeScript: X `any`s, Y `@ts-ignore`s | Python: findings | Docker: findings]

**AI generation signals** (if present)
[bullet list]

### Strengths
[what's actually done well]

### If I had to fix one thing first
[single most impactful improvement, plain English]
```

---

## Context budget rules

- **Never read entire files.** Read first 80 lines to understand structure, then grep for specific patterns.
- **Prefer grep over reading.** Most signals are findable with targeted searches.
- **Write snapshot after each sub-step.**
- **Stop at 3–5 examples of any pattern.** Record "pattern found in X+ places" rather than cataloguing every instance.
- **Skip:** `node_modules/`, `.venv/`, `dist/`, `build/`, `generated/`, `*.pb.ts`, `*.generated.ts`

---

## Failure modes to avoid

- **Score inflation:** Be honest. A C is useful information, not an insult.
- **Nitpick spiral:** Don't spend paragraphs on naming conventions. Grade on what matters in production.
- **Missing the forest:** If the entire validation layer is fake, that's an F-level finding. Don't bury it.
- **Punishing AI generation:** AI-generated code can be good. Flag patterns as signals to verify, not automatic demerits.
