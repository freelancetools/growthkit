# `config/` — Environment-Specific Configuration Files

This directory stores **non-code artefacts** that adjust how the GrowthKit
tooling connects to external services. Unlike the Python package in
`src/`, everything here is **deployment-specific** and _may_ contain secrets.

> ⚠️ **Never commit production credentials**.  Keep API keys, OAuth tokens, and
> personal access tokens in **untracked** files (see `.gitignore`).  Ship
> **templates** or **sample** configs instead, so other developers know what the
> file _should_ look like.

---

## Current Layout

| Subfolder | Purpose |
|-----------|---------|
| `slack/`   | Playwright auth artifacts and workspace settings used by the Slack exporter. Files: `workspace.json`, `playwright_creds.json`, `storage_state.json`, `conversion_tracker.json`. Templates: `*.example`. |
| `facebook/` | Facebook Marketing API configuration. Files: `facebook.ini` (created on first run), optional `ad-ids.txt`, and a generated `tokens/` folder containing timestamped token JSON files. Templates: `*.example`. |
| `mail/`     | Gmail API OAuth credentials and token cache used by the mail exporter. Files: `client_secret_<id>.json`, `token.pickle`. Templates: `*.example`. |

Each subfolder is a **namespace** for one integration.  Feel free to add more
(e.g. `stripe/`, `amplitude/`) following the same pattern.

---

## Files by Integration

### Slack (`config/slack/`)

- `workspace.json`: Workspace URL and team ID. Auto-created with placeholders by `growthkit.connectors.slack._init_config.ensure_workspace_config()` if missing.
- `playwright_creds.json`: Playwright-saved cookies and Slack tokens for authenticated export.
- `storage_state.json`: Alternative Playwright storage state file (used by the exporter if present).
- `conversion_tracker.json`: Tracks the newest exported `ts` per channel for incremental runs.
- Templates provided: `workspace.json.example`, `playwright_creds.json.example`, `storage_state.json.example`, `conversion_tracker.json.example`.

### Facebook (`config/facebook/`)

- `facebook.ini`: App credentials and settings. Created on first run by the Facebook connector and must be filled in before continuing.
- `ad-ids.txt` (optional): Plain-text list of Ad or Page IDs used by some workflows.
- `tokens/` (generated): Timestamped JSON files saved by the token workflow (history of token runs).
- Templates provided: `facebook.ini.example`, `ad-ids.txt.example`, `ad-account-id.json.example`.

### Mail (`config/mail/`)

- `client_secret_<id>.json`: Google OAuth Desktop client JSON.
- `token.pickle`: Cached OAuth token produced after the first auth flow.
- Templates provided: `client_secret_id-hash.json.example`, `token.pickle.example`.
- Other helper files may exist (e.g. `metadata.json.example`) but are not required by the sync script.

## What **should** live here

| ✅  | Rationale |
|----|-----------|
| **Credential templates** (`*.template`, `*_example.json`) | Allow others to copy & fill in without exposing secrets. |
| **Small, human-editable config files** (`.ini`, `.yaml`, `.json`) | Runtime settings that change across environments. |
| **Helper scripts** that _generate_ default configs (e.g. `growthkit.connectors.slack._init_config.ensure_workspace_config()`). |
| **`.gitignore` rules** that exclude the real secrets while keeping templates. |

---

## What **should _not_** live here

| ❌  | Why |
|----|----|
| Hard-coded API keys, refresh tokens, cookies | Security risk; use environment variables or untracked files. |
| Large binary blobs (>1-2 MB) | Bloats the repo; store externally or compress if truly needed. |
| Business logic or Python modules | Put code in `src/growthkit/` or utility packages. |

---

## Best Practices

1. **Template before commit** – add `*.example` or `*.template` versions of any
   new secret file so CI/tests don’t break.
2. **Reference via environment variables** in code wherever possible.  Only fall
   back to reading files in `config/` when OAuth/device tokens need persistence.
3. **Rotate & revoke** credentials regularly; automated scripts should respect
   token expiry and refresh when needed.
