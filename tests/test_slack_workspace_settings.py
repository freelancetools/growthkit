"""
Tests for Slack workspace settings loading in `growthkit.connectors.slack.slack_fetcher`.

We stub Playwright to avoid heavy/runtime deps at import, and chdir to a temp
directory so config files are written/read in isolation.
"""

import sys
import json
import types
import importlib
from pathlib import Path

import pytest


def _import_slack_fetcher_with_stubs():
    """Import slack_fetcher with a stubbed Playwright async API."""
    # Stub playwright APIs
    playwright_pkg = types.ModuleType("playwright")
    playwright_async_api = types.ModuleType("playwright.async_api")
    playwright_sync_api = types.ModuleType("playwright.sync_api")

    class _Dummy:  # simple placeholder type for Page/Request/Route/Error/TimeoutError
        pass

    def _async_playwright():  # not used in these tests
        return None

    playwright_async_api.async_playwright = _async_playwright
    playwright_async_api.Page = _Dummy
    playwright_async_api.Request = _Dummy
    playwright_async_api.Route = _Dummy
    playwright_async_api.Error = _Dummy
    playwright_async_api.TimeoutError = _Dummy

    # sync_api stub: minimal sync_playwright context manager and Error class
    class _PlaywrightError(Exception):
        pass

    class _Browser:
        def close(self):
            return None

    class _Chromium:
        def launch(self, headless=True):
            return _Browser()

    class _PlaywrightCtx:
        def __enter__(self):
            return types.SimpleNamespace(chromium=_Chromium())

        def __exit__(self, exc_type, exc, tb):
            return False

    def _sync_playwright():
        return _PlaywrightCtx()

    playwright_sync_api.sync_playwright = _sync_playwright
    playwright_sync_api.Error = _PlaywrightError

    sys.modules.setdefault("playwright", playwright_pkg)
    sys.modules.setdefault("playwright.async_api", playwright_async_api)
    sys.modules.setdefault("playwright.sync_api", playwright_sync_api)

    return importlib.import_module("growthkit.connectors.slack.slack_fetcher")


def test_load_workspace_settings_placeholder_raises(tmp_path, monkeypatch):
    mod = _import_slack_fetcher_with_stubs()

    # Work in a temp dir so config lives under tmp_path/config/slack/workspace.json
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError):
        mod.load_workspace_settings()

    # Ensure the default file was created with placeholders
    ws_path = Path("config/slack/workspace.json")
    assert ws_path.exists()
    data = json.loads(ws_path.read_text(encoding="utf-8"))
    assert data["url"].startswith("https://YOUR_WORKSPACE")
    assert data["team_id"].startswith("T")


def test_load_workspace_settings_valid_values(tmp_path, monkeypatch):
    mod = _import_slack_fetcher_with_stubs()

    monkeypatch.chdir(tmp_path)

    ws_path = Path("config/slack/workspace.json")
    ws_path.parent.mkdir(parents=True, exist_ok=True)
    ws_path.write_text(
        json.dumps({"url": "https://acme.slack.com", "team_id": "T123456"}),
        encoding="utf-8",
    )

    settings = mod.load_workspace_settings()
    assert settings.url == "https://acme.slack.com"
    assert settings.team_id == "T123456"
    assert settings.app_client_url == "https://app.slack.com/client/T123456"
