"""
This file is used to ensure that the Chromium runtime is installed for Playwright.
"""
import sys
import subprocess

from playwright.sync_api import sync_playwright
from playwright.sync_api import Error as PlaywrightError

def ensure_chromium_installed() -> None:
    """
    Ensure that the Chromium runtime is installed for Playwright.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()

    except PlaywrightError:
        print("🔄 Installing Playwright Chromium runtime:")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True
        )
