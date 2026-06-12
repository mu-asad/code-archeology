#!/usr/bin/env python3
"""Deterministic checks for code-archeology output artifacts.

Validates .archeology/snapshot.json against schema/snapshot.schema.json and
lints .archeology/report.md marker structure. This is the external check the
skills themselves cannot be trusted to perform — no model discretion involved.

Usage:
    validate.py <target-repo>          # validate <target-repo>/.archeology/*
    validate.py --snapshot FILE        # validate a specific snapshot file
    validate.py --report FILE          # lint a specific report file
    validate.py --self-test            # verify the validator itself works

Exit codes: 0 = all checks passed, 1 = violations found, 2 = usage/setup error.

Lives in .claude/skills/ so it travels with `cp -r .claude <target>/`.
Uses the `jsonschema` package when installed; otherwise falls back to a
built-in structural check covering required keys, types, and enums.
"""

import json
import re
import sys
from pathlib import Path

CANONICAL_SECTION_ORDER = [
    "orient",
    "map",
    "api-trace",
    "quality",
    "finder-outer",
    "story",
]

SNAPSHOT_REQUIRED_KEYS = ["meta", "coverage", "stack", "product"]

# Conditional completeness: if a skill claims to have run (meta.skills_run),
# the fields it owns must exist. This is the lightweight alternative to a
# separate "complete" schema (issue #3) — the base schema stays lenient for
# mid-pipeline snapshots, while a skill that finished is held to its output.
SKILL_COMPLETENESS = {
    "orient": ["product.summary", "structure.entry_points", "meta.stats"],
    "map": ["structure.layers"],
    "api-trace": ["api_trace.inventory"],
    "quality": ["quality.overall_grade", "quality.grade_rationale"],
    "the-finder-outer": ["finder_outer.verdict"],
    "story": ["story.timeline"],
}

# Enum fields enforced by the fallback checker (path → allowed values).
ENUM_CHECKS = [
    ("api_trace.inventory[].trace_status",
     {"pending", "traced", "partial", "ambiguous", "generated-from-convention"}),
    ("api_trace.methods[].trace_status",
     {"traced", "partial", "ambiguous", "generated-from-convention"}),
    ("finder_outer.highest_risk_smells[].confidence",
     {"confirmed", "suspicious"}),
    ("finder_outer.fake_abstractions[].recommendation",
     {"delete", "simplify", "keep", "verify-first"}),
]


