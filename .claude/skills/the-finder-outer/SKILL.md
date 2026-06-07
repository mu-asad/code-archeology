---
name: the-finder-outer
description: Adversarial code review — find the gap between "passes checks" and "I'd trust this in production." Hunts code that satisfies linters, tests, and type checkers while being fake-good: single-use abstractions, tests that assert mocks instead of behavior, defensive checks that can't fire, silently-dropped data, hidden global state. Funny name, serious evidence-based output, no grade. Use when the user wants a skeptical senior-reviewer pass, asks "where is this code pretending to be good / what's actually wrong with this," or runs /the-finder-outer. Best after /orient and /map; reuses /quality hotspots if present. Reads and writes .archeology/snapshot.json.
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

# the-finder-outer

Adversarial code review. Where `/quality` asks *"is this codebase well-built?"* and grades it, this skill is sharper and more hostile in a useful way: **"where is this code pretending to be good?"**

The job is to find the gap between *passes checks* and *I'd trust this in production* — the code that satisfies linters, tests, type checkers, and a quick skim while being over-abstracted, quietly fragile, or fake-good. **Funny name, serious output.** It does not dunk on code for sport; it finds the specific places where trust leaks out, and proves each one with evidence.

**The goal is to find what is hard to find.** Surface snark (a long variable name) is not the point. The signature move is to **trace actual behavior** and **pair tests with the source they claim to cover** — to surface trust leaks a skim would miss.

---

## How to invoke

```
/the-finder-outer [path-to-repo]
```

If no path is given, use the current working directory.

**Resolve the target root first.** If a path *is* given — or the repo lives somewhere other than your cwd — `cd` into it before running any steps, so every command operates on that repo. Every step below assumes commands run **inside the target repo**.

**Prerequisite**: run `/orient` first. This skill reuses `/map`'s layer model and `/quality`'s complexity hotspots when present, but works without them.

---

## Step 0 — Load context

Load `.archeology/snapshot.json`. If it doesn't exist, tell the user to run `/orient` first.

Pull in whatever prior analysis exists — it makes suspect-selection cheaper and the findings sharper:
- `snapshot.quality.structural.complexity_hotspots` — pre-identified large/complex files
- `snapshot.quality.intentional` — silent failures / fake validation already flagged (confirm or deepen them)
- `snapshot.structure.layers` — the logical layers (from `/map`)
- `snapshot.product.summary` + `snapshot.structure.domain_model` — so you can tell *generic* names from *honest domain* names

If `the-finder-outer` is already in `meta.skills_run`, report the existing findings and ask if the user wants to re-run.

**Write the snapshot after every major step.**

---

## Step 1 — Pick 5–10 suspects (cheap scan)

Do **not** analyze the whole repo. Identify a short list of suspect areas, cheaply, then spend your budget tracing them in Step 2.

Sources of suspects, in priority order:
1. **`/quality` hotspots** (if present) — start here, they're already found.
2. **Largest files** — `git ls-files '*.ts' '*.tsx' '*.py' | while IFS= read -r f; do wc -l "$f"; done | sort -rn | head`. Large files are often large because no one made decisions.
3. **Deep abstraction layers** — directories or files named `strategy`, `factory`, `provider`, `manager`, `abstract`, `base`, `*Interface`, `handler`. Grep for them; they're where fake sophistication hides.
4. **Broad tests** — the largest test files, and tests with the most mock setup (`grep -rl "mock\|Mock\|patch\|stub"` in the test dir). These are the prime candidates for "asserts mocks, not behavior."
5. **Repeated module shapes** — directories whose subfolders all have the identical file layout (the AI-uniformity signal). These often hide copy-paste that should've been one abstraction — or a fake abstraction that wasn't extracted.

Pick **5–10 suspects total**, spanning a few categories. Record them in a working list. Write snapshot.

---

## Step 2 — Trace, don't guess (the core)

This is the skill's signature step, and where it earns its keep. For each suspect, **actually read it** and **trace what it does** — don't pattern-match from the filename. Every finding that comes out of this step must carry **concrete evidence**.

### For a suspect abstraction (interface / strategy / factory / manager / base class)

Run the five questions, and answer each with evidence:
1. **What complexity is this abstraction buying down?** (If you can't name it, that's the finding.)
2. **How many real implementations / callers does it have?** — `grep -rn` for the class/interface name. One implementation behind an interface is a red flag.
3. **Would deleting it make the code easier to understand?** Trace what collapses if it's inlined.
4. **Does it preserve domain language, or hide it behind generic names?** (`process`, `handle`, `manager`, `data` over `Invoice`, `settle`, `refund`.)
5. **Is it honest about failure, state, and side effects?** Does a method named `get*` mutate? Does a "pure" transform hit the network?

### For a suspect test

Read the test **and the source it claims to cover**, together:
- Does it assert **behavior**, or just that a **mock was called**? (`assert mock.called` proves wiring, not correctness.)
- Is it a **snapshot/golden** test that locks in whatever the code happened to output — including bugs?
- Does it cover the **risky** path (the error branch, the edge case), or only the happy path while the dangerous code is untested?
- Does setup quietly **replace the system under test** with a stub, so the test passes regardless of the real logic?

### For a suspect function / transform

