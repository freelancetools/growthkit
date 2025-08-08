# `scripts/` — Thin CLI Wrappers

This directory holds **executable, one-liner** Python wrappers that you can
invoke directly from the command-line (e.g. `python scripts/report_weekly.py`).
Each wrapper should do nothing more than:

1. Validate / bootstrap **local environment state** that _cannot_ live inside
   the library (e.g. ensure a config file has been generated).
2. Import the **real implementation** from the installable `growthkit` package.
3. Delegate execution to a single `main()` function.

The goal is to keep the package import-safe (side-effect-free) while still
shipping ergonomic entry-points for end-users.

---

## What **should** live here

| ✅  | Description |
|----|-------------|
| Tiny, self-contained wrappers | One-file scripts < ~30 LOC that only call `growthkit.*` code. |
| Shebang & docstring | Each file starts with `#!/usr/bin/env python3` and a concise docstring. |
| CLI convenience | Argument parsing **only** if it cannot be moved into the library without side-effects. |
| Transitional glue | Light helpers that prepare *runtime* artefacts (e.g. create a default config file) before delegating. |

---

## What **should _not_** live here

| ❌  | Reason |
|----|--------|
| Business logic, data processing, or analysis code | Put that in `src/growthkit/` so it can be unit-tested and imported elsewhere. |
| Secrets, API tokens, or environment-specific config | Use the `config/` hierarchy; scripts must read from there, not embed secrets. |
| Large helper libraries | If more than ~30 LOC and reusable, move it into `growthkit.utils` (or a more specific sub-module). |
| Long-running daemons / services | Create a dedicated module (or `cli/` entry-point) instead of hiding it here. |

---

## Existing Scripts

| File | Type | Purpose |
|------|------|---------|
| `slack_export.py` | Python wrapper | Delegates to `growthkit.connectors.slack.slack_fetcher.run_main()` to export Slack messages via Playwright. |
| `email_export.py` | Python wrapper | Delegates to `growthkit.connectors.mail.gmail_sync.main()` to export a complete Gmail archive. |
| `untrack_sensitive_files.sh` | Bash utility | Removes large, generated, or sensitive files from Git index without deleting local copies. Run once after cloning to clean up tracked artifacts. |

### Python Wrappers
Every new Python script should follow the same **import-then-delegate** pattern used
in the existing examples:

```python
#!/usr/bin/env python3
"""Brief description of what this script does."""

from growthkit.module import main

if __name__ == "__main__":
    main()
```

### Shell Utilities
Shell scripts should be self-documenting with:
- Clear usage instructions in header comments
- Proper error handling (`set -euo pipefail`)
- Informative output messages with status indicators