def find_schema():
    """Locate snapshot.schema.json relative to this script."""
    here = Path(__file__).resolve().parent
    candidates = [
        here / "snapshot.schema.json",                    # copied alongside
        here.parent.parent / "schema" / "snapshot.schema.json",  # repo layout
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def get_path(obj, dotted):
    """Resolve 'a.b[].c' against obj, yielding (location, value) pairs."""
    parts = dotted.split(".")
    items = [("", obj)]
    for part in parts:
        nxt = []
        is_array = part.endswith("[]")
        key = part[:-2] if is_array else part
        for loc, val in items:
            if not isinstance(val, dict) or key not in val:
                continue
            child = val[key]
            child_loc = f"{loc}.{key}".lstrip(".")
            if is_array:
                if isinstance(child, list):
                    nxt.extend((f"{child_loc}[{i}]", v) for i, v in enumerate(child))
            else:
                nxt.append((child_loc, child))
        items = nxt
    return items


def validate_snapshot(snapshot_path, schema_path):
    errors = []
    try:
        snapshot = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return [f"snapshot unreadable or invalid JSON: {e}"]

    if not isinstance(snapshot, dict):
        return [f"snapshot root must be a JSON object, got {type(snapshot).__name__}"]

    schema = None
    if schema_path:
        try:
            schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            errors.append(f"schema unreadable or invalid JSON: {e}")

    schema_validated = False
    if schema is not None:
        try:
            import jsonschema
        except ImportError:
            jsonschema = None  # fall through to built-in checks
        if jsonschema is not None:
            try:
                # Pick the validator class from the schema's own $schema
                # declaration (ours is draft-07); don't assume a draft.
                validator_cls = jsonschema.validators.validator_for(schema)
                validator_cls.check_schema(schema)
                validator = validator_cls(schema)
                for err in sorted(validator.iter_errors(snapshot), key=str):
                    loc = ".".join(str(p) for p in err.absolute_path) or "(root)"
                    errors.append(f"schema violation at {loc}: {err.message}")
                schema_validated = True
            except jsonschema.exceptions.SchemaError as e:
                # The schema itself is broken — report it and fall back to
                # the built-in checks rather than crashing.
                errors.append(f"schema file is not a valid JSON Schema: "
                              f"{e.message}")

    if not schema_validated:
        # Built-in fallback: required keys, basic types, enums.
        for key in SNAPSHOT_REQUIRED_KEYS:
            if key not in snapshot:
                errors.append(f"missing required top-level key: {key}")

        meta = snapshot.get("meta", {})
        if not isinstance(meta, dict):
            errors.append("meta must be an object")
        else:
            skills_run = meta.get("skills_run")
            if skills_run is not None and not isinstance(skills_run, list):
                errors.append("meta.skills_run must be an array")

        coverage = snapshot.get("coverage", {})
        if isinstance(coverage, dict):
            for field in ("analyzed", "queued", "skipped"):
                v = coverage.get(field)
                if v is not None and not isinstance(v, list):
                    errors.append(f"coverage.{field} must be an array")

        for dotted, allowed in ENUM_CHECKS:
            for loc, val in get_path(snapshot, dotted):
                if val is not None and val not in allowed:
                    errors.append(
                        f"invalid enum at {loc}: {val!r} not in {sorted(allowed)}")

    # Conditional completeness — runs in both modes, since it isn't (and can't
    # be) expressed in the lenient base schema: a skill that claims completion
    # must have written the fields it owns.
    meta = snapshot.get("meta", {})
    skills_run = meta.get("skills_run", []) if isinstance(meta, dict) else []
    if isinstance(skills_run, list):
        for skill in skills_run:
            if not isinstance(skill, str):
                errors.append(
                    f"meta.skills_run entries must be strings, got "
                    f"{type(skill).__name__}: {skill!r}")
                continue
            for dotted in SKILL_COMPLETENESS.get(skill, []):
                if not get_path(snapshot, dotted):
                    errors.append(
                        f"incomplete: '{skill}' is in meta.skills_run but "
                        f"{dotted} is missing")

    return errors


def lint_report(report_path):
    errors = []
    try:
        text = Path(report_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"report unreadable: {e}"]

    opens = re.findall(r"<!-- section:([a-z-]+) -->", text)
    closes = re.findall(r"<!-- /section:([a-z-]+) -->", text)

    for name in sorted(set(opens)):
        if opens.count(name) > 1:
            errors.append(f"duplicate section marker: {name} (×{opens.count(name)})")
    for name in set(opens):
        if closes.count(name) != opens.count(name):
            errors.append(f"unbalanced markers for section: {name}")
    for name in set(closes) - set(opens):
        errors.append(f"closing marker without opening: {name}")

    known = [s for s in opens if s in CANONICAL_SECTION_ORDER]
    expected = [s for s in CANONICAL_SECTION_ORDER if s in known]
    if known != expected:
        errors.append(
            f"sections out of canonical order: found {known}, expected {expected}")
    for name in set(opens) - set(CANONICAL_SECTION_ORDER):
        errors.append(f"unknown section name: {name}")

    return errors


def self_test():
    """Verify the validator catches what it claims to catch."""
    import tempfile

    failures = []
    schema_path = find_schema()

    good_snapshot = {
        "meta": {"repo": "/tmp/x", "created_at": "now", "updated_at": "now",
                 "skills_run": ["orient"], "stats": {"tracked_files": 10},
                 "progress": {"orient": {"current_step": "done",
                                         "completed_steps": ["step-1"]}}},
        "coverage": {"analyzed": [], "queued": [], "skipped": []},
        "stack": {},
        "product": {"summary": "a thing"},
        "structure": {"entry_points": [{"path": "main.py"}]},
        "finder_outer": {"highest_risk_smells": [
            {"path": "a.py", "smell": "x", "evidence": "y",
             "confidence": "confirmed"}]},
    }
    bad_snapshot = {
        "meta": {"skills_run": "not-a-list"},
        "finder_outer": {"highest_risk_smells": [
            {"path": "a.py", "smell": "x", "evidence": "y",
             "confidence": "definitely"}]},
    }
    # Schema-valid but claims a skill ran without writing its output —
    # must be caught by the conditional completeness check in BOTH modes.
    incomplete_snapshot = {
        "meta": {"repo": "/tmp/x", "created_at": "now", "updated_at": "now",
                 "skills_run": ["quality"]},
        "coverage": {"analyzed": [], "queued": [], "skipped": []},
        "stack": {},
        "product": {},
    }
    good_report = (
        "# Report\n\n<!-- section:orient -->\n## Orientation\n<!-- /section:orient -->\n"
        "<!-- section:quality -->\n## Quality\n<!-- /section:quality -->\n")
    bad_report = (
        "# Report\n\n<!-- section:quality -->\nq\n<!-- /section:quality -->\n"
        "<!-- section:orient -->\no\n<!-- /section:orient -->\n"
        "<!-- section:orient -->\ndupe\n")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "good.json").write_text(json.dumps(good_snapshot), encoding="utf-8")
        (td / "bad.json").write_text(json.dumps(bad_snapshot), encoding="utf-8")
        (td / "incomplete.json").write_text(
            json.dumps(incomplete_snapshot), encoding="utf-8")
        (td / "good.md").write_text(good_report, encoding="utf-8")
        (td / "bad.md").write_text(bad_report, encoding="utf-8")

        if validate_snapshot(td / "good.json", schema_path):
            failures.append("valid snapshot was rejected: "
                            + str(validate_snapshot(td / "good.json", schema_path)))
        if not validate_snapshot(td / "bad.json", schema_path):
            failures.append("invalid snapshot was accepted")
        incomplete_errs = validate_snapshot(td / "incomplete.json", schema_path)
        if not any("incomplete" in e for e in incomplete_errs):
            failures.append(
                "snapshot claiming 'quality' ran without quality output "
                "was not flagged incomplete")
        if lint_report(td / "good.md"):
            failures.append("valid report was rejected: "
                            + str(lint_report(td / "good.md")))
        if not lint_report(td / "bad.md"):
            failures.append("invalid report was accepted")

    for f in failures:
        print(f"SELF-TEST FAIL: {f}")
    if not failures:
        mode = "jsonschema" if _has_jsonschema() and schema_path else "built-in fallback"
        print(f"self-test passed ({mode} mode, schema: {schema_path or 'not found'})")
    return 1 if failures else 0


