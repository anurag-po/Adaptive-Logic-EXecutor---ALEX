"""
ALEX — Browser Actions (Phase 2)
Simple browser opens (Phase 1) + Playwright automation (Phase 2).
Playwright browser instance is reused within a session and auto-closed
after BROWSER_IDLE_TIMEOUT seconds of inactivity.
"""

import os
import webbrowser
import threading
import time
from urllib.parse import quote_plus

import config
from utils.helpers import get_logger

logger = get_logger()

# ═══════════════════════════════════════════════════════════════════
# PHASE 1 — Simple browser opens (unchanged)
# ═══════════════════════════════════════════════════════════════════


def open_website(url: str) -> str:
    """Open a URL in the default browser."""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    webbrowser.open(url)
    logger.info(f"Opened website: {url}")
    return f"Opened {url} in your browser."


def search_google(query: str) -> str:
    """Search Google for the given query."""
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    webbrowser.open(url)
    logger.info(f"Google search: {query}")
    return f"Searching Google for '{query}'."


def open_youtube_video(query: str) -> str:
    """Search YouTube for the given query."""
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    webbrowser.open(url)
    logger.info(f"YouTube search: {query}")
    return f"Searching YouTube for '{query}'."


def play_youtube_music(query: str) -> str:
    """Search YouTube Music for the given query."""
    url = f"https://music.youtube.com/search?q={quote_plus(query)}"
    webbrowser.open(url)
    logger.info(f"YouTube Music search: {query}")
    return f"Searching YouTube Music for '{query}'."


# ═══════════════════════════════════════════════════════════════════
# PHASE 2 — Playwright Browser Automation
# ═══════════════════════════════════════════════════════════════════

# Shared browser instance (lazy-initialized, auto-cleaned)
_playwright = None
_browser = None
_browser_lock = threading.Lock()
_last_used = 0
_cleanup_thread = None


def _get_browser():
    """Get or create a shared headless Chromium browser instance."""
    global _playwright, _browser, _last_used, _cleanup_thread

    with _browser_lock:
        _last_used = time.time()

        if _browser and _browser.is_connected():
            return _browser

        try:
            from playwright.sync_api import sync_playwright

            logger.info("Launching headless Chromium browser...")
            _playwright = sync_playwright().start()
            _browser = _playwright.chromium.launch(headless=True)
            logger.info("Chromium browser ready.")

            # Start idle cleanup thread
            if _cleanup_thread is None or not _cleanup_thread.is_alive():
                _cleanup_thread = threading.Thread(
                    target=_idle_cleanup, daemon=True
                )
                _cleanup_thread.start()

            return _browser

        except ImportError:
            logger.error(
                "Playwright not installed. "
                "Run: pip install playwright && playwright install chromium"
            )
            raise RuntimeError("Playwright not installed.")
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            raise


def _idle_cleanup():
    """Auto-close browser after BROWSER_IDLE_TIMEOUT seconds of inactivity."""
    global _playwright, _browser

    while True:
        time.sleep(30)  # Check every 30 seconds
        with _browser_lock:
            if _browser and (time.time() - _last_used > config.BROWSER_IDLE_TIMEOUT):
                logger.info("Browser idle timeout — closing Chromium.")
                try:
                    _browser.close()
                    _playwright.stop()
                except Exception:
                    pass
                _browser = None
                _playwright = None
                return


def browse_and_extract(url: str, selector: str = "body") -> str:
    """
    Navigate to a URL and extract text content from a CSS selector.
    Defaults to extracting all body text if no selector specified.
    """
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        browser = _get_browser()
        page = browser.new_page()

        page.goto(url, timeout=config.BROWSER_TIMEOUT)
        page.wait_for_load_state("domcontentloaded")

        element = page.query_selector(selector)
        if element:
            text = element.inner_text()
            # Truncate very long text
            if len(text) > 2000:
                text = text[:2000] + "... (truncated)"
            logger.info(
                f"Extracted {len(text)} chars from {url} ({selector})"
            )
            page.close()
            return f"Extracted from {url}:\n{text}"
        else:
            page.close()
            return f"No element found matching selector '{selector}' on {url}."

    except RuntimeError as e:
        return str(e)
    except Exception as e:
        logger.error(f"Browse and extract failed: {e}")
        return f"Error browsing {url}: {e}"


def fill_web_form(url: str, fields: str) -> str:
    """
    Navigate to a URL and fill form fields.
    Fields should be a JSON string or comma-separated key=value pairs.
    Example: "name=John, email=john@example.com"
    """
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        import json

        # Parse fields — accept JSON dict or key=value pairs
        if isinstance(fields, dict):
            field_map = fields
        elif fields.strip().startswith("{"):
            field_map = json.loads(fields)
        else:
            field_map = {}
            for pair in fields.split(","):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    field_map[k.strip()] = v.strip()

        if not field_map:
            return "No valid form fields provided."

        browser = _get_browser()
        page = browser.new_page()
        page.goto(url, timeout=config.BROWSER_TIMEOUT)
        page.wait_for_load_state("domcontentloaded")

        filled = []
        for selector, value in field_map.items():
            try:
                page.fill(selector, value)
                filled.append(selector)
            except Exception as e:
                logger.warning(f"Could not fill '{selector}': {e}")

        page.close()

        if filled:
            return f"Filled {len(filled)} field(s) on {url}: {', '.join(filled)}"
        else:
            return f"Could not fill any fields on {url}."

    except RuntimeError as e:
        return str(e)
    except Exception as e:
        logger.error(f"Form fill failed: {e}")
        return f"Error filling form on {url}: {e}"


def take_page_screenshot(url: str, save_path: str = None) -> str:
    """Take a screenshot of a webpage."""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    if not save_path:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(desktop, f"page_{timestamp}.png")

    try:
        browser = _get_browser()
        page = browser.new_page()
        page.goto(url, timeout=config.BROWSER_TIMEOUT)
        page.wait_for_load_state("networkidle")

        page.screenshot(path=save_path, full_page=True)
        page.close()

        logger.info(f"Page screenshot saved: {save_path}")
        return f"Screenshot of {url} saved to {save_path}."

    except RuntimeError as e:
        return str(e)
    except Exception as e:
        logger.error(f"Page screenshot failed: {e}")
        return f"Error taking screenshot of {url}: {e}"


def click_element(url: str, selector: str) -> str:
    """Navigate to a URL and click an element matching the CSS selector."""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        browser = _get_browser()
        page = browser.new_page()
        page.goto(url, timeout=config.BROWSER_TIMEOUT)
        page.wait_for_load_state("domcontentloaded")

        element = page.query_selector(selector)
        if element:
            element.click()
            page.wait_for_load_state("domcontentloaded")
            title = page.title()
            page.close()
            logger.info(f"Clicked '{selector}' on {url}")
            return f"Clicked element '{selector}' on {url}. Page title: {title}"
        else:
            page.close()
            return f"No element found matching '{selector}' on {url}."

    except RuntimeError as e:
        return str(e)
    except Exception as e:
        logger.error(f"Click element failed: {e}")
        return f"Error clicking element on {url}: {e}"
