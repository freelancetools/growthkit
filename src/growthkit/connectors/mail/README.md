# Mail Archiving

This directory provides everything needed to **export Gmail messages to local Markdown files** so they can be searched, indexed, or included in reports.

---

## 📦  What’s inside

| File | Purpose |
|------|---------|
| `gmail_sync.py` | Core logic.  Authenticates, discovers new mail, saves each message as Markdown.  Handles **incremental sync** using Gmail’s History ID so it only processes messages once. |
| `cursor.txt` | Stores the latest History ID returned by Gmail.  Presence of this file triggers incremental mode.  If the ID is too old (or the file is missing) the script performs a full back-fill and writes a fresh cursor. |
| `scripts/email_export.py` | Tiny wrapper that simply calls `gmail_sync.main()`.  It exists so you can `python -m scripts.email_export` (or point cron at it) without worrying about package paths. |
| `data/mail/exports/` | Destination for all exported mail (`YYYYMMDD-subject-messageID.md`). |
| `config/mail/` | OAuth credentials live here.  – `client_secret_*.json` (downloaded from Google Cloud) – `token.pickle` (auto-created refresh token). |

---

## 🚀  Running it (interactive)

```bash
# activate the project’s virtualenv first
source venv/bin/activate

# run directly
python -m growthkit.connectors.mail.gmail_sync

# …or via the convenience wrapper
python scripts/email_export.py
```

On first run you will be prompted to grant the app access.  A browser window will open; after authorising, `token.pickle` will be saved so subsequent runs are fully automated.

---

## 🕑  Automating with cron (example)

```cron
0 * * * * /path/to/venv/bin/python /path/to/eskiin/scripts/email_export.py \
  >> /path/to/logs/gmail_sync.log 2>&1
```
This executes the sync hourly, logging output and **only processing new mail** thanks to the cursor mechanism.

---

## ⚙️  How it works (under the hood)

1. **Authenticate**:   Reads/refreshes `token.pickle` or launches the OAuth flow using the client-secret JSON.
2. **Determine mode**:
   * If `cursor.txt` exists → call Gmail History API (`history().list`) to fetch only messages added since that ID.
   * Else (first run) → call `users().messages().list` to enumerate *all* messages.
3. **Save messages**:   For each message ID returned, fetch the raw MIME, extract headers & body, convert HTML → Markdown when needed, run cleaning utilities, and write to `data/mail/exports/`.
4. **Update cursor**:   Writes the latest History ID so the next invocation is incremental.

The script uses the read-only scope `https://www.googleapis.com/auth/gmail.readonly`, so it **cannot modify or delete any mail** in your account.

---

## 🛠  Dependencies

* `google-api-python-client`
* `google-auth-oauthlib`
* `markitdown`
* Anything listed in `pyproject.toml`

All are installed automatically when you set up the project’s virtualenv.

---

## 📝  Notes & Troubleshooting

* **Token revoked?**  Delete `config/mail/token.pickle` and re-run the script to re-authorise.
* **History ID too old** (e.g., long inactivity) → script will automatically perform a full archive and reset the cursor.
* **File paths** are relative to the project root; you can run the script from anywhere.

Happy archiving! 🎉