def _has_jsonschema():
    try:
        import jsonschema  # noqa: F401
        return True
    except ImportError:
        return False


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2 if not argv else 0

    if argv[0] == "--self-test":
        return self_test()

    snapshot_path = report_path = None
    if argv[0] in ("--snapshot", "--report"):
        if len(argv) < 2:
            print(f"error: {argv[0]} requires a file path")
            return 2
        if argv[0] == "--snapshot":
            snapshot_path = Path(argv[1])
        else:
            report_path = Path(argv[1])
    else:
        target = Path(argv[0])
        arch = target / ".archeology"
        if not arch.is_dir():
            print(f"error: {arch} not found — has any skill run yet?")
            return 2
        if (arch / "snapshot.json").is_file():
            snapshot_path = arch / "snapshot.json"
        if (arch / "report.md").is_file():
            report_path = arch / "report.md"
        if not snapshot_path and not report_path:
            print(f"error: nothing to validate in {arch}")
            return 2

    schema_path = find_schema()
    all_errors = []

    if snapshot_path:
        errs = validate_snapshot(snapshot_path, schema_path)
        all_errors.extend(f"[snapshot] {e}" for e in errs)
        if not errs:
            mode = "jsonschema" if _has_jsonschema() and schema_path else "built-in"
            print(f"✓ snapshot valid ({mode}): {snapshot_path}")
    if report_path:
        errs = lint_report(report_path)
        all_errors.extend(f"[report] {e}" for e in errs)
        if not errs:
            print(f"✓ report markers valid: {report_path}")

    for e in all_errors:
        print(f"✗ {e}")
    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
