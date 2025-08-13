## GrowthKit — Quick Start

Pragmatic setup and usage for Windows and macOS/Linux. Commands below always invoke tools via the virtual environment’s executables directly (recommended): `./.venv/bin/...` on macOS/Linux and `./.venv/Scripts/...` on Windows.

### 0) Clone the repository

```bash
git clone https://github.com/chrischcodes/growthkit
cd growthkit
```

### 1) Create a virtual environment

macOS/Linux:
```bash
python3.12 -m venv --prompt gkit .venv
./.venv/bin/python -m pip install --upgrade pip wheel
```

Windows (PowerShell):
```powershell
py -3.12 -m venv --prompt gkit .venv
./.venv/Scripts/python -m pip install --upgrade pip wheel
```

Notes:
- Python 3.12 is preferred; 3.10+ is supported.
- Activating the venv is optional. We recommend using the explicit `./.venv/bin/` or `./.venv/Scripts/` paths in all commands to avoid confusion.

### 2) Install GrowthKit in editable mode

macOS/Linux:
```bash
./.venv/bin/pip install -e .
```

Windows (PowerShell):
```powershell
./.venv/Scripts/pip install -e .
```

This provides the CLI scripts inside the venv: `gk-slack` and `gk-email`.

### 3) Playwright runtime (auto, or install explicitly)

The Slack fetcher will auto-install Chromium if missing. To install explicitly:

macOS/Linux:
```bash
./.venv/bin/python -m playwright install chromium
```

Windows (PowerShell):
```powershell
./.venv/Scripts/python -m playwright install chromium
```

### 4) Slack export — first run

Run the Slack fetcher. On first run it creates `config/slack/workspace.json` with placeholders and exits until you update it.

macOS/Linux:
```bash
./.venv/bin/gk-slack
```

Windows (PowerShell):
```powershell
./.venv/Scripts/gk-slack
```

Edit `config/slack/workspace.json` to include your real workspace URL and team ID:
```json
{
  "note": "Enter your workspace URL and team ID here.",
  "url": "https://YOUR_WORKSPACE.slack.com",
  "team_id": "TXXXXXXXX"
}
```

Then re-run the command. You’ll see a browser window and a login status message. Complete the login once; future runs reuse `config/slack/storage_state.json`.

Outputs and files:
- Exports: `data/slack/exports/`
- Storage state: `config/slack/storage_state.json`
- Credentials (if captured): `config/slack/playwright_creds.json`
- Channel map (optional): `data/slack/channel_map.json`
- Detailed logs: `src/growthkit/utils/logs/slack_fetcher.log`

### 5) Gmail export — first run

Before running, place your OAuth Desktop client JSON at `config/mail/client_secret_<id>.json`.

How to obtain:
1) Google Cloud Console → APIs & Services → Credentials
2) Create OAuth client ID (Application type: Desktop app)
3) Download JSON and save as `config/mail/client_secret_<id>.json`

Run the Gmail sync:

macOS/Linux:
```bash
./.venv/bin/gk-email
```

Windows (PowerShell):
```powershell
./.venv/Scripts/gk-email
```

First run starts a local OAuth flow and creates `config/mail/token.pickle`. Exports are written to `data/mail/exports/`.

### Running tests

macOS/Linux:
```bash
./.venv/bin/python -m pytest
```

Windows (PowerShell):
```powershell
./.venv/Scripts/python -m pytest
```

### Troubleshooting

- ImportError when launching `gk-slack` or `gk-email` (e.g., “cannot import name …” or “module is not callable”):
  - Reinstall the package in editable mode: macOS/Linux `./.venv/bin/pip install -e .` or Windows `./.venv/Scripts/pip install -e .`.

- Slack: “Workspace is not configured” or placeholders still present:
  - Edit `config/slack/workspace.json` and set real `url` and `team_id` values.

- Slack: Playwright Chromium not present or page closes unexpectedly:
  - Install runtime explicitly: macOS/Linux `./.venv/bin/python -m playwright install chromium` or Windows `./.venv/Scripts/python -m playwright install chromium`.
  - If you interrupted the run (Ctrl+C) and see “Target page closed” or “Event loop is closed”, just re-run the command.

- Gmail: “No OAuth client secret JSON found”:
  - Place your file at `config/mail/client_secret_<id>.json` (Desktop app type) and try again.

### Useful paths

- Slack
  - Config: `config/slack/workspace.json`
  - State: `config/slack/storage_state.json`
  - Exports: `data/slack/exports/`
  - Logs: `src/growthkit/utils/logs/slack_fetcher.log`
- Gmail
  - OAuth secrets: `config/mail/client_secret_<id>.json`
  - Token: `config/mail/token.pickle`
  - Exports: `data/mail/exports/`

### Uninstall/reinstall (local dev)

If you update the source, it’s usually enough to keep editable mode installed. If things get out of sync, reinstall:

macOS/Linux:
```bash
./.venv/bin/pip install -e .
```

Windows (PowerShell):
```powershell
./.venv/Scripts/pip install -e .
```

