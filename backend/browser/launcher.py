"""
Centralized Browser Launcher
=============================
Supports many browsers via Playwright:
  - chromium (bundled Chromium, tries Chrome channel first)
  - chrome   (user's installed Google Chrome)
  - msedge   (user's installed Microsoft Edge)
  - brave    (user's installed Brave Browser)
  - opera    (user's installed Opera / Opera GX)
  - firefox  (bundled Firefox)
  - webkit   (bundled WebKit — closest to Safari)
  - safari   (alias for webkit)

Defaults to **headful** mode so users can see everything.

Usage (sync):
    from browser.launcher import launch_persistent, get_page, BrowserType

    with sync_playwright() as p:
        context = launch_persistent(p, "profile_dir", browser_type="brave")
        page = get_page(context)
        ...

Usage (async):
    from browser.launcher import launch_persistent_async, get_page_async

    async with async_playwright() as p:
        context = await launch_persistent_async(p, "profile_dir", browser_type="opera")
        page = await get_page_async(context)
        ...
"""

from __future__ import annotations

import os
import platform
import textwrap
import shutil
from typing import Literal


# ── Public types & defaults ──────────────────────────────────────────

BrowserType = Literal[
    "chromium", "chrome", "msedge", "brave", "opera",
    "firefox", "webkit", "safari",
]

SUPPORTED_BROWSERS: list[BrowserType] = [
    "chrome", "chromium", "msedge", "brave", "opera",
    "firefox", "webkit", "safari",
]
DEFAULT_BROWSER: BrowserType = os.environ.get("BROWSER_TYPE", "chromium")  # type: ignore[assignment]
DEFAULT_HEADLESS: bool = os.environ.get("HEADLESS", "true").lower() in ("true", "1", "yes")

# ── Anti-detection constants ─────────────────────────────────────────

_STEALTH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_STEALTH_INIT_SCRIPT = textwrap.dedent(r"""
    // --- Playwright stealth patches ---

    // 1. Hide navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    // 2. Fake navigator.plugins (headless has empty list)
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' },
        ],
    });

    // 3. Fake navigator.languages (headless sometimes has empty array)
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en', 'ja'],
    });

    // 4. Add window.chrome object (missing in headless)
    if (!window.chrome) {
        window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
    }

    // 5. Override Permissions.query to report 'prompt' for notifications
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => {
        if (parameters.name === 'notifications') {
            return Promise.resolve({ state: Notification.permission });
        }
        return originalQuery(parameters);
    };

    // 6. Spoof navigator.platform
    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });

    // 7. Fake window.outerWidth/outerHeight (headless often has 0)
    if (window.outerWidth === 0) {
        Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth });
        Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight });
    }
""")

# engine:   which Playwright engine to use (chromium / firefox / webkit)
# channel:  Playwright channel name (only for chromium-based browsers)
# exe_hint: possible executable names / paths to search for on the system
_BROWSER_CONFIG: dict[str, dict] = {
    "chrome":   {"engine": "chromium", "channel": "chrome", "exe_hint": []},
    "chromium": {"engine": "chromium", "channel": "chrome", "exe_hint": []},
    "msedge":   {"engine": "chromium", "channel": "msedge", "exe_hint": []},
    "brave": {
        "engine": "chromium",
        "channel": None,
        "exe_hint": [
            # Linux
            "brave-browser", "brave-browser-stable",
            "/usr/bin/brave-browser",
            "/usr/bin/brave-browser-stable",
            "/opt/brave.com/brave/brave-browser",
            # macOS
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            # Windows
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ],
    },
    "opera": {
        "engine": "chromium",
        "channel": None,
        "exe_hint": [
            # Linux
            "opera", "opera-stable",
            "/usr/bin/opera",
            "/usr/bin/opera-stable",
            "/snap/bin/opera",
            # macOS
            "/Applications/Opera.app/Contents/MacOS/Opera",
            "/Applications/Opera GX.app/Contents/MacOS/Opera",
            # Windows
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\opera.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe"),
            os.path.expandvars(r"%APPDATA%\Opera Software\Opera Stable\opera.exe"),
            os.path.expandvars(r"%APPDATA%\Opera Software\Opera GX Stable\opera.exe"),
        ],
    },
    "firefox": {"engine": "firefox", "channel": None, "exe_hint": []},
    "webkit":  {"engine": "webkit",  "channel": None, "exe_hint": []},
    "safari":  {"engine": "webkit",  "channel": None, "exe_hint": []},  # alias
}


