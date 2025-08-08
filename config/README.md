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
| `slack/`   | Playwright credentials (`playwright_creds.json`), channel → ID maps, and a helper `workspace.py` that defines your Slack team URL & IDs. |
| `facebook/` | Facebook Marketing API tokens, app IDs, and INI-style settings (`facebook.ini`). |
| `mail/`     | Gmail API credentials (e.g. OAuth `credentials.json`, token caches). |

Each subfolder is a **namespace** for one integration.  Feel free to add more
(e.g. `stripe/`, `amplitude/`) following the same pattern.

---

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
