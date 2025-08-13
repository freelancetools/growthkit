# `scripts/` — Utilities and Local Helpers

This directory hosts **shell utilities and repo maintenance helpers**. Python
entry points have moved under `src/growthkit/entrypoints/` and are exposed as
installed CLI commands (see Installed Python Entry Points below).

The goal is to keep the package import-safe (side-effect-free) while still
shipping ergonomic entry-points for end-users.

---

## What **should** live here

| ✅  | Description |
|----|-------------|
| Shell utilities | One-file `bash` scripts that help with local setup, maintenance, or safety rails. |
| Tiny, self-contained wrappers (rare) | If unavoidable, Python files < ~30 LOC that only call `growthkit.*` code. Prefer `src/growthkit/entrypoints/` instead. |
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
| Long-running daemons / services | Create a dedicated module (or entry-point) instead of hiding it here. |

---

## Existing Scripts

| File | Type | Purpose |
|------|------|---------|
| `untrack_sensitive_files.sh` | Bash utility | Removes large, generated, or sensitive files from Git index without deleting local copies. Run once after cloning to clean up tracked artifacts. |

Run:

```
bash scripts/untrack_sensitive_files.sh
```

### Installed Python Entry Points

After installing the package (editable install shown):

```
python -m pip install -e .
```

You can use the following CLI commands (defined in `pyproject.toml`):

- `gk-slack`: Runs Slack export (`growthkit.entrypoints.slack_export:run_main`).
- `gk-email`: Runs Gmail export (`growthkit.entrypoints.email_export:main`).

### Python Wrappers
If you must add a Python script here, keep it minimal and prefer adding it under
`src/growthkit/entrypoints/` with a console entry in `pyproject.toml`.

### Shell Utilities
Shell scripts should be self-documenting with:
- Clear usage instructions in header comments
- Proper error handling (`set -euo pipefail`)
- Informative output messages with status indicators