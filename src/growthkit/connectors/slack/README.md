# Slack Fetcher

Automated Playwright-powered exporter that turns any Slack conversation (channels, direct messages, multi-person DMs) into neatly formatted Markdown archives.

---

## Why does this exist?

Slack’s built-in exports are rate-limited, clunky, and omit private DMs unless you’re a Workspace Owner.  
This script lets **any logged-in user** grab conversations they have access to – using the same web session your browser already has – and stores them locally for:

* Weekly growth reports & H1 / H2 reviews
* Searchable knowledge bases
* Data & sentiment analysis
* Long-term compliance / backups

---

## Quick Start (TL;DR)

```bash
# 1. Activate (or create) a virtual-env and install the package in editable mode
pip install -e .

# 2. Run the exporter via the convenience wrapper
gk-slack
# - or - 

python -m growthkit.connectors.slack.slack_fetcher
```

Interaction steps:
1. A Chromium window launches (non-headless by default).  
2. If your default Chrome profile is already logged into your workspace, no action needed; otherwise sign in once.  
3. In the terminal, type the channel(s) you want to export, e.g. `#general` **or** `marketing, dm_with_jake` **or** `C0123ABCD`.  
4. Markdown files appear in `data/slack/exports/`.

> **Tip:** separate multiple targets with commas to export in one run.

---

## Key Files & Directories

| Path | Purpose |
|------|---------|
| `src/growthkit/connectors/slack/slack_fetcher.py` | Main script – Playwright wrapper + export logic |
| `config/slack/workspace.py` | Workspace URL & team ID |
| `config/slack/playwright_creds.json` | **Sensitive!** Auto-saved cookies & `xoxc-` / `xoxd-` tokens (refreshed hourly) |
| `config/slack/conversion_tracker.json` | Keeps the latest exported timestamp per channel so subsequent runs are incremental |
| `data/slack/exports/` | Destination folder for `*.md` conversation archives |

---

## How it works

1. **Browser session** – Starts a persistent Chromium context pointing at your regular Chrome profile (macOS path: `~/Library/Application Support/Google/Chrome/Default`).  
2. **Network interception** – Listens to `**/api/**` requests to capture fresh auth tokens & cookies.  
3. **Hybrid history fetch**  
   * **Fast path:** queries `conversations.history` & `conversations.replies` Web API directly.  
   * **Fallback:** scrolls the UI + scrapes the DOM when API data is restricted.
4. **Markdown renderer** – Converts Slack formatting, uploads, reactions, threads, etc. into friendly Markdown bullets.
5. **Incremental tracker** – Saves the newest message timestamp so the next run only appends deltas.

---

## Usage Modes

### 1. Interactive single export
Just run the script and enter one target.

### 2. Batch export
Provide a comma-separated list e.g.:
```text
#general, marketing, C01234567, dm_with_Jake_Panzer_0T3YBF
```
The script cycles through each item with one browser session.

### 3. Incremental updates
The file `config/slack/conversion_tracker.json` remembers the newest `ts` seen per channel.  Delete an entry (or the whole file) to force a full re-export.

### 4. Headless / cron job *(optional)*
Set `headless=True` in the `browser.start()` call or wrap the module in your own runner.  Make sure credentials are fresh (they expire ~1 hour).

---

## Output Format

```markdown
# #general

**Channel ID:** C0123ABCD
**Exported:** 2025-07-28 12:34:56
**Message Count:** 128

---

- **2025-07-25 14:03** *Alice* 💬 2 replies: Hello team!
- **2025-07-25 14:04** *Bob*: ↳ Sounds good 👍
- **2025-07-25 14:06** *🤖 Zapier*: Deployed build <https://example.com|v1.2.3>
```

Features:
* Converts Slack mentions (`<@U123> → @alice`, `<#C123|general> → #general`).
* Preserves bold/italic/code formatting.
* Embeds hyperlinks & file metadata.  
* Reactions summarised (e.g. `:thumbsup: 5`).
* Thread replies indented & prefixed with `↳`.

---

## Troubleshooting / FAQ

| Symptom | Fix |
|---------|-----|
| **Blank page asking to open the desktop app** | The launch screen blocker might have failed – click **“Continue in browser”** or press Escape. |
| **`Invalid Slack ID` error** | Check for typos; private channel you’re not a member of; or use the channel ID instead. |
| **No new messages exported** | The tracker file thinks you’re up-to-date – delete the channel’s entry in `conversion_tracker.json`. |
| **Playwright error about missing browsers** | Run `playwright install chromium` manually or just re-run the script (it auto-installs). |

---

## Security & Privacy

* `config/slack/playwright_creds.json` grants full API access – **do not commit** it.  It’s in `.gitignore` by default.
* Exports may contain PII and should be handled according to your organization's data-handling policy.
* Respect Slack’s and your company’s terms of service when distributing archives.

---

## Roadmap / Ideas

* CLI flags (`--headless`, `--batch-file`, `--oldest`) via `argparse`.
* HTML / PDF renderers for prettier sharing.
* Scheduled GitHub Action for nightly backups.
* NLP sentiment tagging & keyword search across exports.
