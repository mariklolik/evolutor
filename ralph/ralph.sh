#!/bin/bash
# Ralph — Autonomous AI agent loop for Evolutor framework
# Each iteration spawns a FRESH Claude instance with clean context.
# Memory persists via: git history, prd.json (passes field), progress.txt
#
# Usage: ./ralph.sh [max_iterations]
# Default: 100 iterations, model: claude-opus-4-6

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PRD_FILE="$SCRIPT_DIR/prd.json"
PROGRESS_FILE="$SCRIPT_DIR/progress.txt"
CLAUDE_PROMPT="$SCRIPT_DIR/CLAUDE.md"
MODEL="claude-opus-4-6"
MAX_ITERATIONS="${1:-100}"

# Validate required files
for f in "$PRD_FILE" "$PROGRESS_FILE" "$CLAUDE_PROMPT"; do
  if [ ! -f "$f" ]; then
    echo "Error: Required file missing: $f"
    exit 1
  fi
done

# Check jq is available
if ! command -v jq &> /dev/null; then
  echo "Error: jq is required. Install with: apt-get install jq"
  exit 1
fi

# Check claude is available
if ! command -v claude &> /dev/null; then
  echo "Error: claude CLI is required."
  exit 1
fi

echo "================================================================"
echo "  Ralph — Evolutor Framework Builder"
echo "  Model: $MODEL"
echo "  Max iterations: $MAX_ITERATIONS"
echo "  PRD: $PRD_FILE"
echo "================================================================"

# Show initial status
TOTAL=$(jq '.userStories | length' "$PRD_FILE")
DONE=$(jq '[.userStories[] | select(.passes == true)] | length' "$PRD_FILE")
echo "Stories: $DONE/$TOTAL complete"
echo ""

for i in $(seq 1 $MAX_ITERATIONS); do
  echo ""
  echo "==============================================================="
  echo "  Iteration $i of $MAX_ITERATIONS — $(date '+%H:%M:%S')"
  echo "==============================================================="

  # Show current progress from prd.json
  DONE=$(jq '[.userStories[] | select(.passes == true)] | length' "$PRD_FILE")
  REMAINING=$(jq '[.userStories[] | select(.passes == false)] | length' "$PRD_FILE")
  NEXT=$(jq -r '[.userStories[] | select(.passes == false)] | .[0] | "\(.id): \(.title)"' "$PRD_FILE")
  echo "Progress: $DONE done, $REMAINING remaining"
  echo "Next: $NEXT"
  echo ""

  # Early exit if all done
  if [ "$REMAINING" -eq 0 ]; then
    echo "All stories complete!"
    break
  fi

  # Spawn a FRESH Claude instance
  OUTPUT=$(cd "$PROJECT_DIR" && \
    env -u CLAUDECODE \
    CLAUDE_CODE_BLOCKING_LIMIT_OVERRIDE="197000" \
    CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 \
    claude \
      --dangerously-skip-permissions \
      --model "$MODEL" \
      --print \
      < "$CLAUDE_PROMPT" 2>&1 | tee /dev/stderr) || true

  # Check for completion signal
  if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
    echo ""
    echo "================================================================"
    echo "  Ralph completed all tasks!"
    echo "  Finished at iteration $i of $MAX_ITERATIONS"
    echo "================================================================"
    DONE=$(jq '[.userStories[] | select(.passes == true)] | length' "$PRD_FILE")
    echo "Stories completed: $DONE/$TOTAL"
    exit 0
  fi

  # Show last progress entries
  echo ""
  echo "--- Recent progress ---"
  tail -10 "$PROGRESS_FILE" 2>/dev/null || true
  echo "---"

  sleep 3
done

echo ""
echo "================================================================"
echo "  Ralph reached max iterations ($MAX_ITERATIONS)"
echo "================================================================"
DONE=$(jq '[.userStories[] | select(.passes == true)] | length' "$PRD_FILE")
echo "Stories completed: $DONE/$TOTAL"
exit 1
