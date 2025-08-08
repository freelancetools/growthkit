#!/usr/bin/env python3
"""
Slack conversation extractor using Playwright.
"""

import os
import re
import time
import json
import asyncio
import argparse
import traceback
import urllib.parse
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, UTC
from http.cookies import SimpleCookie
from typing import Dict, List, Any, Optional

from playwright.async_api import async_playwright, Page, Request, Route, Error, TimeoutError
import requests

from growthkit.utils.style import ansi
from growthkit.utils.logs import report
from growthkit.connectors.slack._playwright_setup import ensure_chromium_installed

# Initialize logging
logger = report.settings(__file__)


# -------------- Config -------------------------------------------------------
# Updated path to align with new repository structure
EXPORT_DIR = Path("data/slack/exports")
ROLODEX_FILE = Path("data/rolodex.json")
TRACK_FILE = Path("config/slack/conversion_tracker.json")
CREDENTIALS_FILE = Path("config/slack/playwright_creds.json")
STORAGE_STATE_FILE = Path("config/slack/storage_state.json")
CHANNEL_MAP_FILE = Path("data/slack/channel_map.json")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

@dataclass(frozen=True)
class WorkspaceSettings:
    """Workspace settings for Slack fetcher"""
    url: str
    team_id: str

    @property
    def app_client_url(self) -> str:
        """URL for the Slack app client"""
        return f"https://app.slack.com/client/{self.team_id}"


def load_workspace_settings() -> WorkspaceSettings:
    """Create/validate workspace config and return settings object.

    This mirrors the safety in `scripts/slack_export.py` by generating a
    default `config/slack/workspace.py` if missing, then importing and
    validating it before use.
    """
    from growthkit.connectors.slack._init_config import ensure_workspace_config

    # Create default config file if missing
    ensure_workspace_config()

    # Import after ensuring the file exists
    from config.slack.workspace import validate_workspace, CONFIG

    # Validate values are not placeholders
    validate_workspace()

    # Return an immutable settings object used throughout this module
    return WorkspaceSettings(url=CONFIG.url, team_id=CONFIG.team_id)

# -------------- Conversation Type Enum ---------------------------------------

class ConversationType(Enum):
    """Enum for different types of Slack conversations."""
    CHANNEL = "channel"
    DM = "dm"
    MULTI_PERSON_DM = "multi_person_dm"
    UNKNOWN = "unknown"


# -------------- Conversation Data Structure ---------------------------------

class ConversationInfo:
    """Data structure to hold information about a Slack conversation (channel, DM, etc.)."""
    def __init__(self,
                 name: str,
                 conversation_id: str,
                 conversation_type: ConversationType,
                 is_private: bool = False,
                 member_count: int = 0,
                 members: List[str] = None):
        self.name = name
        self.id = conversation_id
        self.conversation_type = conversation_type
        self.is_private = is_private
        self.member_count = member_count
        self.members = members or []

    def __repr__(self):
        type_symbol = {
            ConversationType.CHANNEL: "#",
            ConversationType.DM: "@",
            ConversationType.MULTI_PERSON_DM: "👥",
            ConversationType.UNKNOWN: "?",
        }
        symbol = type_symbol.get(self.conversation_type, "?")
        private_marker = "🔒" if self.is_private else ""
        member_info = f" ({self.member_count} members)" if self.member_count > 0 else ""

        display_name = self.name or ""
        if display_name.startswith(symbol):
            display_name = display_name[len(symbol):]

        return f"{symbol}{display_name}{private_marker}{member_info}"

# ---------------- Timing Helper -------------------------------------------
class Stopwatch:
    """Tiny helper for ad-hoc performance tracing (seconds precision)."""
    def __init__(self, prefix: str = "") -> None:
        self.t0 = time.perf_counter()
        self.prefix = prefix

    def lap(self, label: str) -> float:
        """Log the elapsed time since the stopwatch was created."""
        elapsed = time.perf_counter() - self.t0
        logger.debug("%s%s: %.2fs", self.prefix, label, elapsed)
        print(f"⏱️  {self.prefix}{label}: {ansi.yellow}{elapsed:.2f}s{ansi.reset}", flush=True)
        return elapsed

# -------------- Credential Management ----------------------------------------

class SlackCredentials:
    """Manages Slack authentication credentials including cookies and tokens."""
    def __init__(self):
        self.cookies: Dict[str, str] = {}
        self.token: str = ""
        self.user_id: str = ""
        self.team_id: str = ""
        self.last_updated: float = 0

    def is_valid(self) -> bool:
        """Check if credentials are recent and have required fields."""
        if not self.token or not self.cookies:
            return False
        # Consider credentials stale after 1 hour
        return (time.time() - self.last_updated) < 3600

    def save(self):
        """Save credentials to file."""
        data = {
            "cookies": self.cookies,
            "token": self.token,
            "user_id": self.user_id,
            "team_id": self.team_id,
            "last_updated": self.last_updated
        }
        CREDENTIALS_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')

    @classmethod
    def load(cls) -> 'SlackCredentials':
        """Load credentials from file."""
        creds = cls()
        if CREDENTIALS_FILE.exists():
            try:
                data = json.loads(CREDENTIALS_FILE.read_text(encoding='utf-8'))
                creds.cookies = data.get("cookies", {})
                creds.token = data.get("token", "")
                creds.user_id = data.get("user_id", "")
                creds.team_id = data.get("team_id", "")
                creds.last_updated = data.get("last_updated", 0)
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️  Error loading credentials: {e}")
        return creds

    def update_from_request(self, request: Request, response_data: Dict[str, Any] = None):
        """Update credentials from intercepted request."""
        # Extract token from request
        if request.method == "POST":
            try:
                post_data = request.post_data
                if post_data and "token" in post_data:
                    # Extract token from form data
                    if "xoxc-" in post_data:
                        token_match = re.search(r'(xoxc-[a-zA-Z0-9-]+)', post_data)
                        if token_match:
                            self.token = token_match.group(1)
                    # Capture any token that starts with xox(c|p|b|s|e)-
                    token_match = re.search(r'(xox[a-z]-[a-zA-Z0-9-]+)', post_data)
                    if token_match:
                        self.token = token_match.group(1)
            except (AttributeError, TypeError, ValueError):
                pass

        # Extract from headers or cookies
        headers = request.headers
        if "cookie" in headers:
            cookie_str = headers["cookie"]
            # Parse cookies
            for cookie_pair in cookie_str.split(";"):
                if "=" in cookie_pair:
                    key, value = cookie_pair.strip().split("=", 1)
                    self.cookies[key] = value

                    # Extract token from 'd' cookie if present
                    if key == "d" and value and not self.token:
                        try:
                            decoded = urllib.parse.unquote(value)
                            if decoded.startswith(('xox',)):
                                # cookie sometimes holds xoxd- or xoxc-/xoxe-, accept any
                                self.token = decoded
                        except (ValueError, TypeError):
                            pass

        # Update from response data if available
        if response_data:
            if "user_id" in response_data:
                self.user_id = response_data["user_id"]
            if "team_id" in response_data:
                self.team_id = response_data["team_id"]

        if self.token:  # Only update timestamp if we got something useful
            self.last_updated = time.time()


# -------------- Playwright Browser Manager ----------------------------------

