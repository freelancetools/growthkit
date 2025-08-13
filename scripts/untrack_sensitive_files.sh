#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# untrack_sensitive_files.sh
# -----------------------------------------------------------------------------
# Removes large, generated, or sensitive files from the Git index **without**
# deleting the local copies.  Run this from the repository root *once* after
# cloning.  After it completes, inspect the output of `git status`, then commit
# the changes and push.
# -----------------------------------------------------------------------------
# USAGE
#   bash scripts/untrack_sensitive_files.sh
# -----------------------------------------------------------------------------
set -euo pipefail

# Verify we are inside a Git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "❌  This script must be run from within a Git repository" >&2
  exit 1
fi

# Targeted untracking that preserves tracked *.example templates
# - We enumerate tracked files under these roots and drop anything that is NOT a
#   *.example file. This avoids nuking committed templates.
sensitive_roots=(
  # 👉 Credentials & private configs
  "config/facebook"       # facebook.ini + tokens/*.json (real)
  "config/slack"          # workspace.json, playwright creds, storage state (real)
  "config/mail"           # client_secret_*.json, token.pickle, metadata.json (real)

  # 👉 Generated data exports
  "data/ads"
  "data/facebook"
  "data/slack"
  "data/mail/exports"
  "data/transcripts"
  "data/products/unattributed"
  "data/reports"          # keep *.example reports tracked
)

# Explicit single-file artefacts to untrack if accidentally committed
explicit_files=(
  "src/growthkit/connectors/mail/cursor.txt"
  "data/rolodex.json"
)

# First handle explicit files
for f in "${explicit_files[@]}"; do
  if git ls-files --error-unmatch "$f" > /dev/null 2>&1; then
    echo "➡️  Untracking $f …"
    git rm --cached --quiet --ignore-unmatch "$f"
  else
    echo "ℹ️  $f was not tracked – skipping"
  fi
done

# Then handle directories by enumerating tracked files and skipping *.example
for root in "${sensitive_roots[@]}"; do
  if [ -d "$root" ]; then
    tracked=$(git ls-files -z "$root" || true)
    if [ -n "$tracked" ]; then
      while IFS= read -r -d '' file; do
        case "$file" in
          *.example)
            # keep example templates tracked
            ;;
          *)
            echo "➡️  Untracking $file …"
            git rm --cached --quiet --ignore-unmatch "$file" || true
            ;;
        esac
      done < <(printf '%s' "$tracked")
    else
      echo "ℹ️  No tracked files under $root – skipping"
    fi
  else
    echo "ℹ️  $root does not exist – skipping"
  fi
done

echo "\n✅  Finished.  Review the staged changes with 'git status' or 'git diff --cached'."
echo "   When you're happy, commit and push:"
echo "     git commit -m 'chore: stop tracking generated / sensitive artefacts'"