# ── Internal helpers ─────────────────────────────────────────────────

def _find_executable(hints: list[str]) -> str | None:
    """Try to locate a browser executable from a list of hints."""
    for hint in hints:
        # Absolute path?
        if os.path.isfile(hint):
            return hint
        # On PATH?
        found = shutil.which(hint)
        if found:
            return found
    return None


def _engine(playwright, browser_type: BrowserType):
    """Return the Playwright engine object for a given browser_type."""
    config = _BROWSER_CONFIG.get(browser_type)
    if config is None:
        raise ValueError(
            f"Unsupported browser_type={browser_type!r}. "
            f"Choose from: {', '.join(SUPPORTED_BROWSERS)}"
        )
    engine_name = config["engine"]
    engines = {
        "chromium": playwright.chromium,
        "firefox": playwright.firefox,
        "webkit":  playwright.webkit,
    }
    return engines[engine_name]


def _build_opts(
    browser_type: BrowserType,
    headless: bool,
    extra: dict,
) -> dict:
    """Build the kwargs dict for launch / launch_persistent_context."""
    opts: dict = {"headless": headless, **extra}
    config = _BROWSER_CONFIG.get(browser_type, {})

    # Disable browser-level notification prompts for Chromium-based browsers
    if config.get("engine") == "chromium":
        existing_args = list(opts.get("args", []))
        if not any("--disable-notifications" in a for a in existing_args):
            existing_args.append("--disable-notifications")
            
        if headless:
            for flag in [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1280,720",
            ]:
                if flag not in existing_args:
                    existing_args.append(flag)
                    
        opts["args"] = existing_args

    # For Brave / Opera: find the executable and set executablePath
    if config.get("exe_hint"):
        exe = _find_executable(config["exe_hint"])
        if exe:
            opts.setdefault("executable_path", exe)
        else:
            raise FileNotFoundError(
                f"Could not find {browser_type} on this system. "
                f"Make sure it is installed. Searched: {config['exe_hint'][:3]}..."
            )
    # For chrome / msedge: use Playwright's built-in channel
    elif config.get("channel"):
        opts.setdefault("channel", config["channel"])

    return opts


# ── Sync API ─────────────────────────────────────────────────────────

def launch_persistent(
    playwright,
    user_data_dir: str,
    browser_type: BrowserType = DEFAULT_BROWSER,
    headless: bool = DEFAULT_HEADLESS,
    **extra,
):
    """Launch a **persistent** browser context (sync).

    Persistent contexts keep cookies / local-storage between runs.
    Works with all three engines.
    """
    engine = _engine(playwright, browser_type)
    opts = _build_opts(browser_type, headless, extra)

    try:
        return engine.launch_persistent_context(user_data_dir, **opts)
    except Exception:
        # Chrome channel not installed → fall back to plain Chromium
        if "channel" in opts:
            opts.pop("channel")
            return engine.launch_persistent_context(user_data_dir, **opts)
        raise


def launch_browser(
    playwright,
    browser_type: BrowserType = DEFAULT_BROWSER,
    headless: bool = DEFAULT_HEADLESS,
    **extra,
):
    """Launch a non-persistent browser (sync)."""
    engine = _engine(playwright, browser_type)
    opts = _build_opts(browser_type, headless, extra)

    try:
        return engine.launch(**opts)
    except Exception:
        if "channel" in opts:
            opts.pop("channel")
            return engine.launch(**opts)
        raise


def get_page(context):
    """Return the first page of a context, or create one (sync)."""
    return context.pages[0] if context.pages else context.new_page()


# ── Async API ────────────────────────────────────────────────────────

async def launch_persistent_async(
    playwright,
    user_data_dir: str,
    browser_type: BrowserType = DEFAULT_BROWSER,
    headless: bool = DEFAULT_HEADLESS,
    **extra,
):
    """Launch a **persistent** browser context (async)."""
    engine = _engine(playwright, browser_type)
    opts = _build_opts(browser_type, headless, extra)

    try:
        return await engine.launch_persistent_context(user_data_dir, **opts)
    except Exception:
        if "channel" in opts:
            opts.pop("channel")
            return await engine.launch_persistent_context(user_data_dir, **opts)
        raise


