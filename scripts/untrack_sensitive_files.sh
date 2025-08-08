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

# List of paths (files or directories) that should no longer be tracked.
# Feel free to extend this list as new generated/secret artefacts appear.
paths=(
  # 👉  Credentials & private configs
  "config/facebook"                # app_secret + tokens
  "config/slack"                   # cookies, workspace config
  "src/growthkit/connectors/mail/cursor.txt" # runtime artefact

  # 👉  Generated data exports
  "data/ads"
  "data/products/unattributed"
  "data/slack"
  "data/facebook"

  # (optional) add more paths – e.g. data/facebook, data/transcripts, etc.
)

# Iterate over each path and untrack it from Git (leave working-tree intact)
for p in "${paths[@]}"; do
  if git ls-files --error-unmatch "$p" > /dev/null 2>&1; then
    echo "➡️  Untracking $p …"
    git rm --cached -r --quiet --ignore-unmatch "$p"
  else
    echo "ℹ️  $p was not tracked – skipping"
  fi
done

echo "\n✅  Finished.  Review the staged changes with 'git status' or 'git diff --cached'."
echo "   When you're happy, commit and push:"
echo "     git commit -m 'chore: stop tracking generated / sensitive artefacts'"