Trace input → output against what the name and docstring **claim**:
- Does it **silently drop fields** a caller would expect to survive? (Common in mappers and serializers.)
- Are there **defensive checks that can't trigger** given how it's actually called? (Dead reassurance.)
- Does it **swallow partial failures** — return a partial result or increment an error counter with no way to know what was lost?
- Is there **retry logic without idempotency**, or **"temporary" code on a critical path**?

For each finding, record: the **path (and line if you can)**, the **smell**, the **evidence** (what you traced, the caller count, the specific behavior), and label it **`confirmed`** (you traced it) or **`suspicious`** (worth a look, not proven). Never present `suspicious` as `confirmed`.

Write snapshot after tracing.

---

## Step 3 — Rank by risk, not aesthetics

Order findings by **risk to trust/production**, not by how annoying they are. Risk ≈ *(how likely it bites)* × *(blast radius if it does)*.

- A mapper that silently drops a field on a payment object outranks a `UserDataProcessingManager` name every time.
- **Suppress pure-aesthetic complaints.** A verbose name, a tutorial-style comment, or boilerplate is **not a finding** unless it *hides behavior* or *causes a trust leak*. If your only evidence is "this looks AI-generated," it goes in the AI-signals caveat section, not the risk list.

---

## Step 4 — Recommend: delete or simplify first, safety-gated

Default to **"delete or simplify"** over "rewrite." The most useful output is often "this whole layer can go."

**But gate every deletion on blast radius.** Only recommend removing something when you've **verified it's safe**:
- few or no callers (you grepped), and
- you traced what it does and nothing load-bearing is hiding inside.

If you **can't** verify it's safe to remove, say so explicitly: *"load-bearing or unclear — flag, don't delete yet."* Recommending the deletion of code you didn't trace is exactly the kind of confident-but-wrong move this skill exists to catch. Hold yourself to the same standard.

---

## Step 5 — Output

Print the report in this format (no grade — findings stand on their evidence):

```
## The Finder Outer

### Verdict
[2-4 paragraphs: where this code is fake-good, over-complex, or quietly fragile — and, fairly, where it is genuinely solid. Skeptical and direct, but evidence-based.]

### Highest-risk smells
[ranked list. Each item: `path:line` — the smell — the evidence you traced — why it matters — [confirmed|suspicious]]

### Fake abstractions
| Abstraction | Where | Promised value | Actual value | Recommendation |
|-------------|-------|----------------|--------------|----------------|
| ... | path | what it implies it buys | what it actually buys (e.g. "1 impl, 1 caller") | delete / simplify / keep |

### Tests that don't prove much
[examples: test path → what it asserts → why that doesn't increase trust (asserts a mock, locks in junk, happy-path only)]

### AI / slop signals
[patterns observed — with the explicit caveat that AI-generated code can still be good. These are signals to verify, not findings on their own.]

### Delete or simplify first
[the single most useful simplification, with the blast-radius check that makes it safe — or a clear note if it needs verification first]
```

---

## Step 6 — Snapshot + aggregated report

Record findings under `snapshot.finder_outer`:
- `verdict` (string)
- `highest_risk_smells` (array of `{ path, smell, evidence, risk }`)
- `fake_abstractions` (array of `{ name, path, promised_value, actual_value, recommendation }`)
- `low_value_tests` (array of strings)
- `simplify_first` (string)

Then append to the aggregated `.archeology/report.md` (create it with the standard header if it doesn't exist):

- Insert or replace your marker-delimited section. Keep section order `orient`, `map`, `quality`, `the-finder-outer`, `story`:
  ```markdown
  <!-- section:finder-outer -->
  <the same content you printed to the console, verbatim — it already begins with `## The Finder Outer`, so do not add another heading>
  <!-- /section:finder-outer -->
  ```
- Update the `last updated` timestamp in the header.

Then write the snapshot one final time with `the-finder-outer` added to `meta.skills_run`.

---

## Context budget rules

- **Sample, don't exhaust.** 5–10 suspects, full stop. This is not a static analyzer; it's a skeptical reviewer with limited time spending it where trust is most likely to leak.
- **Only read test+source pairs for chosen suspects.** Don't read the whole test suite.
- **Stop at sufficient evidence.** Once a finding is proven, move on — you don't need a third example of the same smell. Record "pattern appears in N+ places" instead.
- **Prefer grep for caller/impl counts** over reading every file.
- **Skip** `node_modules/`, `.venv/`, `dist/`, `build/`, `generated/`, `*.generated.*`, `*.pb.*`.

---

## Failure modes to avoid

- **No evidence, no finding.** Every claim cites a line or a traced behavior. "Feels off" is not a finding.
- **`suspicious` ≠ `confirmed`.** Label honestly. Overclaiming destroys the tool's credibility faster than missing a smell.
- **Aesthetic ≠ risk.** A long name, a verbose comment, or boilerplate is not a finding unless it hides behavior. Don't become a snark generator.
- **Don't punish AI generation per se.** AI-written code can be excellent. Flag the *consequence* (the trust leak), not the origin. AI signals are a caveat section, not the verdict.
- **Don't recommend deleting what you didn't trace.** Hold yourself to the standard you're enforcing.
- **Be fair.** If the code is actually solid, say so. A finder-outer that finds nothing real, but says nothing's wrong honestly, is more trustworthy than one that manufactures findings to justify itself.
