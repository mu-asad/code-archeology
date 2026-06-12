# Prompt: The Finder Outer

> **Agent-agnostic version.** Works with any agent that has terminal access and can read/write files — Claude Code, GitHub Copilot agent, Codex, Cursor, etc.
>
> **How to use:**
> - *Claude Code:* use `.claude/skills/the-finder-outer/SKILL.md` — invoked automatically via `/the-finder-outer`
> - *Copilot agent / Cursor:* paste this prompt or reference it with `@workspace prompts/the-finder-outer.md`, then say "run the finder-outer on [path]"
> - *Any other agent:* paste the prompt content directly and specify the target repo path
>
> **Requirements:** agent must be able to run terminal/bash commands and read/write files.
> **Prerequisite:** run the `orient` prompt first. Reuses `map` layers and `quality` hotspots if present.

---

Adversarial code review. Where `quality` asks *"is this codebase well-built?"* and grades it, this is sharper and more hostile in a useful way: **"where is this code pretending to be good?"**

Find the gap between *passes checks* and *I'd trust this in production* — code that satisfies linters, tests, type checkers, and a quick skim while being over-abstracted, quietly fragile, or fake-good. **Funny name, serious output.** Don't dunk on code for sport; find the specific places where trust leaks out, and prove each with evidence.

**The goal is to find what is hard to find.** Surface snark (a long variable name) is not the point. The signature move is to **trace actual behavior** and **pair tests with the source they claim to cover.**

**Target repo:** [specify path, or assume current working directory]

> **Resolve the target root first.** If a path is given — or you launched the agent from a different directory — `cd` into the target repo before running any steps, so every command operates on that repo. Every step below assumes commands run **inside the target repo**.

---

> **Start this skill in a fresh conversation.** Load the snapshot, do the work, end the session. The snapshot has everything prior skills found — there is no need to carry their context forward. Chaining skills in one conversation bloats context; on large repos it will exhaust it.

## Step 0 — Load context

Load `.archeology/snapshot.json`. If it doesn't exist, run the `orient` prompt first.

When citing repo-wide aggregate facts (commit counts, date span, tracked files, entry point counts), use `snapshot.meta.stats` from `orient`. Before citing a value, confirm the specific needed field is present and non-null. Do not recompute or publish alternate counts. If `meta.stats` is missing, or any needed field is absent/null, treat stats as unavailable and recommend re-running `orient` rather than guessing.

Pull in whatever prior analysis exists:
- `snapshot.quality.structural.complexity_hotspots` — pre-identified large/complex files
- `snapshot.quality.intentional` — silent failures / fake validation already flagged (confirm or deepen)
- `snapshot.structure.layers` — logical layers (from `map`)
- `snapshot.product.summary` + `snapshot.structure.domain_model` — so you can tell *generic* names from *honest domain* names

**Write the snapshot after every major step.**

---

## Step 1 — Pick 5–10 suspects (cheap scan)

Do **not** analyze the whole repo. Identify a short suspect list cheaply, then spend your budget tracing in Step 2.

Sources, in priority order:
1. **`quality` hotspots** (if present) — start here.
2. **Largest files** — `git ls-files '*.ts' '*.tsx' '*.py' | while IFS= read -r f; do wc -l "$f"; done | sort -rn | head`.
3. **Deep abstraction layers** — files/dirs named `strategy`, `factory`, `provider`, `manager`, `abstract`, `base`, `*Interface`, `handler`.
4. **Broad tests** — largest test files, and tests with the most mock setup (`grep -Erl "mock|Mock|patch|stub"` in the test dir).
5. **Repeated module shapes** — directories whose subfolders share an identical file layout (AI-uniformity signal).

Pick **5–10 suspects total** across a few categories. Record them. Write snapshot.

---

## Step 2 — Trace, don't guess (the core)

For each suspect, **actually read it** and **trace what it does** — don't pattern-match from the filename. Every finding must carry **concrete evidence**.

**For a suspect abstraction** — answer with evidence:
1. What complexity is this buying down? (Can't name it → that's the finding.)
2. How many real implementations / callers? (`grep -rn` the name. One impl behind an interface is a red flag.)
3. Would deleting it make the code easier to understand?
4. Does it preserve domain language, or hide it behind generic names?
5. Is it honest about failure, state, and side effects? (Does `get*` mutate? Does a "pure" transform hit the network?)

