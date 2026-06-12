#!/usr/bin/env bash
# code-archeology/scripts/run.sh
#
# Run any combination of code-archeology skills against a target repo,
# each skill in a separate claude session so context stays bounded.
#
# Usage:
#   ./scripts/run.sh [TARGET] [OPTIONS]
#
# Run from the code-archeology repo (skills load from here, target is passed as path).
# Or run from inside the target repo if you've already copied .claude/ there.

set -euo pipefail

# ── colours ────────────────────────────────────────────────────────────────────
BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

# ── usage ──────────────────────────────────────────────────────────────────────
usage() {
  cat <<EOF

${BOLD}code-archeology — run all skills, each in a fresh session${RESET}

${BOLD}Usage:${RESET}
  $(basename "$0") [TARGET] [OPTIONS]

${BOLD}Arguments:${RESET}
  TARGET              Path to the repo to analyze (default: current directory)

${BOLD}Options:${RESET}
  --skills LIST       Comma-separated skills to run (default: all, in order)
                      Available: orient, map, api-trace, quality, the-finder-outer, story
  --from SKILL        Start from this skill, skipping earlier ones
                      (useful for resuming after orient already ran)
  --diagram           Pass --diagram to /api-trace (emit Mermaid per method)
  --max-methods N     Pass --max-methods to /api-trace (default: 20)
  --api NAME          Pass --api to /api-trace (limit to one API group)
  -h, --help          Show this help

${BOLD}Examples:${RESET}
  $(basename "$0") ../my-repo
  $(basename "$0") ../my-repo --skills orient,quality
  $(basename "$0") ../my-repo --from map
  $(basename "$0") ../my-repo --diagram --max-methods 10 --api users
  $(basename "$0") ../my-repo --skills api-trace --api payments --diagram

${BOLD}How it works:${RESET}
  Each skill runs as a separate 'claude -p' invocation — a completely fresh
  process with its own context window. Skills communicate via
  .archeology/snapshot.json in the target repo, not via conversation context.

EOF
}

# ── defaults ───────────────────────────────────────────────────────────────────
TARGET="."
ALL_SKILLS=("orient" "map" "api-trace" "quality" "the-finder-outer" "story")
SELECTED_SKILLS=()
FROM_SKILL=""
DIAGRAM=""
MAX_METHODS=""
API_GROUP=""

# ── arg parsing ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)       usage; exit 0 ;;
    --skills)        IFS=',' read -ra SELECTED_SKILLS <<< "$2"; shift 2 ;;
    --from)          FROM_SKILL="$2"; shift 2 ;;
    --diagram)       DIAGRAM="--diagram"; shift ;;
    --max-methods)   MAX_METHODS="--max-methods $2"; shift 2 ;;
    --api)           API_GROUP="--api $2"; shift 2 ;;
    -*)              echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
    *)               TARGET="$1"; shift ;;
  esac
done

# ── resolve target ─────────────────────────────────────────────────────────────
TARGET=$(realpath "$TARGET")
if [[ ! -d "$TARGET" ]]; then
  echo -e "${RED}Error: target directory not found: $TARGET${RESET}" >&2
  exit 1
fi

# ── check claude is available ──────────────────────────────────────────────────
if ! command -v claude &>/dev/null; then
  echo -e "${RED}Error: 'claude' CLI not found. Install Claude Code first.${RESET}" >&2
  exit 1
fi