class SlackBrowser:
    """Manages a Playwright browser instance for automated Slack data extraction."""
    def __init__(self, settings: WorkspaceSettings):
        self.page: Optional[Page] = None
        self.context = None
        self.browser = None
        self.credentials = SlackCredentials.load()
        self.intercepted_data: List[Dict[str, Any]] = []
        self.user_mappings: Dict[str, str] = {}
        self.channel_mappings: Dict[str, str] = {}
        self.settings = settings
        self.use_storage_state: bool = True
        self._dialog_dismiss_enabled: bool = True

    async def start(
        self,
        headless: bool = False,
        use_storage_state: bool = True,
        fresh: bool = False,
    ):
        """Start browser and setup interception.

        Always uses an isolated Playwright context. Optionally restores session from
        a saved storage state file and/or injects cookies as a fallback.
        """
        self.use_storage_state = use_storage_state
        playwright = await async_playwright().start()

        # Always start a fresh, non-persistent browser
        self.browser = await playwright.chromium.launch(headless=headless)
        user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/137.0.0.0 Safari/537.36"
        )

        # Prefer storage_state if enabled and available (and not fresh)
        if use_storage_state and not fresh and STORAGE_STATE_FILE.exists():
            self.context = await self.browser.new_context(
                user_agent=user_agent,
                storage_state=str(STORAGE_STATE_FILE),
            )
            print(f"🔐 Loaded storage state from {STORAGE_STATE_FILE}")
        else:
            # Create an empty context
            self.context = await self.browser.new_context(user_agent=user_agent)

            # Inject cookies as a best-effort fallback, unless fresh
            if not fresh and self.credentials.cookies:
                cookies = []
                for name, value in self.credentials.cookies.items():
                    cookies.append({
                        "name": name,
                        "value": value,
                        "domain": ".slack.com",
                        "path": "/",
                    })
                    cookies.append({
                        "name": name,
                        "value": value,
                        "domain": "app.slack.com",
                        "path": "/",
                    })
                await self.context.add_cookies(cookies)
                print("🍪 Injected cookies into fresh context")

        # Always create a new page in this isolated context
        self.page = await self.context.new_page()
        print("📄 Created new browser page")

        # Setup request/response interception
        await self.page.route("**/api/**", self._intercept_api_call)
        print("🔍 Set up API interception for **/api/**")

        # Enable verbose network logging by default for debugging
        # Request handler is sync; response uses async task to avoid blocking
        self.page.on("request", self._on_request_event)
        self.page.on("response", lambda r: asyncio.create_task(self._on_response_event(r)))

        # Auto-dismiss native app-open dialogs if they appear
        async def _on_dialog(dialog):
            try:
                logger.info("DIALOG %s: %s", dialog.type, dialog.message)
                if self._dialog_dismiss_enabled:
                    await dialog.dismiss()
                    logger.info("Dialog dismissed")
                else:
                    await dialog.accept()
            except (Error, TimeoutError):
                pass

        self.page.on("dialog", lambda d: asyncio.create_task(_on_dialog(d)))

    async def _save_storage_state_if_enabled(self) -> None:
        """Persist current storage state if enabled."""
        try:
            if self.use_storage_state and self.context is not None:
                STORAGE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
                await self.context.storage_state(path=str(STORAGE_STATE_FILE))
                logger.debug("Saved storage state to %s", STORAGE_STATE_FILE)
                print(f"💾 Saved storage state → {STORAGE_STATE_FILE}")
        except (Error, TimeoutError, OSError, ValueError) as e:
            logger.warning("Failed to save storage state: %s", e)

    async def _intercept_api_call(self, route: Route, request: Request):
        """Intercept Slack API calls to extract credentials and data."""
        try:
            # Continue the request
            response = await route.fetch()

            # Update credentials from this request
            self.credentials.update_from_request(request)

            # Debug: Log all API calls
            if "/api/" in request.url:
                logger.debug("Intercepted API call: %s", request.url)

            # Capture Set-Cookie from response headers to improve credential capture
            try:
                headers = response.headers
                set_cookie = headers.get("set-cookie") if isinstance(headers, dict) else None
                if set_cookie:
                    sc = SimpleCookie()
                    sc.load(set_cookie)
                    for morsel in sc.values():
                        name = morsel.key
                        value = morsel.value
                        if name and value:
                            self.credentials.cookies[name] = value
                            # Token occasionally rides in 'd' cookie or similar
                            if name == "d" and value and not self.credentials.token:
                                try:
                                    decoded = urllib.parse.unquote(value)
                                    if decoded.startswith(('xox',)):
                                        self.credentials.token = decoded
                                except (ValueError, TypeError):
                                    pass
                    self.credentials.last_updated = time.time()
            except Exception:
                pass

            # If this is an API call we're interested in, store the response
            if any(endpoint in request.url for endpoint in [
                "conversations.history", "conversations.list", "users.list",
                "conversations.info", "conversations.replies", "conversations.listPrefs",
                "conversations.browse", "conversations.search", "channels.list",
                "channels.info", "channels.browse", "channels.search",
                "client.boot", "client.counts", "rtm.start", "rtm.connect",
                "team.info", "workspace.info", "api",  # Include any API call
                # Sign-in/magic code endpoints that indicate auth state
                "signin.", "signup.", "auth.captcha", "auth.verify", "auth.magic"
            ]):
                try:
                    response_text = await response.text()
                    response_data = json.loads(response_text)

                    self.intercepted_data.append({
                        "url": request.url,
                        "method": request.method,
                        "post_data": request.post_data,
                        "response": response_data,
                        "timestamp": time.time()
                    })

                    logger.debug("Stored API response: %s (%d bytes)", request.url, len(response_text))

                    # Update credentials from response if it contains user/team info
                    self.credentials.update_from_request(request, response_data)

                except json.JSONDecodeError as e:
                    print(f"⚠️  Error parsing API response: {e}")

            # Continue with the response
            await route.fulfill(response=response)

        except (TimeoutError, Error) as e:
            print(f"⚠️  Error intercepting request: {e}")
            await route.continue_()

    # -------------- Network logging helpers ----------------------------------
    def _classify_slack_url(self, url: str) -> str:
        """Return a small tag describing the kind of Slack URL for log context."""
        try:
            if not url:
                return "other"
            if "/api/" in url and ".slack.com" in url:
                return "api"
            if "account.slack.com" in url:
                return "account"
            if "app.slack.com" in url:
                return "app"
            if ".slack.com" in url and ("challenge" in url or "captcha" in url):
                return "challenge"
            if ".slack.com" in url and ("signin" in url or "login" in url or "verify" in url):
                return "signin"
            if ".slack.com" in url:
                return "workspace"
            return "other"
        except (AttributeError, ValueError, TypeError):
            return "other"

    def _on_request_event(self, request: Request) -> None:
        """Lightweight request logger – avoids awaiting to keep perf overhead low."""
        try:
            url = request.url
            method = request.method
            rtype = request.resource_type
            tag = self._classify_slack_url(url)
            logger.info("HTTP REQ %s %s [%s] type=%s", method, url, tag, rtype)
        except (Error, TimeoutError, AttributeError):
            pass

    async def _on_response_event(self, response) -> None:
        """Response logger – captures status and content-type for debugging."""
        try:
            url = response.url
            status = response.status
            headers = response.headers or {}
            content_type = headers.get("content-type")
            tag = self._classify_slack_url(url)
            logger.info("HTTP RES %s %s [%s] ct=%s", status, url, tag, content_type)
        except (Error, TimeoutError, AttributeError):
            pass

    async def _is_login_or_captcha_visible(self) -> bool:
        """Best-effort detection of Slack login/magic-code/captcha screens.

        Never navigates; only inspects the current page URL and DOM.
        """
        if not self.page:
            return False

        try:
            url = self.page.url
        except (Error, AttributeError):
            url = ""

        # URL heuristics
        url_indicators = [
            "signin", "login", "account.slack.com", "verify", "challenge", "captcha",
        ]
        if any(ind in url for ind in url_indicators):
            return True

        # DOM heuristics: common login/magic-code/captcha elements
        selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[type="password"]',
            '[data-qa="signin_form"]',
            '[data-qa="signin_button"]',
            # Magic code / OTP inputs
            'input[name="pin"]',
            '[data-qa="magic_code_input"]',
            'input[autocomplete="one-time-code"]',
            # Captcha iframes
            'iframe[src*="hcaptcha"]',
            'iframe[src*="recaptcha"]',
            # Generic textual hints
            ':text-is("Enter your code")',
            ':text-is("We sent you a code")',
            ':text-is("Verify your identity")',
            ':text-is("Just a moment")',
        ]
        try:
            for sel in selectors:
                el = await self.page.query_selector(sel)
                if el:
                    return True
        except (TimeoutError, Error):
            # Non-fatal – if selectors fail, we simply don't detect
            pass
        return False

    async def _is_authenticated(self) -> bool:
        """Confirm authenticated session via DOM or definitive API payloads.

        - Prefer DOM workspace selectors
        - Otherwise, look for specific API responses that only occur post-login
        """
        if not self.page:
            return False

        # DOM indicators of a loaded workspace
        dom_selectors = [
            '[data-qa="workspace_name"]', '[data-qa="team_name"]', '.p-ia__sidebar',
            '.p-channel_sidebar', '.p-workspace__sidebar', '.c-team_sidebar',
            '.c-workspace_sidebar', '[data-qa="sidebar"]', '.c-message_input',
            '.p-message_input', '[data-qa="message_input"]',
        ]
        for sel in dom_selectors:
            try:
                el = await self.page.query_selector(sel)
                if el:
                    return True
            except (TimeoutError, Error):
                continue

        # API indicators: look for specific endpoints in intercepted data
        definitive_apis = ["client.userBoot", "client.counts", "team.info", "users.prefs"]
        for data in self.intercepted_data:
            url = data.get("url", "")
            resp = data.get("response", {})
            if any(api in url for api in definitive_apis) and isinstance(resp, dict) and resp.get("ok"):
                # Ensure the response contains expected structures
                keys = set(resp.keys())
                if ("users" in keys) or ("team" in keys) or ("channels" in keys):
                    return True

        return False

    def _on_app_client(self) -> bool:
        """Return True if the current page is already the app client for this TEAM_ID."""
        try:
            if not self.page:
                return False
            url = self.page.url
            return ("app.slack.com/client/" in url) and (self.settings.team_id in url)
        except (Error, AttributeError):
            return False

    async def _wait_for_manual_login(self, timeout_seconds: int = 300) -> bool:
        """Allow the user to complete interactive login without navigating away.

        Periodically checks for authenticated state and returns when detected or timeout.
        """
        if not self.page:
            return False

        print("🔐 Login UI detected. Waiting for you to complete sign-in…")
        print(f"   We'll monitor for up to {timeout_seconds//60} minutes and continue automatically once you're in.")

        start = time.time()
        while (time.time() - start) < timeout_seconds:
            try:
                # Give the page a moment for any transitions
                await self.page.wait_for_timeout(1000)
            except (TimeoutError, Error):
                pass

            # If authenticated, persist state and continue
            if await self._is_authenticated():
                await self._save_storage_state_if_enabled()
                await self.save_credentials()
                return True

            # If still on login/captcha, keep waiting; don't navigate
            # Small extra sleep to avoid busy loop
            await asyncio.sleep(0.5)

        print("⏳ Login wait timed out. Still not authenticated.")
        return False

    async def ensure_logged_in(self) -> bool:
        """Ensure we're logged in to Slack workspace."""
        if not self.page:
            return False

        try:
            # Navigate to the workspace
            print(f"🌐 Navigating to {self.settings.url}")
            sw = Stopwatch("login ")
            await self.page.goto(self.settings.url)
            sw.lap("page.goto")

            # First, try to bypass any launch screen that tries to open the desktop app
            await self._bypass_launch_screen()
            sw.lap("bypass")

            # Check if we're already logged in by waiting for API calls
            print("⏳ Waiting for workspace to load (networkidle)…")
            try:
                await self.page.wait_for_load_state("networkidle", timeout=6000)
            except (TimeoutError, Error):
                # Network might stay busy; continue anyway
                pass
            sw.lap("networkidle")

            print("   Checking authentication status…")
            await self.page.wait_for_timeout(500)  # brief pause to let API calls begin
            sw.lap("post-check 0.5s")

            # If we're already on the app client, we're done
            if self._on_app_client():
                await self._save_storage_state_if_enabled()
                await self.save_credentials()
                return True

            # If login or captcha UI is visible, wait for user to complete, then prefer app client
            if await self._is_login_or_captcha_visible():
                success = await self._wait_for_manual_login(timeout_seconds=600)
                if success:
                    # If authenticated and not already on app client, open app client
                    if not self._on_app_client():
                        try:
                            await self.page.goto(self.settings.app_client_url, timeout=15000)
                            await self.page.wait_for_timeout(1500)
                        except (TimeoutError, Error):
                            pass
                    if self._on_app_client() or await self._is_authenticated():
                        await self._save_storage_state_if_enabled()
                        await self.save_credentials()
                        return True
                # If we timed out, continue with additional checks below

            # Fallback: Try to find elements that indicate we're logged in
            await self.page.wait_for_timeout(3000)

            logged_in_selectors = [
                '[data-qa="workspace_name"]',
                '[data-qa="team_name"]',
                '.p-ia__sidebar',
                '.p-channel_sidebar',
                '.p-workspace__sidebar',
                '.c-team_sidebar',
                '.c-workspace_sidebar',
                # More generic selectors
                '[data-qa="sidebar"]',
                '.c-message_input',
                '.p-message_input',
                '[data-qa="message_input"]'
            ]

            for selector in logged_in_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=2000)
                    if element:
                        print(f"✅ Login confirmed via DOM element: {selector}")
                        return True
                except (TimeoutError, Error):  # Playwright timeout or other selector errors
                    continue

            # As a last check, only treat API activity as authenticated if we saw
            # definitive post-login endpoints with ok:true OR signin success
            definitive_apis = ["client.userBoot", "client.counts", "team.info", "users.prefs"]
            for data in self.intercepted_data:
                url = data.get("url", "")
                resp = data.get("response", {})
                if any(api in url for api in definitive_apis) and isinstance(resp, dict) and resp.get("ok"):
                    print(f"✅ Confirmed login via API: {url}")
                    await self._save_storage_state_if_enabled()
                    await self.save_credentials()
                    return True
                # Sign-in success on workspace domain (pre-app) – treat as authenticated
                if ("signin." in url or "signup." in url or "auth.magic" in url or "auth.verify" in url) and isinstance(resp, dict) and resp.get("ok"):
                    print(f"✅ Sign-in completed on workspace domain: {url}")
                    # Open app client only if not already there
                    if not self._on_app_client():
                        try:
                            await self.page.goto(self.settings.app_client_url, timeout=15000)
                            await self.page.wait_for_timeout(1500)
                        except (TimeoutError, Error):
                            pass
                    if await self._is_authenticated():
                        await self._save_storage_state_if_enabled()
                        await self.save_credentials()
                        return True

            # Check current URL for login indicators
            current_url = self.page.url
            if "signin" in current_url or "login" in current_url:
                print("🔐 Login page detected. Please authenticate manually.")
                print("💡 This script requires existing authentication via browser profile.")
                return False

            # If we can navigate and have some API activity, consider it logged in
            if "slack.com" in current_url and len(self.intercepted_data) > 0:
                print("✅ Login assumed successful (on Slack domain with API activity)")
                await self._save_storage_state_if_enabled()
                await self.save_credentials()
                return True

            print("❌ Unable to verify login status")
            return False

        except (TimeoutError, Error) as e:
            print(f"❌ Error checking login status: {e}")
            return False

    def _parse_conversation_data(self, conv_data: Dict[str, Any]) -> Optional[ConversationInfo]:
        """Parse conversation data and return ConversationInfo object."""
        if not isinstance(conv_data, dict):
            return None

        name = conv_data.get("name", "")
        conv_id = conv_data.get("id", "")

        if not conv_id:
            return None

        # Get user and channel mappings for better naming
        user_mappings = getattr(self, 'user_mappings', {})
        channel_mappings = getattr(self, 'channel_mappings', {})

        # Determine conversation type based on ID and other properties
        conversation_type = ConversationType.UNKNOWN

        # Check for multi-person DM patterns in the name FIRST (before checking ID)
        if name and ("mpdm-" in name or "--" in name):
            conversation_type = ConversationType.MULTI_PERSON_DM
            # Fix name format for multi-person DMs
            if not name.startswith("@"):
                name = f"@{name}"

        # Check if it's a DM (starts with D)
        elif conv_id.startswith('D'):
            # Check if it's a multi-person DM
            if conv_data.get("is_mpim", False) or conv_data.get("is_group", False):
                conversation_type = ConversationType.MULTI_PERSON_DM
                # Try to get user names for multi-person DM
                if not name:
                    user_ids = conv_data.get("members", [])
                    if user_ids:
                        user_names = []
                        for user_id in user_ids[:3]:  # Limit to first 3 users
                            if user_id in user_mappings:
                                user_names.append(user_mappings[user_id])
                            else:
                                user_names.append(f"user_{user_id[-6:]}")
                        if user_names:
                            name = f"@{'_'.join(user_names)}"
                        else:
                            name = f"@mpim_{conv_id}"
                    else:
                        name = f"@mpim_{conv_id}"
            else:
                # Regular DM
                conversation_type = ConversationType.DM
                if not name:
                    # Try to get the other user's name
                    user_id = conv_data.get("user", "")
                    if user_id and user_id in user_mappings:
                        name = f"@{user_mappings[user_id]}"
                    else:
                        name = f"@dm_{conv_id}"

        # Check if it's a channel (starts with C)
        elif conv_id.startswith('C'):
            conversation_type = ConversationType.CHANNEL
            # Use channel mapping if available
            if conv_id in channel_mappings:
                name = channel_mappings[conv_id]
            elif name:
                name = f"#{name}"
            else:
                name = f"#channel_{conv_id}"

        # Check if it's a group (starts with G)
        elif conv_id.startswith('G'):
            conversation_type = ConversationType.MULTI_PERSON_DM
            if conv_id in channel_mappings:
                name = channel_mappings[conv_id]
            elif name:
                name = f"#{name}"
            else:
                name = f"#group_{conv_id}"

        # Fallback naming
        if not name:
            if conversation_type == ConversationType.CHANNEL:
                name = f"#channel_{conv_id}"
            elif conversation_type == ConversationType.DM:
                name = f"@dm_{conv_id}"
            elif conversation_type == ConversationType.MULTI_PERSON_DM:
                name = f"@group_{conv_id}"
            else:
                name = f"unknown_{conv_id}"

        # Get member count
        member_count = 0
        if "num_members" in conv_data:
            member_count = conv_data["num_members"]
        elif "members" in conv_data and isinstance(conv_data["members"], list):
            member_count = len(conv_data["members"])

        # Get members list
        members = []
        if "members" in conv_data and isinstance(conv_data["members"], list):
            members = conv_data["members"]

        # Check if private
        is_private = conv_data.get("is_private", False)

        return ConversationInfo(
            name=name,
            conversation_id=conv_id,
            conversation_type=conversation_type,
            is_private=is_private,
            member_count=member_count,
            members=members
        )



    async def get_channel_list(self) -> Dict[str, str]:
        """Get channel list from processed files and API data."""
        print("🔗 Getting channel list...")

        channels: Dict[str, str] = {}
        # Pre-populate with entries from persistent channel map
        try:
            for cid, cname in self._load_channel_map().items():
                if cid and cname:
                    channels[cid] = f"#{cname.lstrip('#')}"
        except (IOError, json.JSONDecodeError) as exc:
            logger.debug("Failed to load persistent channel map: %s", exc)

        try:
            # Check processed directories for known channel names
            processed_dir = os.path.join(os.path.dirname(__file__), 'processed')
            if os.path.exists(processed_dir):
                for item in os.listdir(processed_dir):
                    item_path = os.path.join(processed_dir, item)
                    if os.path.isdir(item_path):
                        # This is a known channel/DM name
                        if item.startswith('sb-'):
                            # This looks like a channel name
                            channels[item] = f"#{item}"
                        elif item.startswith('dm_'):
                            # This is a DM name
                            channels[item] = f"@{item}"

            # Also check exports directory
            if EXPORT_DIR.exists():
                for item in os.listdir(EXPORT_DIR):
                    if item.endswith('.md'):
                        # Remove .md extension
                        name = item[:-3]
                        if name.startswith('sb-'):
                            channels[name] = f"#{name}"
                        elif name.startswith('dm_'):
                            channels[name] = f"@{name}"

            # --------------- Direct Web API list fast-path -----------------
            if self.credentials.token and self.credentials.cookies:
                try:
                    cursor = None
                    while True:
                        payload = {
                            "limit": 1000,
                            "types": "public_channel,private_channel"
                        }
                        if cursor:
                            payload["cursor"] = cursor
                        resp = self._api_post_sync("conversations.list", payload)
                        if not resp.get("ok"):
                            break
                        for ch in resp.get("channels", []):
                            if isinstance(ch, dict):
                                ch_id = ch.get("id")
                                ch_name = ch.get("name")
                                if ch_id and ch_name:
                                    channels[ch_id] = f"#{ch_name}"
                        cursor = resp.get("response_metadata", {}).get("next_cursor")
                        if not cursor:
                            break
                    logger.debug("Loaded %d channels via conversations.list fast path", len(channels))
                except requests.exceptions.RequestException as exc:
                    logger.debug("conversations.list fast path failed: %s", exc)

            # Extract channels from API data - enhanced extraction
            for data in self.intercepted_data:
                url = data.get("url", "")
                response = data.get("response", {})

                if not isinstance(response, dict):
                    continue

                # Check search.modules.channels - this might contain channel names
                if "search.modules.channels" in url and response.get("ok"):
                    logger.debug("Processing search.modules.channels response")
                    if "channels" in response:
                        search_channels = response["channels"]
                        if isinstance(search_channels, list):
                            for ch in search_channels:
                                if isinstance(ch, dict):
                                    ch_id = ch.get("id", "")
                                    ch_name = ch.get("name", "")
                                    if ch_id and ch_name:
                                        channels[ch_id] = f"#{ch_name}"
                                        logger.debug("Found search channel: %s -> #%s", ch_id, ch_name)

                # Check client.counts response - it showed 4 channels
                if "client.counts" in url and response.get("ok"):
                    logger.debug("Processing client.counts response")
                    if "channels" in response:
                        counts_channels = response["channels"]
                        if isinstance(counts_channels, dict):
                            for ch_id, ch_data in counts_channels.items():
                                if isinstance(ch_data, dict):
                                    ch_name = ch_data.get("name", "")
                                    if ch_name:
                                        channels[ch_id] = f"#{ch_name}"
                                        logger.debug("Found counts channel: %s -> #%s", ch_id, ch_name)
                                    else:
                                        # Try other fields that might contain the name
                                        fields_to_try = [
                                            "display_name",
                                            "real_name",
                                            "canonical_name"
                                        ]
                                        for field in fields_to_try:
                                            if field in ch_data:
                                                ch_name = ch_data[field]
                                                if ch_name:
                                                    channels[ch_id] = f"#{ch_name}"
                                                    logger.debug("Found counts channel (%s): %s -> #%s", field, ch_id, ch_name)
                                                    break
                        elif isinstance(counts_channels, list):
                            for ch in counts_channels:
                                if isinstance(ch, dict):
                                    ch_id = ch.get("id", "")
                                    ch_name = ch.get("name", "")
                                    if ch_id and ch_name:
                                        channels[ch_id] = f"#{ch_name}"
                                        logger.debug("Found counts channel (list): %s -> #%s", ch_id, ch_name)

                # Check client.userBoot and client.counts for comprehensive channel data
                if "client.userBoot" in url and response.get("ok"):
                    logger.debug("Processing client.userBoot response")
                    # Look for channels in various structures
                    for key in ["channels", "ims", "groups", "team"]:
                        if key in response:
                            data_section = response[key]
                            if isinstance(data_section, dict):
                                if key == "team" and "channels" in data_section:
                                    # Team channels structure
                                    team_channels = data_section["channels"]
                                    if isinstance(team_channels, dict):
                                        for ch_id, ch_data in team_channels.items():
                                            if isinstance(ch_data, dict):
                                                ch_name = ch_data.get("name", "")
                                                if ch_name:
                                                    channels[ch_id] = f"#{ch_name}"
                                                    logger.debug("Found team channel: %s -> #%s", ch_id, ch_name)
                                elif key == "channels":
                                    # Direct channels structure
                                    if isinstance(data_section, dict):
                                        for ch_id, ch_data in data_section.items():
                                            if isinstance(ch_data, dict):
                                                ch_name = ch_data.get("name", "")
                                                if ch_name:
                                                    channels[ch_id] = f"#{ch_name}"
                                                    logger.debug("Found direct channel: %s -> #%s", ch_id, ch_name)
                                    elif isinstance(data_section, list):
                                        for ch_data in data_section:
                                            if isinstance(ch_data, dict):
                                                ch_id = ch_data.get("id", "")
                                                ch_name = ch_data.get("name", "")
                                                if ch_id and ch_name:
                                                    channels[ch_id] = f"#{ch_name}"
                                                    logger.debug("Found list channel: %s -> #%s", ch_id, ch_name)

                # Check team.info response - might contain channel information
                if "team.info" in url and response.get("ok"):
                    logger.debug("Processing team.info response")
                    if "team" in response:
                        team_data = response["team"]
                        if isinstance(team_data, dict) and "channels" in team_data:
                            team_channels = team_data["channels"]
                            if isinstance(team_channels, dict):
                                for ch_id, ch_data in team_channels.items():
                                    if isinstance(ch_data, dict):
                                        ch_name = ch_data.get("name", "")
                                        if ch_name:
                                            channels[ch_id] = f"#{ch_name}"
                                            logger.debug("Found team.info channel: %s -> #%s", ch_id, ch_name)

                # Check conversations.list and channels.list
                endpoints = ["conversations.list", "channels.list"]
                if any(endpoint in url for endpoint in endpoints) and response.get("ok"):
                    for channel in response.get("channels", []):
                        if isinstance(channel, dict):
                            channel_id = channel.get("id")
                            channel_name = channel.get("name")
                            if channel_id and channel_name:
                                channels[channel_id] = f"#{channel_name}"
                                logger.debug("Found API channel: %s -> #%s", channel_id, channel_name)

                # Check for channel data in client.boot
                if "client.boot" in url and response.get("ok"):
                    team = response.get("team", {})
                    if isinstance(team, dict):
                        team_channels = team.get("channels", {})
                        if isinstance(team_channels, dict):
                            for channel_id, channel_data in team_channels.items():
                                if isinstance(channel_data, dict):
                                    channel_name = channel_data.get("name")
                                    if channel_name:
                                        channels[channel_id] = f"#{channel_name}"
                                        logger.debug("Found boot channel: %s -> #%s", channel_id, channel_name)

                # Check individual conversations in responses
                if "conversations" in response and isinstance(response["conversations"], list):
                    for conv in response["conversations"]:
                        if isinstance(conv, dict):
                            conv_id = conv.get("id")
                            conv_name = conv.get("name")
                            if conv_id and conv_name:
                                channels[conv_id] = f"#{conv_name}"
                                logger.debug("Found conv channel: %s -> #%s", conv_id, conv_name)

            print(f"✅ Found {ansi.green}{len(channels)}{ansi.reset} channels")
            logger.info("Channel discovery completed: %d channels found", len(channels))
            print(f"🔑 Credentials present? token={'✅' if self.credentials.token else '❌'}, cookies={'✅' if bool(self.credentials.cookies) else '❌'}")
            logger.debug("Credentials status: token=%s cookies=%s", bool(self.credentials.token), bool(self.credentials.cookies))
            if not (self.credentials.token and self.credentials.cookies):
                print("⚠️  Placeholder channel name resolution skipped (credentials missing)")
                logger.debug("Skipping placeholder fix-up due to missing credentials")

            if self.credentials.token and self.credentials.cookies:
                                # Broaden placeholder detection beyond '#channel_'
                placeholder_ids = []
                for cid, cname in channels.items():
                    if not cname:
                        placeholder_ids.append(cid)
                        continue
                    lower = cname.lower()
                    # Strip leading # for easier checks
                    stripped = lower.lstrip("#")
                    if (
                        stripped.startswith(("channel_", "group_"))
                        or stripped == cid.lower()  # name is literally the ID
                        or (stripped.startswith(("c", "g")) and len(stripped) == len(cid))
                        or cname in {"#", ""}
                    ):
                        placeholder_ids.append(cid)

                for cid in placeholder_ids:
                    info = self._api_post_sync("conversations.info", {"channel": cid})
                    if info.get("ok") and isinstance(info.get("channel"), dict):
                        real_name = info["channel"].get("name") or info["channel"].get("normalized_name")
                        if real_name:
                            channels[cid] = f"#{real_name}"
                            logger.debug("Resolved placeholder channel name: %s -> #%s", cid, real_name)

        except (IOError, OSError) as e:
            print(f"❌ Error loading channels: {e}")

        # Persist any resolved channel names to the channel map
        try:
            self._save_channel_map(channels)
        except (IOError, json.JSONDecodeError) as exc:
            logger.debug("Failed to save channel map: %s", exc)

        return channels

    async def get_conversations(self) -> Dict[str, ConversationInfo]:
        """Get all conversations (channels, DMs, group DMs) with proper ConversationInfo objects."""
        print("🔍 Getting conversations...")

        # Get user and channel mappings for better naming
        users = await self.get_user_list()
        channels = await self.get_channel_list()

        # Store mappings for use in parsing
        self.user_mappings = users
        self.channel_mappings = channels

        # Navigate to channels page to trigger channel list API calls
        try:
            print("🔍 Navigating to channels page to get channel data...")
            url = f"https://app.slack.com/client/{self.settings.team_id}/browse-channels"
            await self.page.goto(url, timeout=10000)
            await self.page.wait_for_timeout(3000)

            # Also try the main channels view
            await self.page.goto(f"https://app.slack.com/client/{self.settings.team_id}/channels", timeout=10000)
            await self.page.wait_for_timeout(3000)

            # Refresh channel mappings after navigation
            print("🔍 Refreshing channel mappings after navigation...")
            channels = await self.get_channel_list()
            self.channel_mappings = channels

        except (TimeoutError, Error) as e:
            print(f"⚠️  Error navigating to channels page: {e}")

        conversations = {}

        # Debug: Log API response data
        logger.debug("Found %d intercepted API calls for conversation discovery", len(self.intercepted_data))
        for data in self.intercepted_data[-10:]:  # Log last 10 calls
            url = data.get("url", "")
            if "client.userBoot" in url or "client.counts" in url or "conversations" in url:
                logger.debug("Processing API response: %s", url)
                response = data.get("response", {})
                if isinstance(response, dict):
                    logger.debug("Response keys: %s", list(response.keys()))
                    if "channels" in response:
                        channels_count = (len(response['channels'])
                                        if isinstance(response['channels'], list)
                                        else 'dict')
                        logger.debug("Channels in response: %s", channels_count)

        # Extract conversations from intercepted data
        for data in self.intercepted_data:
            url = data.get("url", "")
            response = data.get("response", {})

            if not isinstance(response, dict):
                continue

            # Check various API endpoints that might contain conversation data
            conversation_endpoints = [
                "conversations.list",
                "conversations.info",
                "channels.list",
                "channels.info",
                "im.list",
                "groups.list",
                "client.counts",
                "client.boot",
                "client.userBoot",
                "search.modules.people",
                "conversations.genericInfo"
            ]

            # Extract conversations from different API responses
            if any(endpoint in url for endpoint in conversation_endpoints) and response.get("ok"):
                # Handle conversations.list, channels.list, etc.
                for list_key in ["conversations", "channels", "ims", "groups"]:
                    if list_key in response and isinstance(response[list_key], list):
                        for conv_data in response[list_key]:
                            if isinstance(conv_data, dict):
                                conv_info = self._parse_conversation_data(conv_data)
                                if conv_info:
                                    conversations[conv_info.name] = conv_info

                # Handle client.boot and client.userBoot responses
                if "client.boot" in url or "client.userBoot" in url:
                    # Look for conversation data in various nested structures
                    for key in ["channels", "ims", "groups", "conversations"]:
                        if key in response:
                            conv_data = response[key]
                            if isinstance(conv_data, dict):
                                # Handle dict format (user_id: data)
                                for conv_id, conv_info in conv_data.items():
                                    if isinstance(conv_info, dict):
                                        conv_info["id"] = conv_id
                                        parsed_conv = self._parse_conversation_data(conv_info)
                                        if parsed_conv:
                                            conversations[parsed_conv.name] = parsed_conv
                            elif isinstance(conv_data, list):
                                # Handle list format
                                for conv_info in conv_data:
                                    if isinstance(conv_info, dict):
                                        parsed_conv = self._parse_conversation_data(conv_info)
                                        if parsed_conv:
                                            conversations[parsed_conv.name] = parsed_conv

                # Handle im.list specifically
                if "im.list" in url and "ims" in response:
                    for im_data in response["ims"]:
                        if isinstance(im_data, dict):
                            conv_info = self._parse_conversation_data(im_data)
                            if conv_info:
                                conversations[conv_info.name] = conv_info

        # Create fallback conversations for known channels from processed directories
        processed_dir = os.path.join(os.path.dirname(__file__), 'processed')
        if os.path.exists(processed_dir):
            for item in os.listdir(processed_dir):
                item_path = os.path.join(processed_dir, item)
                if os.path.isdir(item_path) and item not in conversations:
                    # Create a fallback ConversationInfo
                    if item.startswith('sb-'):
                        conv_type = ConversationType.CHANNEL
                        name = f"#{item}"
                    elif item.startswith('dm_'):
                        conv_type = ConversationType.DM
                        name = f"@{item}"
                    else:
                        conv_type = ConversationType.UNKNOWN
                        name = item

                    conversations[name] = ConversationInfo(
                        name=name,
                        conversation_id=item,
                        conversation_type=conv_type,
                        is_private=False,
                        member_count=0,
                        members=[]
                    )

        print(f"✅ Found {len(conversations)} conversations")
        return conversations



    async def _dismiss_modals(self):
        """Dismiss any modal dialogs that might interfere with scrolling."""
        if not self.page:
            return

        try:
            # Common modal selectors to try closing
            modal_selectors = [
                # Channel overview modal
                '[data-qa="channel_overview_modal"] .c-button--close',
                '[data-qa="channel_overview_modal"] .c-icon--times',
                '[data-qa="channel_overview_modal"] [aria-label="Close"]',

                # Generic modal close buttons
                '.c-modal__close',
                '.c-modal__close_button',
                '.c-dialog__close',
                '.c-dialog__close_button',

                # Slack-specific modal patterns
                '.c-sk-modal__close',
                '.c-sk-modal__close_button',
                '[data-qa="modal_close_button"]',
                '[data-qa="close_modal"]',
                '[data-qa="dialog_close"]',

                # Generic close icons
                '.c-icon--times',
                '.c-icon--close',
                '[aria-label="Close"]',
                '[aria-label="Close dialog"]',
                '[aria-label="Close modal"]',

                # Overlay/backdrop elements (click to close)
                '.c-modal__backdrop',
                '.c-sk-modal__backdrop',
                '.c-dialog__backdrop',

                # Specific known modals
                '[data-qa="channel_browser_modal"] .c-button--close',
                '[data-qa="member_profile_modal"] .c-button--close',
                '[data-qa="thread_view_modal"] .c-button--close',
            ]

            for selector in modal_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for element in elements:
                        is_visible = await element.is_visible()
                        if is_visible:
                            logger.debug("Found modal element, closing: %s", selector)
                            await element.click()
                            await self.page.wait_for_timeout(500)
                            return True  # Found and closed a modal
                except (TimeoutError, Error):
                    # Some selectors might not work, that's okay
                    continue

            # Try pressing Escape key as a fallback
            await self.page.keyboard.press("Escape")
            await self.page.wait_for_timeout(300)

        except (TimeoutError, Error) as e:
            print(f"⚠️  Error dismissing modals: {e}")

        return False

    # ------------------------------------------------------------------ #
    # Direct Web API fallback                                            #
    # ------------------------------------------------------------------ #
    def _fetch_history_via_api_sync(self, channel_id: str, oldest_ts: float = 0) -> List[Dict[str, Any]]:
        """Blocking helper that paginates conversations.history using the
        fresh token & cookies captured during interception. Mirrors the
        old fetch_cookie_md.py flow so we aren't dependent on UI scrolling."""

        # Require both token and cookies
        if not (self.credentials.token and self.credentials.cookies):
            return []

        # Build headers & multipart body (Slack still accepts form-data)
        boundary = "----WebKitFormBoundary" + hex(int(time.time()*1000))[2:]
        cookie_header = "; ".join(f"{k}={v}" for k, v in self.credentials.cookies.items())
        headers = {
            "cookie": cookie_header,
            "content-type": f"multipart/form-data; boundary={boundary}",
            "user-agent": "Mozilla/5.0",
            "accept": "*/*",
        }

        def _multipart(payload: dict) -> str:
            parts = []
            for k, v in payload.items():
                parts.append(f"--{boundary}")
                parts.append(f'Content-Disposition: form-data; name="{k}"')
                parts.append("")
                parts.append(str(v))
            parts.append(f"--{boundary}--")
            return "\r\n".join(parts)

        domain = self.settings.url.split("//")[-1]
        url = f"https://{domain}/api/conversations.history"

        messages: List[Dict[str, Any]] = []
        cursor = None
        while True:
            payload: Dict[str, Any] = {
                "token": self.credentials.token,
                "channel": channel_id,
                "limit": 1000,
                "oldest": oldest_ts,
                "inclusive": False,
            }
            if cursor:
                payload["cursor"] = cursor
            resp = requests.post(url, headers=headers, data=_multipart(payload), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                print(f"⚠️  API error: {data.get('error')}")
                break
            messages.extend(data.get("messages", []))
            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(0.3)

        # Sort chronologically
        messages.sort(key=lambda m: float(m.get("ts", 0)))
        return messages

    async def fetch_history_via_api(self, channel_id: str, oldest_ts: float = 0) -> List[Dict[str, Any]]:
        """Async wrapper around the sync helper so we don't block Playwright."""
        return await asyncio.to_thread(self._fetch_history_via_api_sync, channel_id, oldest_ts)

    async def fetch_conversation_history(self, channel_id: str, oldest_ts: float = 0) -> List[Dict[str, Any]]:
        """Fetch conversation history – prefers Web API pagination, falls back to UI scroll."""
        # 1) Try pure Web-API pagination first (fast & reliable)
        if self.credentials.token and self.credentials.cookies:
            try:
                api_msgs = await self.fetch_history_via_api(channel_id, oldest_ts)
                if api_msgs:
                    # ------------------------------------------------------------------
                    # NEW: also fetch thread replies via Web API
                    # ------------------------------------------------------------------
                    threaded_msgs: List[Dict[str, Any]] = []
                    for parent in api_msgs:
                        if parent.get("reply_count", 0) > 0 and parent.get("ts"):
                            try:
                                payload = {"channel": channel_id, "ts": parent["ts"], "limit": 1000}
                                reply_data = await asyncio.to_thread(self._api_post_sync, "conversations.replies", payload)
                                if reply_data.get("ok") and isinstance(reply_data.get("messages"), list):
                                    # Skip the first message (parent) to avoid duplicates
                                    threaded_msgs.extend(reply_data["messages"][1:])
                            except Exception as _e:
                                logger.debug("Failed to fetch thread replies for %s: %s", parent.get("ts"), _e)
                    combined_msgs = api_msgs + threaded_msgs
                    # De-duplicate by timestamp
                    deduped = {m.get("ts"): m for m in combined_msgs if m.get("ts")}
                    print(f"✅ Retrieved {ansi.green}{len(deduped)}{ansi.reset} messages via direct API", flush=True)
                    logger.info("Retrieved %d total messages (with thread replies) via direct API for channel %s", len(deduped), channel_id)
                    return list(sorted(deduped.values(), key=lambda m: float(m.get('ts', 0))))
                # Early exit for empty channels - but only if we can verify the channel exists and is accessible
                if oldest_ts == 0:  # Full history request
                    # Double-check by trying conversations.info to confirm channel is accessible
                    info_check = self._api_post_sync("conversations.info", {"channel": channel_id})
                    if info_check.get("ok") and info_check.get("channel"):
                        channel_info = info_check["channel"]
                        # If channel exists and is accessible but has no messages, likely empty/retention
                        print(f"📭 Channel '{channel_info.get('name', channel_id)}' has no messages - likely empty or beyond retention limit", flush=True)
                        logger.info("Channel %s exists but has no messages (confirmed via conversations.info) - skipping UI scroll", channel_id)
                        return []
                    else:
                        print("⚠️  Could not verify channel accessibility - proceeding with UI scroll as fallback")
                        logger.warning("Could not verify channel %s accessibility - proceeding with UI scroll", channel_id)

                print("⚠️  API returned no messages - falling back to UI scroll…")
                logger.info("API returned no messages for channel %s, falling back to UI scroll", channel_id)
            except (requests.exceptions.RequestException, KeyError, ValueError) as e:
                print(f"⚠️  API pagination failed ({e}) - falling back to UI scroll…")
                logger.warning("API pagination failed for channel %s: %s - falling back to UI scroll", channel_id, e)

        # 2) UI scroll fallback (original behaviour)
        if not self.page:
            print("❌ No page available for UI scroll fallback")
            return []

        print(f"📥 Fetching history for channel {channel_id} via UI scroll…")

        try:
            # Do NOT clear earlier intercepted data – we keep user/channel maps
            _start_intercept_index = len(self.intercepted_data)

            # Navigate to the channel to trigger history loading –
            # prefer the universal app.slack.com URL first to avoid desktop-app redirects
            primary_url = f"https://app.slack.com/client/{self.settings.team_id}/{channel_id}"
            fallback_url = f"{self.settings.url}/archives/{channel_id}"

            try:
                await self.page.goto(primary_url, timeout=10000)
                print("✅ Navigated via app.slack.com client URL")
            except (TimeoutError, Error) as e:
                print(f"⚠️  Failed to load primary URL ({primary_url}): {e}")
                # Fallback to workspace sub-domain URL
                try:
                    await self.page.goto(fallback_url, timeout=10000)
                    print("✅ Successfully navigated using workspace URL fallback")
                except (TimeoutError, Error) as e2:
                    print(f"❌ Failed to navigate with fallback URL ({fallback_url}): {e2}")
                    return []

            # Wait for initial messages to load
            await self.page.wait_for_timeout(3000)

            # Dismiss any modals that might interfere with scrolling
            print("🔍 Checking for and dismissing any modal dialogs...")
            await self._dismiss_modals()

            # Improved scrolling to load more history
            print("🔄 Scrolling to load more message history...")

            # Try to scroll to the very top to load all history
            previous_message_count = 0
            max_scroll_attempts = 50  # Increased from 10 to 50
            no_new_messages_count = 0

            # Check if we already have any messages from initial load
            initial_message_count = 0
            for data in self.intercepted_data:
                if "conversations.history" in data["url"]:
                    response = data.get("response", {})
                    if response.get("ok"):
                        initial_message_count += len(response.get("messages", []))

            # If no messages found initially, use reduced attempts for faster termination
            if initial_message_count == 0:
                max_scroll_attempts = 10  # Much faster for empty channels
                print(f"🔄 No initial messages found - using reduced scroll attempts ({max_scroll_attempts})")
                logger.info("No initial messages for channel %s - using reduced scroll attempts (%d)", channel_id, max_scroll_attempts)
            else:
                print(f"🔄 Starting message history scroll (up to {max_scroll_attempts} attempts)")
                logger.info("Starting aggressive scrolling for channel %s (up to %d attempts)", channel_id, max_scroll_attempts)

            for attempt in range(max_scroll_attempts):
                try:
                    # Every few attempts, dismiss any launch screens or popups
                    if attempt % 3 == 0:  # Every 3rd attempt
                        await self._bypass_launch_screen()
                        await self._dismiss_modals()

                    # Get current message count from intercepted data
                    current_message_count = 0
                    earliest_timestamp = None

                    for data in self.intercepted_data:
                        if "conversations.history" in data["url"]:
                            response = data.get("response", {})
                            if response.get("ok"):
                                messages = response.get("messages", [])
                                current_message_count += len(messages)

                                # Track earliest timestamp to detect if we've reached the beginning
                                for msg in messages:
                                    msg_ts = float(msg.get("ts", "0"))
                                    if earliest_timestamp is None or msg_ts < earliest_timestamp:
                                        earliest_timestamp = msg_ts

                    # Check if we've stopped loading new messages
                    if current_message_count == previous_message_count:
                        no_new_messages_count += 1
                        logger.debug("No new messages loaded in attempt %d (count: %d)", attempt + 1, no_new_messages_count)

                        # Adjust termination threshold based on initial message count
                        termination_threshold = 3 if initial_message_count == 0 else 8
                        if no_new_messages_count >= termination_threshold:
                            if initial_message_count == 0:
                                print("✅ No messages found - channel appears empty")
                                logger.info("No messages found for channel %s after %d attempts - appears empty", channel_id, attempt + 1)
                            else:
                                print("✅ Reached the beginning of channel history")
                                logger.info("Reached beginning of channel history after %d attempts", attempt + 1)
                            break

                        # Try more aggressive scrolling methods when no new messages
                        # Skip aggressive methods for empty channels to speed up termination
                        if attempt > 5 and initial_message_count > 0:
                            # First dismiss any modals that might be blocking
                            await self._dismiss_modals()

                            # Try multiple Page Up presses
                            for i in range(5):
                                await self.page.keyboard.press("PageUp")
                                await self.page.wait_for_timeout(200)

                            # Try pressing Home key to go to the beginning
                            await self.page.keyboard.press("Home")
                            await self.page.wait_for_timeout(500)

                            # Try Ctrl+Home as alternative
                            await self.page.keyboard.press("Control+Home")
                            await self.page.wait_for_timeout(500)

                            # Try scrolling to absolute top
                            await self.page.evaluate("window.scrollTo(0, 0)")
                            await self.page.wait_for_timeout(500)

                            # Try clicking at the very top of the message area
                            try:
                                await self.page.click('[data-qa="message_pane"]', position={'x': 100, 'y': 10})
                                await self.page.wait_for_timeout(500)
                            except (TimeoutError, Error):
                                pass

                            # Try clicking on the channel name to refresh
                            try:
                                await self.page.click('[data-qa="channel_name"]')
                                await self.page.wait_for_timeout(1000)
                            except (TimeoutError, Error):
                                pass
                    else:
                        no_new_messages_count = 0
                        new_messages = current_message_count - previous_message_count
                        logger.debug("Loaded %d new messages (total: %d) in attempt %d", new_messages, current_message_count, attempt + 1)

                        # Reset no new messages counter since we found new messages
                        no_new_messages_count = 0

                    # Use multiple scrolling methods for better coverage
                    scroll_methods = [
                        lambda: self.page.keyboard.press("PageUp"),
                        lambda: self.page.keyboard.press("Control+Home"),
                        lambda: self.page.keyboard.press("Home"),
                        lambda: self.page.mouse.wheel(0, -2000),
                        lambda: self.page.evaluate("window.scrollTo(0, 0)"),
                        lambda: self.page.evaluate("document.querySelector('[data-qa=\"message_pane\"]')?.scrollTo(0, 0)"),
                        lambda: self.page.evaluate("document.querySelector('.c-message_list')?.scrollTo(0, 0)"),
                        lambda: self.page.evaluate("document.querySelector('.c-message_list__scrollbar')?.scrollTo(0, 0)"),
                        lambda: self.page.evaluate("document.querySelector('.c-message_list__scrollbar_hider')?.scrollTo(0, 0)"),
                    ]

                    # Use different scrolling methods on different attempts
                    method_index = attempt % len(scroll_methods)
                    try:
                        await scroll_methods[method_index]()
                        await self.page.wait_for_timeout(800)  # Increased wait time
                    except (TimeoutError, Error) as e:
                        logger.debug("Scrolling method %d failed: %s", method_index, e)
                        # Fallback to basic PageUp
                        await self.page.keyboard.press("PageUp")
                        await self.page.wait_for_timeout(800)

                    # Every 10 attempts, try to refresh the channel view to trigger more API calls
                    if attempt > 0 and attempt % 10 == 0:
                        logger.debug("Refreshing channel view (attempt %d)", attempt)
                        # Dismiss modals before refreshing
                        await self._dismiss_modals()
                        current_url = self.page.url
                        await self.page.goto(current_url)
                        await self.page.wait_for_timeout(3000)
                        # Dismiss modals after refreshing
                        await self._dismiss_modals()

                    previous_message_count = current_message_count

                    # If we've reached the oldest timestamp, stop scrolling
                    if oldest_ts > 0:
                        oldest_message_found = False
                        for data in self.intercepted_data:
                            if "conversations.history" in data["url"]:
                                response = data.get("response", {})
                                if response.get("ok"):
                                    messages = response.get("messages", [])
                                    for msg in messages:
                                        if float(msg.get("ts", "0")) <= oldest_ts:
                                            oldest_message_found = True
                                            break
                                    if oldest_message_found:
                                        break
                        if oldest_message_found:
                            print("✅ Reached oldest timestamp target")
                            logger.info("Reached oldest timestamp target (%s)", oldest_ts)
                            break

                    # Enhanced check for reaching the beginning
                    if earliest_timestamp and attempt > 15:
                        # Calculate how old the earliest message is
                        current_time = time.time()
                        message_age_days = (current_time - earliest_timestamp) / (24 * 60 * 60)
                        logger.debug("Earliest message is %.1f days old", message_age_days)

                        # If messages are very old, we might be at the beginning
                        if message_age_days > 30:  # More than 30 days old
                            logger.debug("Reached old messages (%.1f days), likely near channel beginning", message_age_days)
                            # But continue for a few more attempts to be sure
                            if attempt > 25:
                                print("✅ Reached very old messages - stopping scroll")
                                logger.info("Stopping scroll after reaching very old messages (%.1f days)", message_age_days)
                                break

                except (TimeoutError, Error) as e:
                    print(f"⚠️  Error during scroll attempt {attempt + 1}: {e}")
                    # Try to dismiss modals in case of error
                    await self._dismiss_modals()
                    # Continue with next attempt
                    continue

            logger.info("Completed %d scroll attempts for channel %s", min(attempt + 1, max_scroll_attempts), channel_id)

            # Final modal dismissal before thread extraction
            await self._dismiss_modals()

            # Final wait for any remaining API calls
            await self.page.wait_for_timeout(5000)  # Increased from 2000 to 5000

            # Try to click on threads to load replies
            try:
                # First check if we have any messages that might have threads from API data
                has_potential_threads = False
                for data in self.intercepted_data:
                    if "conversations.history" in data["url"]:
                        response = data.get("response", {})
                        if response.get("ok"):
                            messages = response.get("messages", [])
                            for msg in messages:
                                if msg.get("reply_count", 0) > 0 or msg.get("thread_ts"):
                                    has_potential_threads = True
                                    break
                            if has_potential_threads:
                                break

                if not has_potential_threads:
                    print("📭 No threaded messages detected in API data - skipping thread extraction")
                    logger.info("No threaded messages found in API data for channel %s - skipping thread clicks", channel_id)
                else:
                    print("🔄 Loading thread replies...")
                    logger.info("Starting thread reply extraction for channel %s", channel_id)

                    # Use prioritized selectors - most common first
                    prioritized_selectors = [
                        'button:has-text("replies")',  # Most common
                        'a:has-text("replies")',
                        '[data-qa="thread_reply_bar"]',
                        '.c-message__thread_reply_count',
                        '[aria-label*="replies"]',
                    ]

                    visible_thread_buttons = []
                    selector_stats = {}  # Track which selectors actually work

                    for selector in prioritized_selectors:
                        try:
                            elements = await self.page.query_selector_all(selector)
                            visible_count = 0

                            for element in elements:
                                # Pre-filter: only include visible elements
                                try:
                                    if await element.is_visible():
                                        visible_thread_buttons.append(element)
                                        visible_count += 1

                                        # Capture DOM attributes for analysis
                                        try:
                                            tag_name = await element.evaluate("el => el.tagName")
                                            class_name = await element.evaluate("el => el.className")
                                            data_qa = await element.evaluate("el => el.getAttribute('data-qa')")
                                            aria_label = await element.evaluate("el => el.getAttribute('aria-label')")
                                            text_content = await element.evaluate("el => el.textContent")

                                            logger.info("Thread element found with selector '%s': tag=%s, class='%s', data-qa='%s', aria-label='%s', text='%s'", 
                                                      selector, tag_name, class_name, data_qa, aria_label, (text_content or "")[:50])
                                        except (TimeoutError, Error):
                                            logger.debug("Could not capture DOM attributes for thread element")
                                except (TimeoutError, Error):
                                    continue

                            # Track selector effectiveness
                            if len(elements) > 0 or visible_count > 0:
                                selector_stats[selector] = {
                                    'total_found': len(elements),
                                    'visible_count': visible_count
                                }
                                logger.info("Selector '%s': found %d elements, %d visible", selector, len(elements), visible_count)

                            # Stop if we found some good candidates
                            if len(visible_thread_buttons) >= 5:  # Reasonable limit
                                logger.info("Reached thread limit (5), stopping selector search")
                                break

                        except (TimeoutError, Error) as e:
                            logger.debug("Selector '%s' failed: %s", selector, e)
                            continue

                    # Log summary of selector effectiveness
                    if selector_stats:
                        logger.info("Thread selector effectiveness summary:")
                        for sel, stats in selector_stats.items():
                            logger.info("  '%s': %d total, %d visible", sel, stats['total_found'], stats['visible_count'])
                    else:
                        logger.info("No thread selectors found any elements")

                    # Remove duplicates more efficiently using set of element handles
                    seen_elements = set()
                    unique_buttons = []
                    for button in visible_thread_buttons:
                        if button not in seen_elements:
                            seen_elements.add(button)
                            unique_buttons.append(button)

                    logger.debug("Found %d visible, unique thread buttons", len(unique_buttons))

                    successful_clicks = 0
                    thread_api_calls_before = len([d for d in self.intercepted_data if "conversations.replies" in d.get("url", "")])

                    for i, button in enumerate(unique_buttons):  # Click every discovered thread
                        try:
                            logger.info("Attempting to click thread %d/%d", i+1, len(unique_buttons))

                            # Since we pre-filtered for visible elements, skip visibility check
                            # Just scroll into view and click
                            try:
                                await button.scroll_into_view_if_needed()
                                await self.page.wait_for_timeout(200)  # Reduced from 500ms
                            except (TimeoutError, Error):
                                pass

                            await button.click()

                            # Wait for thread panel to appear instead of fixed timeout
                            thread_panel_appeared = False
                            try:
                                await self.page.wait_for_selector('[data-qa="thread-messages-scroller"], .c-flexpane__content', timeout=3000)
                                await self.page.wait_for_timeout(500)  # Brief pause for content to load
                                thread_panel_appeared = True
                                logger.info("Thread %d/%d: panel appeared successfully", i+1, len(unique_buttons))
                            except (TimeoutError, Error):
                                # Fallback to shorter fixed wait if selector doesn't work
                                await self.page.wait_for_timeout(1500)  # Reduced from 2000+1000
                                logger.debug("Thread %d/%d: panel selector failed, used fallback wait", i+1, len(unique_buttons))

                            # Quick scroll within thread - most replies load immediately
                            try:
                                # Simple Page Down a couple times should be sufficient
                                await self.page.keyboard.press("PageDown")
                                await self.page.wait_for_timeout(300)  # Reduced from 1000ms
                                await self.page.keyboard.press("PageDown") 
                                await self.page.wait_for_timeout(300)  # Total: 600ms vs 3000ms
                                logger.debug("Thread scroll completed")
                            except (TimeoutError, Error) as e:
                                logger.debug("Error scrolling thread: %s", e)

                            # Quick close - just use Escape key (fastest method)
                            try:
                                await self.page.keyboard.press("Escape")
                                await self.page.wait_for_timeout(200)  # Reduced from 500ms
                                logger.debug("Thread closed with Escape")
                                successful_clicks += 1
                                logger.info("Thread %d/%d: completed successfully", i+1, len(unique_buttons))
                            except (TimeoutError, Error) as e:
                                logger.debug("Error closing thread: %s", e)

                        except (TimeoutError, Error) as e:
                            logger.warning("Error clicking thread %d: %s", i+1, e)
                            continue

                    # Check how many thread API calls were generated
                    thread_api_calls_after = len([d for d in self.intercepted_data if "conversations.replies" in d.get("url", "")])
                    new_thread_calls = thread_api_calls_after - thread_api_calls_before

                    logger.info("Thread extraction summary: %d buttons clicked successfully, %d new API calls generated", 
                              successful_clicks, new_thread_calls)

            except (TimeoutError, Error) as e:
                logger.debug("Error loading threads: %s", e)

            # Wait a bit more for thread API calls
            await self.page.wait_for_timeout(3000)

            # Extract messages from intercepted API calls
            all_messages = []
            _threads_data = {}  # Store thread replies

            for data in self.intercepted_data:
                try:
                    url = data["url"]

                    # Handle main conversation history
                    if "conversations.history" in url:
                        response = data.get("response", {})
                        if response.get("ok"):
                            messages = response.get("messages", [])
                            for msg in messages:
                                if float(msg.get("ts", "0")) > oldest_ts:
                                    all_messages.append(msg)

                    # Handle thread replies
                    elif "conversations.replies" in url:
                        response = data.get("response", {})
                        if response.get("ok"):
                            messages = response.get("messages", [])
                            # Skip the first message (parent) and add replies
                            for msg in messages[1:]:
                                if float(msg.get("ts", "0")) > oldest_ts:
                                    all_messages.append(msg)

                    # Handle other message-related endpoints
                    elif any(endpoint in url for endpoint in [
                        "conversations.info",
                        "conversations.members",
                        "files.info",
                        "reactions.get"
                    ]):
                        response = data.get("response", {})
                        if response.get("ok"):
                            # Extract any message data from these endpoints
                            if "message" in response:
                                msg = response["message"]
                                if float(msg.get("ts", "0")) > oldest_ts:
                                    all_messages.append(msg)

                except (KeyError, TypeError, ValueError) as e:
                    print(f"⚠️  Error processing intercepted data: {e}")
                    # Continue with next data item
                    continue

            # Remove duplicates and sort by timestamp
            seen_ts = set()
            unique_messages = []
            for msg in all_messages:
                try:
                    ts = msg.get("ts")
                    if ts and ts not in seen_ts:
                        seen_ts.add(ts)
                        unique_messages.append(msg)
                except (KeyError, TypeError) as e:
                    print(f"⚠️  Error processing message: {e}")
                    continue

            unique_messages.sort(key=lambda x: float(x.get("ts", "0")))

            print(f"✅ Found {ansi.green}{len(unique_messages)}{ansi.reset} messages")
            logger.info("Message extraction completed for channel %s: %d unique messages", channel_id, len(unique_messages))

            # Log debug info about message types
            if unique_messages:
                subtypes = {}
                for msg in unique_messages:
                    subtype = msg.get("subtype", "regular")
                    subtypes[subtype] = subtypes.get(subtype, 0) + 1

                logger.debug("Message types extracted: %s", dict(subtypes))

            return unique_messages

        except (TimeoutError, Error) as e:
            print(f"❌ Error fetching conversation history: {e}")
            traceback.print_exc()
            return []

    async def get_user_list(self) -> Dict[str, str]:
        """Get user list from intercepted data and rolodex with **live data taking precedence**.
        Previously, rolodex entries overwrote the freshest Slack profile info which led to
        name / user-id mismatches (e.g. Jake vs Rahul). The new logic builds the mapping
        from Slack first, then fills any gaps from rolodex as a **fallback**.
        """
        users: Dict[str, str] = {}

        # ------------------------------------------------------------------
        # 1) Gather from intercepted bootstrap payloads
        # ------------------------------------------------------------------
        for data in self.intercepted_data:
            resp = data.get("response", {})
            if "client.userBoot" in data.get("url", "") and isinstance(resp, dict):
                for uid, info in resp.get("users", {}).items():
                    if not uid:
                        continue
                    name = info.get("real_name") or info.get("name") or f"User_{uid[-6:]}"
                    users[uid] = name

        # ------------------------------------------------------------------
        # 2) Enrich via users.list API when token is present
        # ------------------------------------------------------------------
        if self.credentials.token and self.credentials.cookies:
            cursor = None
            while True:
                payload = {"limit": 1000}
                if cursor:
                    payload["cursor"] = cursor
                api_resp = await asyncio.to_thread(self._api_post_sync, "users.list", payload)
                if not api_resp.get("ok"):
                    break
                for member in api_resp.get("members", []):
                    uid = member.get("id")
                    if not uid or member.get("deleted") or member.get("is_bot"):
                        continue
                    profile = member.get("profile", {})
                    display_name = (
                        profile.get("display_name")
                        or profile.get("real_name")
                        or member.get("name")
                        or f"User_{uid[-6:]}"
                    )
                    users[uid] = display_name
                cursor = api_resp.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
                await asyncio.sleep(0.2)

        # ------------------------------------------------------------------
        # 3) Fallback to rolodex for any **missing** ids
        # ------------------------------------------------------------------
        rolodex_users = self._load_rolodex()
        missing_count = 0
        for uid, name in rolodex_users.items():
            if uid not in users:
                users[uid] = name
                missing_count += 1

        print(f"👥 Loaded {ansi.green}{len(users)}{ansi.reset} users")
        logger.info("User discovery completed: %d total users (%d from live API, %d from rolodex fallback)", len(users), len(users) - missing_count, missing_count)
        # Persist any newly discovered users to rolodex for future runs
        try:
            self._save_rolodex(users)
        except (IOError, json.JSONDecodeError) as e:
            logger.warning("Failed to save rolodex: %s", e)
        return users

    async def save_credentials(self):
        """Save intercepted credentials."""
        if self.credentials.token:
            self.credentials.save()
            print("💾 Saved fresh credentials")

    async def close(self):
        """Close browser and save credentials."""
        await self._save_storage_state_if_enabled()
        await self.save_credentials()
        if self.browser:
            await self.browser.close()

    async def _bypass_launch_screen(self):
        """Bypass the Slack launch screen that tries to open the desktop app."""
        if not self.page:
            return

        try:
            # 0. Quick check – if we already got shunted to Slack's download / getting-started page
            current_url = self.page.url
            download_indicators = ["/getting-started", "/download", "/app", "/desktop", "/install"]
            if any(term in current_url for term in download_indicators):
                print("🔍 Detected app download page, navigating back to web client…")
                # Use workspace URL instead of APP_CLIENT_URL to avoid redirects
                await self.page.goto(self.settings.url)
                await self.page.wait_for_timeout(1000)  # Give it time to load

                # Double-check we didn't get redirected again
                new_url = self.page.url
                if any(term in new_url for term in download_indicators):
                    print("🔍 Still on download page, trying direct app client URL…")
                    await self.page.goto(self.settings.app_client_url)
                    await self.page.wait_for_timeout(1000)

                return True

            # 1. Prefer explicit "Open in browser" actions
            open_in_browser_selectors = [
                # Exact official link variants
                'a[href*="/ssb/redirect"]',
                'a:has-text("use Slack in your browser.")',
                'a:has-text("use Slack in your browser")',
                # Other common variants
                'button:has-text("Open Slack in your browser")',
                'a:has-text("Open Slack in your browser")',
                'button:has-text("Use Slack in your browser")',
                'a:has-text("Use Slack in your browser")',
                'button:has-text("Continue in browser")',
                'a:has-text("Continue in browser")',
                'button:has-text("Open in browser")',
                'a:has-text("Open in browser")',
                '[data-qa="continue_in_browser"]',
            ]

            cancel_selectors = [
                'button:has-text("Cancel")',
                'button:has-text("Not now")',
                'button:has-text("Maybe later")',
                'button:has-text("No thanks")',
                '[data-qa="app-download-banner-close"]',
                '[data-qa="download-banner-close"]',
                '.p-download_page__cta--skip',
                '.p-download_page__skip',
                '.c-banner__close',
                '.c-alert__close',
            ]

            # Try direct open-in-browser first
            for selector in open_in_browser_selectors:
                try:
                    el = await self.page.query_selector(selector)
                    if el:
                        print(f"🔍 Found 'Open in browser' element: {selector}")
                        await el.click()
                        print("✅ Opening Slack in browser")
                        await self.page.wait_for_timeout(700)
                        return True
                except (TimeoutError, Error):
                    continue

            # Otherwise, click cancel/close then try open-in-browser once more
            for selector in cancel_selectors:
                try:
                    el = await self.page.query_selector(selector)
                    if el:
                        print(f"🔍 Found app prompt dismiss element: {selector}")
                        await el.click()
                        await self.page.wait_for_timeout(400)
                        # Second pass for open-in-browser after dismiss
                        for ob_sel in open_in_browser_selectors:
                            try:
                                ob_el = await self.page.query_selector(ob_sel)
                                if ob_el:
                                    print(f"🔍 Found 'Open in browser' element after dismiss: {ob_sel}")
                                    await ob_el.click()
                                    print("✅ Opening Slack in browser")
                                    await self.page.wait_for_timeout(700)
                                    return True
                            except (TimeoutError, Error):
                                continue
                        return True
                except (TimeoutError, Error):
                    continue

            # Check for app download banner in URL and dismiss
            current_url = self.page.url
            download_indicators = ["/getting-started", "/download", "/app", "/desktop", "/install"]
            if any(term in current_url for term in download_indicators):
                print("🔍 Detected app download page, navigating to workspace...")
                await self.page.goto(self.settings.url)
                await self.page.wait_for_timeout(1000)  # Reduced wait time

                # Verify we're not still on a download page
                final_url = self.page.url
                if any(term in final_url for term in download_indicators):
                    print("🔍 Still redirecting to download, forcing client URL...")
                    await self.page.goto(self.settings.app_client_url)
                    await self.page.wait_for_timeout(1000)

                return True

            # Try pressing Escape to dismiss any overlays
            try:
                await self.page.keyboard.press("Escape")
                await self.page.wait_for_timeout(500)
            except (TimeoutError, Error):  # Keyboard action might fail
                pass

            return False

        except (TimeoutError, Error) as e:
            print(f"⚠️ Error handling app launcher: {e}")
            return False

    def _load_rolodex(self) -> Dict[str, str]:
        """Load user mappings from rolodex.json file."""
        try:
            # First look for top-level rolodex, then fall back to data/
            rolodex_path = Path("rolodex.json")
            if not rolodex_path.exists():
                rolodex_path = Path("data/rolodex.json")

            if rolodex_path.exists():
                with open(rolodex_path, 'r', encoding='utf-8') as f:
                    rolodex = json.load(f)

                # Create user_id -> name mapping
                user_mapping = {}
                for person in rolodex.get("people", []):
                    if "user_id" in person and "name" in person:
                        user_mapping[person["user_id"]] = person["name"]

                logger.debug("Loaded %d user mappings from rolodex", len(user_mapping))
                return user_mapping
            logger.debug("No rolodex file found (searched 'rolodex.json' and 'data/rolodex.json'), using basic user mapping")
            return {}
        except (IOError, json.JSONDecodeError) as e:
            logger.warning("Error loading rolodex: %s", e)
            return {}

    # ------------------------------------------------------------------ #
    def _save_rolodex(self, user_mapping: Dict[str, str]) -> None:
        """Persist new user_id→name pairs into rolodex.json (append-only)."""
        try:
            rolodex_path = Path("rolodex.json")
            if not rolodex_path.exists():
                rolodex_path = Path("data/rolodex.json")
            # Load existing data or create fresh structure
            if rolodex_path.exists():
                rolodex_data = json.loads(rolodex_path.read_text(encoding="utf-8"))
            else:
                rolodex_data = {}
            if "people" not in rolodex_data or not isinstance(rolodex_data.get("people"), list):
                rolodex_data["people"] = []
            existing_ids = {p.get("user_id") for p in rolodex_data["people"] if isinstance(p, dict)}
            new_entries = 0
            for uid, name in user_mapping.items():
                if uid not in existing_ids:
                    rolodex_data["people"].append({"user_id": uid, "name": name})
                    new_entries += 1
            if new_entries:
                rolodex_path.parent.mkdir(parents=True, exist_ok=True)
                rolodex_path.write_text(json.dumps(rolodex_data, indent=2), encoding="utf-8")
                logger.debug("Saved %d new user mappings to rolodex", new_entries)
        except (IOError, json.JSONDecodeError) as exc:
            logger.warning("Error saving rolodex: %s", exc)

    # ------------------------------------------------------------------ #
    #  Channel map helpers                                              #
    # ------------------------------------------------------------------ #
    def _load_channel_map(self) -> Dict[str, str]:
        """Load persistent channel ID → name mapping."""
        try:
            if CHANNEL_MAP_FILE.exists():
                data = json.loads(CHANNEL_MAP_FILE.read_text(encoding="utf-8"))
                return {cid: name for cid, name in data.items() if not cid.startswith("_")}
        except (IOError, json.JSONDecodeError) as exc:
            logger.debug("Error loading channel map: %s", exc)
        return {}

    def _save_channel_map(self, channel_dict: Dict[str, str]) -> None:
        """Append newly-resolved channels to persistent map.

        Expects channel_dict in the form {id: "#name"}
        """
        try:
            existing = self._load_channel_map()
            updated = False
            for cid, cname in channel_dict.items():
                if not cid or not cname or not cname.startswith("#"):
                    continue
                name_plain = cname.lstrip("#")
                # Skip obvious placeholders
                if name_plain.lower().startswith(("channel_", "group_")) or name_plain.lower() == cid.lower():
                    continue
                if cid not in existing or existing[cid] != name_plain:
                    existing[cid] = name_plain
                    updated = True
            # flush changes
            if updated:
                existing["_updated"] = datetime.now(UTC).isoformat()
                CHANNEL_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
                CHANNEL_MAP_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
                logger.debug("Channel map updated with %d entries (total %d)", len(channel_dict), len(existing) - 1)
        except (IOError, json.JSONDecodeError) as exc:
            logger.warning("Error saving channel map: %s", exc)

    #  Helper: lightweight Web-API POST using captured creds              #
    # ------------------------------------------------------------------ #
    def _api_post_sync(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Minimal wrapper around Slack web API POST.
        Expects that self.credentials already holds both cookies & token."""
        if not (self.credentials.token and self.credentials.cookies):
            return {}

        domain = self.settings.url.split("//")[-1]
        url = f"https://{domain}/api/{endpoint}"

        payload = {**payload, "token": self.credentials.token}

        cookie_header = "; ".join(f"{k}={v}" for k, v in self.credentials.cookies.items())
        headers = {
            "cookie": cookie_header,
            "user-agent": "Mozilla/5.0",
            "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
            "accept": "application/json, text/plain, */*",
        }

        try:
            r = requests.post(url, headers=headers, data=payload, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as exc:
            logger.error("API call %s failed: %s", endpoint, exc)
            return {}

    def _get_dm_participants_sync(self, channel_id: str, users: Dict[str, str]) -> List[str]:
        """Return display names for all participants in a DM/MPDM channel."""
        info = self._api_post_sync("conversations.info", {"channel": channel_id})
        if not info.get("ok"):
            return []

        chan = info.get("channel", {})
        names: List[str] = []

        # 1-on-1 DM
        if chan.get("is_im") and chan.get("user"):
            uid = chan["user"]
            names.append(users.get(uid, f"User_{uid[-6:]}"))
        # Group DM (mpim)
        elif chan.get("is_mpim") and chan.get("members"):
            for uid in chan["members"]:
                names.append(users.get(uid, f"User_{uid[-6:]}"))

        return names

    async def get_dm_participants(self, channel_id: str, users: Dict[str, str]) -> List[str]:
        """Async wrapper for participant lookup."""
        return await asyncio.to_thread(self._get_dm_participants_sync, channel_id, users)

    # ------------------------------------------------------------------ #
    #  Friendly filename generator                                       #
    # ------------------------------------------------------------------ #
    async def conversation_filename(self, channel_id: str, channel_name: str, users: Dict[str, str], messages: List[Dict[str, Any]] | None = None) -> str:
        """Return a human-friendly, filesystem-safe filename for this conversation."""

        # Detect D or G => DM / MPDM
        if channel_id and channel_id[0] in {"D", "G"}:
            parts = await self.get_dm_participants(channel_id, users)
            # Fallback: derive from message authors if API didn't return anything
            if not parts and messages:
                uid_set = {m.get("user") for m in messages if m.get("user")}
                me = self.credentials.user_id
                if me in uid_set:
                    uid_set.remove(me)
                parts = [users.get(uid, f"User_{uid[-6:]}") for uid in uid_set]

            if parts:
                parts = sorted(set(parts))  # stable ordering
                if len(parts) == 1:
                    base = f"dm_with_{parts[0]}_{channel_id[-6:]}"
                else:
                    trimmed = "-".join(parts[:4])  # limit length after sort
                    base = f"group_dm_{trimmed}"
            else:
                base = f"dm_{channel_id}"
        else:
            base = channel_name.lstrip("#@") or f"channel_{channel_id}"

        # Sanitize: replace invalid chars and collapse whitespace to underscores
        safe = re.sub(r'[<>:"/\\|?*@]', '_', base)
        safe = re.sub(r'\s+', '_', safe)  # spaces and tabs => underscore
        safe = re.sub(r'_+', '_', safe).strip('_')
        return safe

    # ------------------------------------------------------------------ #
    #  Channel helper                                                    #
    # ------------------------------------------------------------------ #
    def _get_channel_name_sync(self, channel_id: str) -> str | None:
        """Return the readable channel name for a given C-channel id."""
        if not channel_id or channel_id[0] not in {"C", "G"}:
            return None
        info = self._api_post_sync("conversations.info", {"channel": channel_id})
        if info.get("ok"):
            ch = info.get("channel", {})
            return ch.get("name") or ch.get("normalized_name")
        return None

    async def get_channel_name(self, channel_id: str) -> str | None:
        """Get readable channel name for a given channel ID."""
        return await asyncio.to_thread(self._get_channel_name_sync, channel_id)


# -------------- Utility Functions -------------------------------------------

def _load_tracker() -> Dict[str, Any]:
    """Load conversation tracking data."""
    if TRACK_FILE.exists():
        data = json.loads(TRACK_FILE.read_text(encoding='utf-8'))
        if "channels" not in data:
            data["channels"] = {}
        return data
    return {"channels": {}}


def _save_tracker(data: Dict[str, Any]) -> None:
    """Save conversation tracking data."""
    TRACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACK_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def _markdown_line(msg: Dict[str, Any], users: Dict[str, str]) -> str:
    """Convert message to markdown line with enhanced formatting."""
    ts_float = float(msg["ts"])
    ts_str = datetime.fromtimestamp(ts_float).strftime("%Y-%m-%d %H:%M")

    user_id = msg.get("user", "")
    user_name = users.get(user_id, f"User_{user_id[-6:]}" if user_id else "System")

    # Handle different message types
    subtype = msg.get("subtype", "")

    # Handle system messages
    if subtype in ["channel_join", "channel_leave", "channel_topic", "channel_purpose"]:
        action = {
            "channel_join": "joined the channel",
            "channel_leave": "left the channel",
            "channel_topic": "changed the channel topic",
            "channel_purpose": "changed the channel purpose"
        }.get(subtype, "performed an action")
        return f"- **{ts_str}** *{user_name}* {action}"

    # Handle bot messages
    if msg.get("bot_id") or subtype == "bot_message":
        bot_name = msg.get("username", "Bot")
        user_name = f"🤖 {bot_name}"

    # Get message text
    text = msg.get("text", "")

    # Process Slack formatting in text
    if text:
        # Handle user mentions (<@U123456>)
        def replace_user_mention(match):
            user_id = match.group(1)
            mentioned_user = users.get(user_id, f"User_{user_id[-6:]}")
            return f"@{mentioned_user}"

        text = re.sub(r'<@([A-Z0-9]+)>', replace_user_mention, text)

        # Handle channel mentions (<#C123456|channel-name>)
        def replace_channel_mention(match):
            channel_name = match.group(2) if match.group(2) else match.group(1)
            return f"#{channel_name}"

        text = re.sub(r'<#([A-Z0-9]+)(?:\|([^>]+))?>', replace_channel_mention, text)

        # Handle URLs (<https://example.com|Link Text>)
        def replace_url(match):
            url = match.group(1)
            link_text = match.group(2) if match.group(2) else url
            return f"[{link_text}]({url})"

        text = re.sub(r'<(https?://[^>|]+)(?:\|([^>]+))?>', replace_url, text)

        # Handle bold text (*text*)
        text = re.sub(r'(?<!\\)\*([^*]+)\*', r'**\1**', text)

        # Handle italic text (_text_)
        text = re.sub(r'(?<!\\)_([^_]+)_', r'*\1*', text)

        # Handle strikethrough (~text~)
        text = re.sub(r'(?<!\\)~([^~]+)~', r'~~\1~~', text)

        # Handle inline code (`text`)
        text = re.sub(r'(?<!\\)`([^`]+)`', r'`\1`', text)

        # Handle code blocks (```text```)
        text = re.sub(r'(?<!\\)```([^`]+)```', r'```\n\1\n```', text)

    # Handle file attachments
    attachments = msg.get("files", [])
    if attachments:
        file_info = []
        for file_data in attachments:
            file_name = file_data.get("name", "Unknown file")
            file_type = file_data.get("filetype", "")
            file_size = file_data.get("size", 0)
            file_url = file_data.get("url_private", "")

            # Format file size
            if file_size > 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f}MB"
            elif file_size > 1024:
                size_str = f"{file_size / 1024:.1f}KB"
            else:
                size_str = f"{file_size}B"

            # Create a nice file description
            if file_type:
                file_desc = f"📎 **{file_name}** ({file_type}, {size_str})"
            else:
                file_desc = f"📎 **{file_name}** ({size_str})"

            # Add URL if available
            if file_url:
                file_desc += f" - [Download]({file_url})"

            file_info.append(file_desc)

        if text:
            text += "\\n\\n" + "\\n".join(file_info)
        else:
            text = "\\n".join(file_info)

    # Handle message attachments (rich content)
    message_attachments = msg.get("attachments", [])
    if message_attachments:
        for attachment in message_attachments:
            attachment_parts = []

            # Add service name/author
            if attachment.get("service_name"):
                attachment_parts.append(f"**{attachment['service_name']}**")
            elif attachment.get("author_name"):
                attachment_parts.append(f"**{attachment['author_name']}**")

            # Add attachment title
            if attachment.get("title"):
                title = attachment["title"]
                title_link = attachment.get("title_link", "")
                if title_link:
                    attachment_parts.append(f"🔗 **[{title}]({title_link})**")
                else:
                    attachment_parts.append(f"🔗 **{title}**")

            # Add attachment text/description
            if attachment.get("text"):
                attachment_parts.append(f"> {attachment['text']}")

            # Add fields if present
            if attachment.get("fields"):
                for field in attachment["fields"]:
                    field_title = field.get("title", "")
                    field_value = field.get("value", "")
                    if field_title and field_value:
                        attachment_parts.append(f"**{field_title}:** {field_value}")

            # Add footer info
            footer_parts = []
            if attachment.get("footer"):
                footer_parts.append(attachment["footer"])
            if attachment.get("ts"):
                footer_ts = datetime.fromtimestamp(float(attachment["ts"])).strftime("%Y-%m-%d %H:%M")
                footer_parts.append(footer_ts)

            if footer_parts:
                attachment_parts.append(f"*{' | '.join(footer_parts)}*")

            if attachment_parts:
                text += "\\n\\n" + "\\n".join(attachment_parts)

    # Handle reactions
    reactions = msg.get("reactions", [])
    if reactions:
        reaction_summary = []
        for reaction in reactions:
            emoji = reaction.get("name", "")
            count = reaction.get("count", 0)
            users_who_reacted = reaction.get("users", [])

            if emoji and count > 0:
                # Show who reacted if it's a small number
                if count <= 3 and users_who_reacted:
                    user_names = []
                    for user_id in users_who_reacted:
                        user_names.append(users.get(user_id, f"User_{user_id[-6:]}"))
                    reaction_summary.append(f":{emoji}: {', '.join(user_names)}")
                else:
                    reaction_summary.append(f":{emoji}: {count}")

        if reaction_summary:
            text += f"\\n\\n*Reactions: {', '.join(reaction_summary)}*"

    # Handle thread info
    thread_info = ""
    if msg.get("reply_count", 0) > 0:
        reply_count = msg["reply_count"]
        thread_info = f" 💬 {reply_count} {'reply' if reply_count == 1 else 'replies'}"

    # Replace newlines for markdown formatting
    text = text.replace("\n", "  \n")

    # Indent replies for threads
    prefix = "    " if msg.get("parent_user_id") else ""

    # Add thread indicator for replies
    thread_indicator = "↳ " if msg.get("parent_user_id") else ""

    return f"{prefix}- **{ts_str}** *{user_name}*{thread_info}: {thread_indicator}{text}"


def _create_safe_filename(channel_name: str, channel_id: str) -> str:
    """Create a safe filename from channel name, fallback to ID if needed."""
    # Try to use the channel name first, clean it up
    if channel_name and channel_name != channel_id:
        # Remove # or @ prefixes
        clean_name = channel_name.lstrip("#@")
        # Replace problematic characters
        safe_name = re.sub(r'[<>:"/\\|?*@]', '_', clean_name)
        # Remove consecutive underscores
        safe_name = re.sub(r'_+', '_', safe_name)
        # Remove leading/trailing underscores
        safe_name = safe_name.strip('_')

        if safe_name:
            return safe_name

    # Fallback to using channel ID
    return f"channel_{channel_id}"


def _is_valid_slack_id(slack_id: str) -> bool:
    """Check if a string is a valid Slack conversation ID format."""
    if not slack_id or not isinstance(slack_id, str):
        return False

    # Slack IDs should start with C (channels), D (DMs), G (groups), or U (users)
    # and be followed by alphanumeric characters, typically 9-11 characters total
    pattern = r'^[CDGU][A-Z0-9]{8,10}$'
    return bool(re.match(pattern, slack_id))


# -------------- Batch Processing Helper ------------------------------------
# This lightweight helper lets us update **multiple** channels in a single
# run.  It re-implements the essentials of the one-off export flow but without
# any interactive prompts so we can be safely called in a loop.


async def _export_single_channel(
    browser: 'SlackBrowser',
    channel_input_raw: str,
    users: Dict[str, str],
    conversations_cache: Optional[Dict[str, 'ConversationInfo']] = None,
) -> None:
    """Export *one* Slack conversation to its respective markdown file.

    Parameters
    ----------
    browser : SlackBrowser
        Live browser instance (already logged-in).
    channel_input_raw : str
        Whatever the user typed – can be a #name, plain name, or C/D/G-style id.
    users : Dict[str, str]
        Mapping of user IDs → human names for nicer formatting.
    conversations_cache : Optional mapping that speeds up name→id resolution.
    """
    sw = Stopwatch(f"export_channel:{channel_input_raw} ")
    print()

    channel_input = channel_input_raw.strip().lstrip("#@")

    # ------------------------------------------------------------------
    # Resolve channel ID & display name
    # ------------------------------------------------------------------
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None

    # 1) Direct ID provided?
    if _is_valid_slack_id(channel_input):
        channel_id = channel_input
        channel_name = f"channel_{channel_id}"
    else:
        # 2) Try cached conversations first (exact then partial match)
        if conversations_cache is None:
            conversations_cache = await browser.get_conversations()

        for _, conv_info in conversations_cache.items():
            if conv_info.name.lstrip("#@").lower() == channel_input.lower():
                channel_id = conv_info.id
                channel_name = conv_info.name
                break

        if not channel_id:
            for _, conv_info in conversations_cache.items():
                if channel_input.lower() in conv_info.name.lower():
                    channel_id = conv_info.id
                    channel_name = conv_info.name
                    break

    if not channel_id:
        print(f"⚠️  Skipping '{channel_input_raw}': unable to resolve channel.")
        logger.warning("Skipping channel '%s': unable to resolve channel ID", channel_input_raw)
        return
    sw.lap("resolve_channel")

    print(f"\n📥 Fetching messages for {ansi.cyan}{channel_name or channel_id}{ansi.reset}", flush=True)
    logger.info("Fetching messages for channel: %s (ID: %s)", channel_name or channel_id, channel_id)

    # ------------------------------------------------------------------
    # Incremental mode – determine the oldest timestamp we already have
    # ------------------------------------------------------------------
    tracker = _load_tracker()
    last_ts = tracker.get("channels", {}).get(channel_id, 0)
    if last_ts:
        print(
            f"🔄 Incremental mode: fetching messages newer than "
            f"{datetime.fromtimestamp(last_ts).strftime('%Y-%m-%d %H:%M:%S')}", 
            flush=True
        )
        logger.info("Incremental fetch – oldest ts for channel %s is %s", channel_id, last_ts)
    else:
        print("🆕 First-time export: fetching full history", flush=True)
        logger.info("First-time export – no existing tracker ts for channel %s", channel_id)

    # ------------------------------------------------------------------
    # Fetch messages (API or UI scroll) using the tracker timestamp
    # ------------------------------------------------------------------
    try:
        raw_messages = await browser.fetch_conversation_history(channel_id, oldest_ts=last_ts)
        sw.lap("fetch_history")
    except (TimeoutError, Error) as exc:
        print(f"⚠️  Failed to fetch history for {channel_input_raw}: {exc}")
        logger.error("Failed to fetch history for channel '%s': %s", channel_input_raw, exc)
        return

    # Filter out messages that we've already exported (UI-scroll fallback
    # can still return older items even when oldest_ts is passed).
    messages = [m for m in raw_messages if float(m.get("ts", 0)) > last_ts]

    if not messages:
        print(
            f"📭 No new messages for {ansi.yellow}{channel_name or channel_id}{ansi.reset}"
        )
        logger.info("No new messages found for channel: %s", channel_name or channel_id)
        return

    # Improve placeholder names when possible
    if channel_name is None or channel_name.startswith("channel_"):
        looked_up = await browser.get_channel_name(channel_id)
        if looked_up:
            channel_name = f"#{looked_up}"

    # ------------------------------------------------------------------
    # Write / append markdown
    # ------------------------------------------------------------------
    safe_name = await browser.conversation_filename(
        channel_id,
        channel_name or channel_input_raw,
        users,
        messages,
    )
    md_path = EXPORT_DIR / f"{safe_name}.md"

    write_mode = "a" if md_path.exists() else "w"
    with md_path.open(write_mode, encoding="utf-8") as f:
        if write_mode == "w":
            f.write(f"# {channel_name or channel_input_raw}\n\n")
            f.write(f"**Channel ID:** {channel_id}\n")
            f.write(f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Message Count:** {len(messages)}\n\n")
            f.write("---\n\n")

        for msg in messages:
            f.write(_markdown_line(msg, users) + "\n")

    # ------------------------------------------------------------------
    # Tracker update – remember newest ts so incremental runs are possible
    # ------------------------------------------------------------------
    tracker = _load_tracker()
    highest_ts = max(float(m.get("ts", 0)) for m in messages)
    tracker.setdefault("channels", {})[channel_id] = highest_ts
    _save_tracker(tracker)

    print(f"✅ Exported {ansi.green}{len(messages)}{ansi.reset} messages → {ansi.cyan}{md_path.name}{ansi.reset}")
    logger.info("Exported %d messages to %s for channel %s", len(messages), md_path, channel_name or channel_id)
    sw.lap("write_and_update_tracker")


# -------------- Main Script -------------------------------------------------

async def main():
    """Main async function."""
    sw = Stopwatch("main ")
    log_file = Path("src/growthkit/utils/logs/slack_fetcher.log")
    print(f"🚀 {ansi.cyan}Playwright-based Slack Fetcher{ansi.reset}")
    # Load settings here and pass down to browser
    settings = load_workspace_settings()
    print(f"📍 Workspace: {ansi.yellow}{settings.url}{ansi.reset}")
    print(f"📝 Detailed logs: {ansi.grey}{log_file.absolute()}{ansi.reset}")
    print()

    logger.info("Slack fetcher started for workspace: %s", settings.url)

    # CLI flags
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--no-storage-state", action="store_true", help="Disable loading/saving storage_state")
    parser.add_argument("--fresh", action="store_true", help="Ignore any saved state and start clean")
    parser.add_argument("--headful-login", action="store_true", help="Force an interactive headful login and refresh storage state")
    # Accept unknown so we don't break existing invocation styles
    args, _unknown = parser.parse_known_args()

    headless = args.headless and not args.headful_login
    use_storage_state = not args.no_storage_state
    fresh = bool(args.fresh)
    if args.headful_login:
        headless = False
        fresh = True

    browser = SlackBrowser(settings=settings)

    try:
        # Start browser with requested options
        await browser.start(headless=headless, use_storage_state=use_storage_state, fresh=fresh)
        sw.lap("browser_start")

        # Ensure we're logged in
        if not await browser.ensure_logged_in():
            print("❌ Failed to log in. Exiting.")
            logger.error("Failed to log in to Slack workspace")
            return
        sw.lap("login")

        # Load and display available channels
        print(f"\n🔍 {ansi.cyan}Discovering available channels...{ansi.reset}")
        conversations = await browser.get_conversations()
        sw.lap("conversation_discovery")

        # Separate and sort different conversation types
        channels = []
        dms = []
        groups = []

        for conv_info in conversations.values():
            if conv_info.conversation_type == ConversationType.CHANNEL:
                channels.append(conv_info.name.lstrip("#"))
            elif conv_info.conversation_type == ConversationType.DM:
                dms.append(conv_info.name.lstrip("@"))
            elif conv_info.conversation_type == ConversationType.MULTI_PERSON_DM:
                groups.append(conv_info.name.lstrip("@"))

        # Display channels in a nice format
        print(f"\n📁 {ansi.green}Available Channels:{ansi.reset}")
        if channels:
            channels.sort()
            # Display in columns for better readability
            for i in range(0, len(channels), 3):
                row_channels = channels[i:i+3]
                formatted_channels = [f"#{ch}" for ch in row_channels]
                print(f"  {' • '.join(formatted_channels)}")
        else:
            print("  No public channels found")

        if dms:
            print(f"\n💬 {ansi.yellow}Direct Messages:{ansi.reset} {len(dms)} conversations")

        if groups:
            print(f"\n👥 {ansi.magenta}Group Messages:{ansi.reset} {len(groups)} conversations")

        # Ask user what they want to extract
        print(f"\n{ansi.cyan}What would you like to extract?{ansi.reset}")
        print("  • Enter a channel name (e.g., 'general' or '#general')")
        print("  • Enter a channel ID (e.g., 'C1234567890')")
        print("  • Enter multiple channels separated by commas")

        user_input = input("\nTarget channel(s): ").strip()

        # ------------------------------------------------------------------
        # Batch mode – allow comma-separated list so we can update multiple
        # conversations in one run.
        # ------------------------------------------------------------------
        # Normalise to a list (filtering out accidental double-commas / whitespace)
        channel_inputs = [s.strip() for s in user_input.split(',') if s.strip()]
        sw.lap("user_input")

        # If more than one entry, switch to batch processing and exit early
        if len(channel_inputs) > 1:
            print(f"🔄 Processing {ansi.cyan}{len(channel_inputs)}{ansi.reset} channels…")
            logger.info("Starting batch processing for %d channels", len(channel_inputs))
            users = await browser.get_user_list()
            conversations = await browser.get_conversations()
            for target in channel_inputs:
                await _export_single_channel(browser, target, users, conversations)
            logger.info("Completed batch processing for %d channels", len(channel_inputs))
            sw.lap("batch_export")
            return

        if not channel_inputs:
            print("❌ No channel specified. Exiting.")
            logger.error("No channel specified by user")
            return

        # Clean up the input
        channel_input = channel_inputs[0].lstrip("#@")

        # Try to find the channel
        channel_id = None
        channel_name = None

        # If it looks like a channel ID (starts with C, D, or G)
        if channel_input.startswith(('C', 'D', 'G')) and len(channel_input) > 8:
            channel_id = channel_input
            channel_name = f"channel_{channel_id}"
            print(f"🎯 Using channel ID: {ansi.cyan}{channel_id}{ansi.reset}")
            logger.info("Using direct channel ID: %s", channel_id)
        else:
            # Try to find by name in conversations
            if 'conversations' in locals():
                # Look for exact match first
                for _, conv_info in conversations.items():
                    if conv_info.name.lstrip("#@").lower() == channel_input.lower():
                        channel_id = conv_info.id
                        channel_name = conv_info.name
                        print(f"🎯 Found channel: {ansi.green}{conv_info}{ansi.reset}")
                        logger.info("Found exact channel match: %s (ID: %s)", conv_info.name, conv_info.id)
                        break

                # If no exact match, try partial match
                if not channel_id:
                    matches = []
                    for _, conv_info in conversations.items():
                        if channel_input.lower() in conv_info.name.lower():
                            matches.append(conv_info)

                    if len(matches) == 1:
                        channel_id = matches[0].id
                        channel_name = matches[0].name
                        print(f"🎯 Found matching channel: {ansi.green}{matches[0]}{ansi.reset}")
                        logger.info("Found partial channel match: %s (ID: %s)", matches[0].name, matches[0].id)
                    elif len(matches) > 1:
                        print(f"❌ Multiple channels match '{channel_input}':")
                        logger.warning("Multiple channels match '%s': %d matches found", channel_input, len(matches))
                        for conv_info in matches:
                            print(f"    {conv_info}")
                        print("Please be more specific.")
                        return

            # If still not found, try loading conversations
            if not channel_id:
                print("🔍 Searching for channel...")
                logger.info("Loading conversations to search for channel: %s", channel_input)
                conversations = await browser.get_conversations()

                for _, conv_info in conversations.items():
                    if conv_info.name.lstrip("#@").lower() == channel_input.lower():
                        channel_id = conv_info.id
                        channel_name = conv_info.name
                        print(f"🎯 Found channel: {ansi.green}{conv_info}{ansi.reset}")
                        logger.info("Found channel after conversation reload: %s (ID: %s)", conv_info.name, conv_info.id)
                        break

            # Last resort: assume it's a channel name and try to find it
            if not channel_id:
                # Use the input as channel name and let the API try to find it
                channel_name = f"#{channel_input}"
                print(f"🎯 Attempting to extract channel: {ansi.yellow}{channel_name}{ansi.reset}")
                print("    (Channel ID will be determined from API calls)")
                logger.info("Channel ID not found, attempting discovery via API calls for: %s", channel_name)

        # Get users for better formatting
        print("👥 Loading user list...")
        users = await browser.get_user_list()

        # Fetch messages
        print(f"📥 Fetching messages from {channel_name or channel_input}...")

        if channel_id:
            # Validate the channel ID format before using it
            if not _is_valid_slack_id(channel_id):
                print(f"❌ Invalid Slack ID format: {ansi.red}{channel_id}{ansi.reset}")
                print("    Slack IDs should start with C (channels), D (DMs), or G (groups)")
                logger.error("Invalid Slack ID format: %s", channel_id)
                return

            messages = await browser.fetch_conversation_history(channel_id, oldest_ts=0)
        else:
            # If we don't have a valid ID, we need to find it through API calls
            # Don't try to navigate to invalid URLs that cause Slack to glitch
            print("🔍 Channel ID not found. Browsing workspace to discover channel IDs...")
            logger.info("Channel ID not found, browsing workspace to discover channel IDs")

            try:
                # Navigate to safer URLs that are more likely to work
                safe_urls = [
                    f"https://app.slack.com/client/{browser.settings.team_id}",  # Main workspace
                    f"https://app.slack.com/client/{browser.settings.team_id}/browse-channels",  # Browse channels
                    browser.settings.url  # Fallback to main URL
                ]

                channel_found = False

                for url in safe_urls:
                    try:
                        print(f"🌐 Navigating to {ansi.cyan}{url}{ansi.reset}")
                        logger.debug("Navigating to URL: %s", url)
                        await browser.page.goto(url, timeout=10000)
                        await browser.page.wait_for_timeout(3000)

                        # Load conversations to get the real IDs
                        conversations = await browser.get_conversations()

                        # Try to find the channel by name in the loaded conversations
                        for _, conv_info in conversations.items():
                            if conv_info.name.lstrip("#@").lower() == channel_input.lower():
                                channel_id = conv_info.id
                                channel_name = conv_info.name
                                print(f"✅ Found channel: {ansi.green}{conv_info}{ansi.reset} (ID: {ansi.cyan}{channel_id}{ansi.reset})")
                                logger.info("Found channel via workspace navigation: %s (ID: %s)", conv_info.name, channel_id)
                                channel_found = True
                                break

                        if channel_found:
                            break

                    except (TimeoutError, Error) as e:
                        print(f"⚠️  Failed to load {url}: {e}")
                        logger.debug("Failed to load URL %s: %s", url, e)
                        continue

                if not channel_found:
                    print(f"❌ Could not find channel '{ansi.red}{channel_input}{ansi.reset}'.")
                    print("Available channels:")
                    logger.error("Could not find channel '%s'", channel_input)
                    conversations = await browser.get_conversations()
                    for _, conv_info in list(conversations.items())[:10]:  # Show first 10
                        print(f"    {conv_info}")
                    if len(conversations) > 10:
                        print(f"    ... and {ansi.grey}{len(conversations) - 10} more{ansi.reset}")
                    return

                # Now fetch with the proper ID
                messages = await browser.fetch_conversation_history(channel_id, oldest_ts=0)

            except (TimeoutError, Error) as e:
                print(f"❌ Error finding channel: {e}")
                logger.error("Error finding channel: %s", e)
                return

        if not messages:
            print("📭 No messages found. The channel might be empty or inaccessible.", flush=True)
            logger.info("No messages found for channel %s (ID: %s)", channel_name or channel_input, channel_id)
            return

        # Try to improve channel_name if it's still a generic placeholder
        if channel_id and (not channel_name or channel_name.startswith("channel_")):
            looked_up = await browser.get_channel_name(channel_id)
            if looked_up:
                channel_name = f"#{looked_up}"

        # Save to markdown with friendly filename
        safe_name = await browser.conversation_filename(channel_id or "", channel_name or channel_input, users, messages)

        md_path = EXPORT_DIR / f"{safe_name}.md"

        # If an old placeholder file exists, rename it
        placeholder_name = _create_safe_filename(f"channel_{channel_id}", channel_id) if channel_id else None
        if placeholder_name:
            old_path = EXPORT_DIR / f"{placeholder_name}.md"
            if old_path.exists() and old_path != md_path:
                try:
                    old_path.rename(md_path)
                    print(f"🔄 Renamed {ansi.yellow}{old_path.name}{ansi.reset} -> {ansi.cyan}{md_path.name}{ansi.reset}")
                    logger.info("Renamed old file %s to %s", old_path.name, md_path.name)
                except OSError as e:
                    print(f"⚠️  Could not rename old file: {e}")
                    logger.warning("Could not rename old file: %s", e)

        write_mode = "a" if md_path.exists() else "w"
        logger.info("Writing messages to file: %s (mode: %s)", md_path, write_mode)
        with md_path.open(write_mode, encoding="utf-8") as f:
            if write_mode == "w":
                f.write(f"# {channel_name or channel_input}\n\n")
                if channel_id:
                    f.write(f"**Channel ID:** {channel_id}\n")
                f.write(f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**Message Count:** {len(messages)}\n\n")
                f.write("---\n\n")

            # Append new messages
            for msg in messages:
                f.write(_markdown_line(msg, users) + "\n")

        # Update tracker
        if messages and channel_id:
            tracker = _load_tracker()
            highest_ts = max(float(m["ts"]) for m in messages)
            tracker["channels"][channel_id] = highest_ts
            _save_tracker(tracker)
            logger.debug("Updated tracker with latest timestamp: %f for channel %s", highest_ts, channel_id)

        print(f"✅ Exported {ansi.green}{len(messages)}{ansi.reset} messages to {ansi.cyan}{md_path.name}{ansi.reset}")
        print(f"📁 File saved: {ansi.grey}{md_path.absolute()}{ansi.reset}")
        logger.info("Export completed successfully: %d messages to %s", len(messages), md_path.absolute())
        sw.lap("single_export")

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        logger.warning("Script interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error("Unexpected error occurred: %s", e, exc_info=True)
        traceback.print_exc()
    finally:
        await browser.close()
        logger.info("Slack fetcher session ended")
        sw.lap("shutdown")


def run_main():
    """Run the async main function."""
    # Ensure workspace config exists and populate runtime settings
    try:
        load_workspace_settings()
    except RuntimeError as exc:
        # Graceful, user-friendly guidance if placeholders still exist
        print("❌ Workspace is not configured.")
        print("   Edit `config/slack/workspace.py` with your real Slack URL and team ID.")
        print(f"   Details: {exc}")
        return
    ensure_chromium_installed()
    asyncio.run(main())


if __name__ == "__main__":
    run_main()
