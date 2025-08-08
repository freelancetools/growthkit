# Contributing to GrowthKit

First off, thank you for taking the time to contribute!  The goal of this
document is to make the process **easy, predictable, and safe** for everyone
involved—humans, CI, and AI assistants alike.

> **Golden Rule:**
> Business logic lives in `src/growthkit/`. Wrapper scripts go in `scripts/`.
> Secrets stay in `config/`. Data goes in `data/`.

---

## 1. Getting Started

1. **Fork & Clone**
   ```bash
   git clone git@github.com:<your-fork>/GrowthKit.git
   cd GrowthKit
   ```
2. **Install Dev Dependencies**
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -e .[dev]          # installs ruff, black, mypy, pytest, pre-commit
   pre-commit install             # installs the git hooks
   ```

---

## 2. Branch Workflow

* **main** – protected, auto-deployed; no direct commits.
* **feature/<topic>** – new work (e.g. `feature/weekly-growth-charts`).
* **fix/<bug>** – hot-fixes (e.g. `fix/ga4-column-name`).
* **docs/** – documentation-only changes are welcome in their own branch.

Create your branch off `main`:
```bash
git checkout -b feature/amazing-idea
```

---

## 3. Commit Messages

```
<type>(scope): <subject>

<body>
```

* **type**: feat, fix, docs, refactor, chore, test
* **scope**: package or directory (e.g. analysis, slack, data)
* **subject**: one-liner using the imperative mood
* Wrap body at 72 chars, explain _why_ the change is needed.

---

## 4. Folder Rules (Quick Reference)

| Folder | ✅ Allowed | ❌ Forbidden |
|--------|-----------|-------------|
| `scripts/` | Thin CLI wrappers (<30 LOC) | Business logic, secrets |
| `src/growthkit/` | Pure library code, tests | Data files, env-specific config |
| `src/growthkit/utils/` | Vendored helper library (read-only) | **Any** modifications in this repo |
| `config/` | Credential **templates**, small INI/JSON | Hard-coded secrets in git |
| `data/` | Raw exports, generated reports | Source code, virtualenvs |

See the per-folder `README.md` files for full detail.

---

## 5. Code Style & Tooling

| Tool  | Command | Purpose |
|-------|---------|---------|
| **ruff** | `ruff check .` | Linting (PEP8 + extra rules) |
| **black** | `black .` | Code formatting |
| **mypy** | `mypy src/` | Static typing |
| **pytest** | `pytest` | Unit tests |

All four run automatically via **pre-commit** hooks.  Fix issues locally before
pushing.

---

## 6. Tests & Coverage

* Place tests in `tests/` mirroring the package path.
* Use fixtures over ad-hoc CSV strings; synthetic data lives in `tests/fixtures/`.
* Pull requests must keep coverage at or above the current baseline.

Run:
```bash
pytest -q
```

---

## 7. Secrets & Large Files

* Do **not** commit real tokens—only `*.template` placeholders.
* Keep files >50 MB out of git (use Git LFS or cloud storage).

---

## 8. Adding a New Directory

1. Create the folder.
2. Add a `README.md` explaining its purpose, allowed & disallowed contents.
3. Add `__init__.py` if it’s a Python package (with a top-of-file comment: _“Import-safe; no side-effects.”_)
4. Update the root README **Repository Layout** diagram.

CI will fail if the directory lacks a README.

---

## 9. Pull Request Checklist

- [ ] Code compiles & hooks pass (`pre-commit run --all-files`).
- [ ] Folder rules respected.
- [ ] Added/updated tests.
- [ ] Updated documentation / READMEs.
- [ ] No secrets or large binaries committed.
- [ ] One of: `@data-team` or `@ops-team` has been requested for review (auto via CODEOWNERS).

---

## 10. Releasing (Maintainers)

1. Bump version in `pyproject.toml`.
2. Tag & push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. GitHub Action publishes to PyPI.

---

## 11. Need Help?

Open an issue or ping in your team Slack. Happy coding!
