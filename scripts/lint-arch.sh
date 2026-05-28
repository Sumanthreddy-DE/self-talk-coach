#!/usr/bin/env bash
# Architecture lint — run before committing.
# Agent-readable errors: each violation says WHAT is wrong and HOW to fix it.
#
# Add project-specific checks in the marked section below.

set -e
PASS=true
SRC_DIRS=("src" "app" "lib")   # edit for this project's source directories

echo "=== lint-arch ==="

# --- File size (800 line max) ---
for dir in "${SRC_DIRS[@]}"; do
  if [[ -d "$dir" ]]; then
    while IFS= read -r file; do
      lines=$(wc -l < "$file")
      if (( lines > 800 )); then
        echo "ERROR [file-size]: $file has $lines lines (max 800)."
        echo "  FIX: Split into smaller files. Each file should have one clear responsibility."
        PASS=false
      fi
    done < <(find "$dir" -type f \( -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.tsx" \) 2>/dev/null)
  fi
done

# --- No bare print/console.log in committed code (comment out if not relevant) ---
# for dir in "${SRC_DIRS[@]}"; do
#   if [[ -d "$dir" ]]; then
#     matches=$(grep -rn "^\s*print(" "$dir" --include="*.py" 2>/dev/null || true)
#     if [[ -n "$matches" ]]; then
#       echo "ERROR [no-bare-print]: raw print() found. Use structured logging instead."
#       echo "$matches"
#       PASS=false
#     fi
#   fi
# done

# --- [ADD PROJECT-SPECIFIC CHECKS BELOW] ---
# Pattern:
#   if <check fails>; then
#     echo "ERROR [rule-name]: <what is wrong>."
#     echo "  FIX: <exactly how to fix it>."
#     PASS=false
#   fi

# --- Result ---
echo ""
if $PASS; then
  echo "lint-arch: PASS — all checks clean"
else
  echo "lint-arch: FAIL — fix violations above before committing"
  exit 1
fi
