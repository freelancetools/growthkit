# Expand tool for multiple slack workspaces
_Exported on 8/18/2025 at 13:53:28 CDT from Cursor (1.4.5)_

---

**User**

What would we have to do in a codebase like this to allow users to use this tool for access to multiple slack workspaces? Right now it's just one. Let's brainstorm paths before proceeding with code.

---

**Cursor**

### Goal
Enable running the Slack exporter against multiple Slack workspaces, with isolated config/state/outputs and an easy way to select a workspace at runtime.

### Option A (recommended): Per-workspace subdirectories
- **Layout changes**
  - Config per workspace:
    - `config/slack/<alias>/workspace.json`  (contains `url`, `team_id`)
    - `config/slack/<alias>/storage_state.json`
    - `config/slack/<alias>/playwright_creds.json`
    - `config/slack/<alias>/conversion_tracker.json`
  - Data per workspace:
    - `data/slack/<alias>/exports/`
    - `data/slack/<alias>/channel_map.json`
    - `data/slack/<alias>/rolodex.json` (Slack user IDs are workspace-scoped)
  - Keep current single-workspace files working as legacy fallback (`config/slack/workspace.json`, etc.).

- **CLI changes**
  - `gk-slack --workspace <alias>` (default to `default` if omitted).
  - `gk-slack --list-workspaces`, `--add-workspace <alias> --url ... --team-id ...`, `--remove-workspace <alias>` (optional sugar).
  - `gk-slack --all` to iterate all configured workspaces.

- **Code changes (high level)**
  - Introduce `WorkspaceAlias` and a `WorkspacePaths` helper on top of `WorkspaceSettings`:
    - Centralize all paths (exports, tracker, creds, storage state, channel map, rolodex) as instance properties instead of module-level constants.
  - Update `ensure_workspace_config(alias)` to create `config/slack/<alias>/workspace.json`.
  - Update `load_workspace_settings(alias)` to read `config/slack/<alias>/workspace.json`, validate, and return `WorkspaceSettings(alias, url, team_id)`.
  - Update `SlackBrowser` to accept `WorkspaceSettings` and use `WorkspacePaths` everywhere (replace `EXPORT_DIR`, `TRACK_FILE`, `CREDENTIALS_FILE`, `STORAGE_STATE_FILE`, `CHANNEL_MAP_FILE`, `ROLODEX_FILE`).
  - Add env var support `GK_SLACK_WORKSPACE=<alias>` as another way to pick the workspace.
  - Logging: write `src/growthkit/utils/logs/slack_fetcher.<alias>.log` for clarity.
  - Backward compatibility: if `--workspace` not provided and legacy files exist, use them; else use `default`.

- **Pros**
  - Clear isolation by directory.
  - Avoids filename suffix sprawl.
  - Straightforward to cleanly remove a workspace by deleting its folder.
- **Cons**
  - Requires updating path creation and IO code across the fetcher.

### Option B: Suffix-based files in shared folders
- **Layout**
  - `config/slack/workspace-<alias>.json`, `storage_state-<alias>.json`, `playwright_creds-<alias>.json`, `conversion_tracker-<alias>.json`
  - `data/slack/exports/<alias>/...`
  - `data/slack/channel_map-<alias>.json`, `data/slack/rolodex-<alias>.json`
- **Pros**
  - Minimal directory restructuring.
- **Cons**
  - Messier directories; harder to purge a workspace; easy to mix files by typo.

### Option C: Single `workspaces.json` with an “active” field
- **Layout**
  - `config/slack/workspaces.json` = { "<alias>": { url, team_id }, ... , "active": "<alias>" }
  - Keep state files per alias (either directory or suffix approach).
- **Pros**
  - One place to see all entries.
- **Cons**
  - Adds indirection; still need per-alias files for state; more moving parts.

### Migration plan (for Option A)
- If `config/slack/workspace.json` exists:
  - Treat it as `alias="default"`.
  - Read from legacy paths; write to new per-alias paths; don’t destructively move files.
  - Print a one-time notice suggesting `config/slack/default/` structure.
- Create `gk-slack --add-workspace` that writes `config/slack/<alias>/workspace.json`.
- README: document `--workspace`, directory layout, and how to migrate.

### Behavior changes
- Storage state, cookies, credentials are isolated per workspace, preventing cross-workspace leakage.
- Exports written to `data/slack/<alias>/exports/` so files are clearly separated.
- Channel/user maps and trackers are per workspace to avoid ID/name collisions.

### Nice-to-haves
- `--all` to iterate `aliases` and run the export sequentially.
- Guardrails: verify that captured `team_id` from `client.userBoot` matches configured `team_id`; warn if mismatch.
- Concurrency: if running multiple aliases in parallel, place a simple lock file in each `config/slack/<alias>`.
- Filename prefix: optionally prefix export filenames with alias for portability when copying files around.

### Acceptance criteria
- Run `gk-slack --workspace acme` and `gk-slack --workspace contoso` separately; each uses its own state and outputs.
- Legacy single-workspace users can run unchanged; no breaking changes.
- Documentation updated with selection, listing, and directory structure.

If this direction (Option A) works for you, I’ll implement: workspace CLI flag, per-workspace paths via `WorkspacePaths`, refactor path constants to instance properties, and add legacy fallback.