**For a suspect test** — read it *with* the source it covers:
- Asserts **behavior**, or just that a **mock was called**?
- A **snapshot/golden** test locking in whatever output, bugs included?
- Covers the **risky** path, or only the happy path while dangerous code is untested?
- Does setup **replace the system under test** so it passes regardless of real logic?

**For a suspect function / transform** — trace input → output vs what the name/docstring claims:
- Silently **drops fields** a caller expects to survive?
- **Defensive checks that can't trigger** given real call sites?
- **Swallows partial failures** (partial result / error counter with no idea what was lost)?
- **Retry without idempotency**, or **"temporary" code on a critical path**?

For each finding record: **path (+line)**, **smell**, **evidence** (what you traced, caller count, behavior), and label **`confirmed`** (traced) or **`suspicious`** (worth a look, unproven). Never present `suspicious` as `confirmed`. Write snapshot.

---

## Step 3 — Rank by risk, not aesthetics

Order by **risk to trust/production** ≈ *(how likely it bites)* × *(blast radius)*.

- A mapper that silently drops a field on a payment object outranks a `UserDataProcessingManager` name.
- **Suppress pure-aesthetic complaints.** A verbose name, tutorial comment, or boilerplate is **not a finding** unless it *hides behavior*. "Looks AI-generated" belongs in the AI-signals caveat, not the risk list.

---

## Step 4 — Recommend: delete or simplify first, safety-gated

Default to **"delete or simplify"** over "rewrite." But gate every deletion on blast radius — only recommend removing something when you've **verified it's safe** (few/no callers, traced, nothing load-bearing hidden inside). If you can't verify, say so: *"load-bearing or unclear — flag, don't delete yet."* Hold yourself to the standard you're enforcing.

---

## Step 5 — Output

Print the report (no grade):

```
## The Finder Outer

### Verdict
[2-4 paragraphs: where this code is fake-good, over-complex, or quietly fragile — and, fairly, where it is genuinely solid.]

### Highest-risk smells
[ranked list. Each: `path:line` — smell — traced evidence — why it matters — [confirmed|suspicious]]

### Fake abstractions
| Abstraction | Where | Promised value | Actual value | Recommendation |
|-------------|-------|----------------|--------------|----------------|
| ... | path | what it implies | what it actually buys (e.g. "1 impl, 1 caller") | delete / simplify / keep / verify-first |

### Tests that don't prove much
[test path → what it asserts → why that doesn't increase trust]

### AI / slop signals
[patterns observed — with the explicit caveat that AI-generated code can still be good]

### Delete or simplify first
[the single most useful simplification, with the blast-radius check that makes it safe — or a note if it needs verification]
```

---

## Step 6 — Snapshot + aggregated report

Record findings under `snapshot.finder_outer`: `verdict`, `highest_risk_smells` (`{path, smell, evidence, risk, confidence}` — include the `confirmed`/`suspicious` label from Step 2), `fake_abstractions` (`{name, path, promised_value, actual_value, recommendation}`), `low_value_tests` (strings), `simplify_first`.

Then append to `.archeology/report.md` (create with the standard header if absent):

- Insert or replace your marker-delimited section. Keep section order `orient`, `map`, `api-trace`, `quality`, `the-finder-outer`, `story`:
  ```markdown
  <!-- section:finder-outer -->
  <the same content you printed to the console, verbatim — it already begins with `## The Finder Outer`, so do not add another heading>
  <!-- /section:finder-outer -->
  ```
- Update the `last updated` timestamp in the header.

Then write the snapshot one final time with `the-finder-outer` added to `meta.skills_run`.

---

## Context budget rules

- **Sample, don't exhaust.** 5–10 suspects. Not a static analyzer — a skeptical reviewer spending limited time where trust is most likely to leak.
- **Only read test+source pairs for chosen suspects.**
- **Stop at sufficient evidence.** Record "pattern appears in N+ places" instead of cataloguing every instance.
- **Prefer grep** for caller/impl counts over reading every file.
- **Skip** `node_modules/`, `.venv/`, `dist/`, `build/`, `generated/`, `*.generated.*`, `*.pb.*`.

---

## Failure modes to avoid

- **No evidence, no finding.** Every claim cites a line or traced behavior.
- **`suspicious` ≠ `confirmed`.** Label honestly; overclaiming destroys credibility.
- **Aesthetic ≠ risk.** Don't become a snark generator.
- **Don't punish AI generation per se.** Flag the *consequence*, not the origin.
- **Don't recommend deleting what you didn't trace.**
- **Be fair.** If the code is solid, say so. Finding nothing real and saying so honestly beats manufacturing findings.