async def launch_browser_async(
    playwright,
    browser_type: BrowserType = DEFAULT_BROWSER,
    headless: bool = DEFAULT_HEADLESS,
    **extra,
):
    """Launch a non-persistent browser (async)."""
    engine = _engine(playwright, browser_type)
    opts = _build_opts(browser_type, headless, extra)

    try:
        return await engine.launch(**opts)
    except Exception:
        if "channel" in opts:
            opts.pop("channel")
            return await engine.launch(**opts)
        raise


async def get_page_async(context):
    """Return the first page of a context, or create one (async)."""
    return context.pages[0] if context.pages else await context.new_page()


# ── Notification popup dismissal ─────────────────────────────────────

def dismiss_notification_popup(page, timeout: int = 3000):
    """Dismiss Instagram's 'Turn on Notifications' dialog if it appears (sync)."""
    try:
        btn = page.wait_for_selector(
            'button:has-text("Not Now"), '
            'button:has-text("Cancel"), '
            'button:has-text("Not now")',
            timeout=timeout,
        )
        if btn:
            btn.click()
    except Exception:
        pass  # no popup appeared — nothing to do


async def dismiss_notification_popup_async(page, timeout: int = 3000):
    """Dismiss Instagram's 'Turn on Notifications' dialog if it appears (async)."""
    try:
        btn = await page.wait_for_selector(
            'button:has-text("Not Now"), '
            'button:has-text("Cancel"), '
            'button:has-text("Not now")',
            timeout=timeout,
        )
        if btn:
            await btn.click()
    except Exception:
        pass  # no popup appeared — nothing to do


# ── Cookie-based launch (no persistent profile needed) ───────────────

_DEFAULT_VIEWPORT = {"width": 1280, "height": 720}


def _apply_stealth(context, headless: bool = False):
    """Inject anti-detection stealth script into a sync context."""
    if headless:
        context.add_init_script(_STEALTH_INIT_SCRIPT)


async def _apply_stealth_async(context, headless: bool = False):
    """Inject anti-detection stealth script into an async context."""
    if headless:
        await context.add_init_script(_STEALTH_INIT_SCRIPT)


def launch_with_cookies(
    playwright,
    cookies: list[dict],
    browser_type: BrowserType = DEFAULT_BROWSER,
    headless: bool = DEFAULT_HEADLESS,
    goto_url: str = "https://www.instagram.com/",
    **extra,
):
    """
    Launch a **non-persistent** browser, inject *cookies*, navigate to
    Instagram and return ``(browser, context, page)`` (sync).

    When running headless, a realistic user-agent and stealth init
    script are injected to avoid bot detection by Instagram.

    The caller MUST close ``context`` and ``browser`` when done.
    """
    browser = launch_browser(playwright, browser_type=browser_type, headless=headless, **extra)
    ctx_opts: dict = {"viewport": _DEFAULT_VIEWPORT}
    if headless:
        ctx_opts["user_agent"] = _STEALTH_USER_AGENT
    context = browser.new_context(**ctx_opts)
    _apply_stealth(context, headless)
    context.add_cookies(cookies)
    page = context.new_page()
    page.goto(goto_url, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    dismiss_notification_popup(page)
    return browser, context, page


async def launch_with_cookies_async(
    playwright,
    cookies: list[dict],
    browser_type: BrowserType = DEFAULT_BROWSER,
    headless: bool = DEFAULT_HEADLESS,
    goto_url: str = "https://www.instagram.com/",
    **extra,
):
    """
    Async version of :func:`launch_with_cookies`.
    Returns ``(browser, context, page)``.

    When running headless, a realistic user-agent and stealth init
    script are injected to avoid bot detection by Instagram.
    """
    browser = await launch_browser_async(playwright, browser_type=browser_type, headless=headless, **extra)
    ctx_opts: dict = {"viewport": _DEFAULT_VIEWPORT}
    if headless:
        ctx_opts["user_agent"] = _STEALTH_USER_AGENT
    context = await browser.new_context(**ctx_opts)
    await _apply_stealth_async(context, headless)
    await context.add_cookies(cookies)
    page = await context.new_page()
    await page.goto(goto_url, wait_until="domcontentloaded")
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    await dismiss_notification_popup_async(page)
    return browser, context, page
