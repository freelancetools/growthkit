# `growthkit/` — Core Python Package

This folder is the **installable source distribution** for the GrowthKit
report toolkit. Anything placed here is shipped to PyPI (or whichever package
index you upload to) and can be imported via:

```python
import growthkit
```

Therefore, keep the code here **clean, generic, and side-effect free on
import**.

---

## Current Sub-packages

| Sub-package | Responsibility |
|-------------|---------------|
| `reports/` | Report generation logic (executive, weekly, H1, etc.). Pure functions that read CSVs & return Markdown or DataFrames. |
| `connectors/facebook/` | Lightweight FB (Meta) Marketing API models & helpers (e.g. `Comment`, `engine.py`, `schema.py`). |
| `connectors/mail/` | Gmail archive extraction logic. |
| `connectors/slack/` | Playwright-based Slack export tooling plus config scaffolding. |
| `utils/` | Re-usable helpers (ANSI colours, CLI shell, file I/O abstractions, logging). |
| `reports/product_data.py` | Canonical list of products / categories used by report modules. _Data-only_ — no heavy imports. |

---

## What **should** live here

| ✅  | Description |
|----|-------------|
| Pure, import-time safe modules | No network calls, file system writes, or environment prompts in global scope. |
| Re-usable business logic & analytics | Functions/classes that can be unit-tested in isolation. |
| Typed data models & schemas | Pydantic/dataclass definitions used across reports. |
| Utilities that are reused by multiple sub-packages. |
| Data constants that are small, version-controlled, and needed at runtime (e.g. `product_data.py`). |

---

## What **should _not_** live here

| ❌  | Why |
|----|-----|
| One-off CLI wrappers or `if __name__ == "__main__"` entry-points | Put thin wrappers into `scripts/` or expose a `console_scripts` entry-point instead. |
| Personal or environment-specific configuration | Use the top-level `config/` directory; keep the package generic. |
| Secrets, API keys, OAuth tokens, Playwright credentials, etc. | Packages published to PyPI are public! Use `config/` + `.gitignore`. |
| Large data dumps, CSV exports, or generated artefacts | These belong in `data/`, **never** inside the Python package. |
| Heavy third-party dependencies that are only needed by a single report script | Vend them behind an optional extra or relocate the script. |

---

## Import Safety Checklist

Before adding a new module, run through this list:

1. **No side-effects on import**  → move runtime code to a `main()` function.
2. **Unit tests pass without network or file system access.**
3. **Type-check passes (`mypy`)**  → keep public APIs well-typed.
4. **Docs / docstrings** are added so other engineers know how to use it.

---

## Adding a New Report Type (Example)

1. Create a new module inside `reports/` – e.g. `reports/monthly_customer_mix.py`.
2. Implement a public `main()` that handles CLI arg parsing.
3. Export helper functions/classes at module-level for reuse in notebooks.
4. Add a new thin wrapper in `scripts/` (`report_monthly_mix.py`) _or_
   expose a console entry point via `pyproject.toml`.
5. Document it in the root `README.md` under **Running Reports**.

By following these guidelines the public package remains clean while still
allowing quick CLI execution via the `scripts/` wrappers.