# ── build skill list ───────────────────────────────────────────────────────────
if [[ ${#SELECTED_SKILLS[@]} -eq 0 ]]; then
  SELECTED_SKILLS=("${ALL_SKILLS[@]}")
fi

# Apply --from filter (skip skills before FROM_SKILL in the canonical order)
if [[ -n "$FROM_SKILL" ]]; then
  found=false
  filtered=()
  for s in "${ALL_SKILLS[@]}"; do
    [[ "$s" == "$FROM_SKILL" ]] && found=true
    if $found; then
      # Only include if it's also in SELECTED_SKILLS
      for sel in "${SELECTED_SKILLS[@]}"; do
        [[ "$sel" == "$s" ]] && filtered+=("$s") && break
      done
    fi
  done
  if ! $found; then
    echo -e "${RED}Error: unknown skill for --from: $FROM_SKILL${RESET}" >&2
    echo "Available: ${ALL_SKILLS[*]}" >&2
    exit 1
  fi
  SELECTED_SKILLS=("${filtered[@]}")
fi

# Validate skill names
valid_skills=()
for skill in "${SELECTED_SKILLS[@]}"; do
  ok=false
  for s in "${ALL_SKILLS[@]}"; do [[ "$s" == "$skill" ]] && ok=true && break; done
  if $ok; then
    valid_skills+=("$skill")
  else
    echo -e "${YELLOW}Warning: unknown skill '$skill', skipping${RESET}" >&2
  fi
done
SELECTED_SKILLS=("${valid_skills[@]}")

if [[ ${#SELECTED_SKILLS[@]} -eq 0 ]]; then
  echo -e "${RED}Error: no valid skills selected${RESET}" >&2
  exit 1
fi

# ── header ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}code-archeology${RESET}"
echo -e "${DIM}Target:${RESET} $TARGET"
echo -e "${DIM}Skills:${RESET} ${SELECTED_SKILLS[*]}"
echo ""

# ── locate the validator (rides with the skills) ──────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALIDATOR="$SCRIPT_DIR/../.claude/skills/validate.py"
if [[ ! -f "$VALIDATOR" ]]; then
  VALIDATOR=""
  echo -e "${YELLOW}Warning: validate.py not found — skipping post-skill validation${RESET}" >&2
fi

# ── run each skill ─────────────────────────────────────────────────────────────
PASSED=()
FAILED=()
INVALID=()

for skill in "${SELECTED_SKILLS[@]}"; do
  echo -e "${BOLD}━━━ /$skill ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  echo ""

  # Build the prompt for this skill
  prompt="/$skill $TARGET"
  if [[ "$skill" == "api-trace" ]]; then
    [[ -n "$DIAGRAM" ]]      && prompt="$prompt $DIAGRAM"
    [[ -n "$MAX_METHODS" ]]  && prompt="$prompt $MAX_METHODS"
    [[ -n "$API_GROUP" ]]    && prompt="$prompt $API_GROUP"
  fi

  if claude --add-dir "$TARGET" -p "$prompt"; then
    PASSED+=("$skill")
  else
    echo -e "${RED}  /$skill exited with an error — continuing${RESET}" >&2
    FAILED+=("$skill")
  fi

  # Deterministic check: validate what the skill just wrote. This runs outside
  # the agent's permission system — no model discretion involved.
  if [[ -n "$VALIDATOR" && -d "$TARGET/.archeology" ]]; then
    if ! python3 "$VALIDATOR" "$TARGET"; then
      echo -e "${RED}  /$skill left invalid artifacts (see above)${RESET}" >&2
      INVALID+=("$skill")
    fi
  fi

  echo ""
done

# ── summary ────────────────────────────────────────────────────────────────────
echo -e "${BOLD}━━━ Done ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

if [[ ${#PASSED[@]} -gt 0 ]]; then
  echo -e "${GREEN}✓ Passed:${RESET} ${PASSED[*]}"
fi
if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo -e "${RED}✗ Failed:${RESET} ${FAILED[*]}"
fi
if [[ ${#INVALID[@]} -gt 0 ]]; then
  echo -e "${RED}✗ Invalid artifacts after:${RESET} ${INVALID[*]}"
fi

REPORT="$TARGET/.archeology/report.md"
if [[ -f "$REPORT" ]]; then
  echo ""
  echo -e "${DIM}Report:${RESET} $REPORT"
fi

echo ""
[[ ${#FAILED[@]} -gt 0 || ${#INVALID[@]} -gt 0 ]] && exit 1 || exit 0
