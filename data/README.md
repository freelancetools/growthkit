# `data/` — Input & Output Datasets

The `data/` hierarchy is the **scratch-space** for all CSV exports, generated
Markdown reports, and other artefacts produced or consumed by the GrowthKit
scripts. Nothing here is imported as code.

Because some files can be large or sensitive, the folder is split into
well-defined sub-directories and protected by granular `.gitignore` rules.

---

## Directory Map

| Subfolder | Role | Typical Contents |
|-----------|------|------------------|
| `ads/` | **INPUT** | Raw CSV exports from Northbeam, Google Ads, Meta Ads, GA4, etc.  Further divided into `exec-sum/`, `h1-report/`, weekly snapshots, etc. |
| `reports/` | **OUTPUT** | Generated Markdown or PDF files for executive, weekly, or H1 reports (e.g. `automated-performance-report-YYYY-MM-DD.md`). |
| `products/` | **INPUT & OUTPUT** | Intermediate product-analysis data (e.g. unattributed line-items to be labelled). |
| `slack/` | **OUTPUT** | Channel or DM exports pulled via Playwright (`exports/*.md`). |
| `mail/` | **OUTPUT** | Gmail message archives (likely JSON or EML). |
| `facebook/` | **INPUT** | Facebook ad-related JSON dumps (ad IDs, comments, page lists). |
| `transcripts/` | **OUTPUT** | `.srt`, `.vtt`, or `.md` meeting transcripts. |

Anything not fitting these categories should live in its own clearly-named
subfolder so downstream scripts can locate it reliably.

---

## What **should** live here

| ✅  | Rationale |
|----|-----------|
| **Raw exports** straight from third-party dashboards | Keep truth-on-disk for reproducible analysis. |
| **Derived CSVs** that represent cleaned or transformed datasets | So long as they’re <= ~50 MB and genuinely needed for version control. |
| **Generated reports** (`*.md`, `*.pdf`) for end-users. |
| **Small lookup tables / JSON blobs** that are data, not config (e.g. `rolodex.json`). |

---

## What **should _not_** live here

| ❌  | Why |
|----|----|
| Gigantic raw exports (>50 MB) or proprietary customer data | Push to cloud bucket or use Git LFS; keep repo slim & compliant. |
| Temporary scratch files (`*.tmp`, Jupyter notebook checkpoints) | Clutters history; they belong in `.gitignore` or `/tmp`. |
| Python source code, virtual environments, compiled artefacts | This folder is for **data only**.

---

## Tips for Managing Large Datasets

1. **Git LFS** – If you _must_ version control >50 MB files, track them with Git LFS.
2. **Deterministic filenames** – Scripts should write predictable filenames
   (`{report_type}-{YYYY-MM-DD}.md`) so CI/CD can pick them up.
3. **Automated cleanup** – Consider a cron/job or `make clean-data` target to
   archive or purge stale intermediate files.
