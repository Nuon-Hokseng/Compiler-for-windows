from playwright.sync_api import sync_playwright
import time
import random
from browser.scrolling import human_mouse_move
from browser.launcher import (
    launch_with_cookies,
    BrowserType,
    DEFAULT_BROWSER,
    DEFAULT_HEADLESS,
)


def click_search_button(page, log=print):
    time.sleep(random.uniform(0.5, 1.0))

    selectors = [
        'a[href="#"]:has(svg[aria-label="Search"])',
        'xpath=//a[.//svg[@aria-label="Search"]]',
        'xpath=//span[text()="Search"]/ancestor::a',
        '[role="link"]:has(svg[aria-label="Search"])',
    ]

    for selector in selectors:
        try:
            btn = page.query_selector(selector)
            if btn:
                btn.click()
                log("Search button clicked!")
                return True
        except:
            continue

    # SVG ancestor fallback
    try:
        btn = page.query_selector('xpath=//svg[@aria-label="Search"]/ancestor::a[1]')
        if btn:
            btn.click()
            log("Search button clicked!")
            return True
    except:
        pass

    # Keyboard fallback
    log("Search button not found, trying keyboard shortcut...")
    page.keyboard.press('/')
    return True


def _get_search_input(page):
    """
    Return the search input ElementHandle using JS — reliable on both layouts.
    Skips Playwright's visibility engine entirely.
    """
    try:
        handle = page.evaluate_handle("""
            () => {
                let el = document.querySelector('input[aria-label="Search input"]');
                if (el) return el;
                const all = document.querySelectorAll('input[placeholder="Search"][type="text"]');
                for (const inp of all) {
                    const r = inp.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) return inp;
                }
                return null;
            }
        """)
        return handle.as_element()
    except:
        return None


def _activate_input_via_js(page, log=print):
    """
    Focus + click the input purely through JS, bypassing any overlapping elements.
    This is always used for the /explore/ layout where a div intercepts pointer events.
    """
    try:
        ok = page.evaluate("""
            () => {
                let el = document.querySelector('input[aria-label="Search input"]');
                if (!el) el = document.querySelector('input[placeholder="Search"][type="text"]');
                if (!el) return false;
                el.scrollIntoView({ block: 'center' });
                el.focus();
                return true;
            }
        """)
        return ok
    except:
        return False


def find_and_activate_search_input(page, log=print):
    # --- Detect layout ---
    # Wait briefly for Chrome to navigate to /explore/ after the search button click.
    # If it doesn't navigate, we're on the old slide-in panel layout.
    on_explore = False
    try:
        page.wait_for_url("**/explore/**", timeout=3000)
        on_explore = True
        log("Chrome /explore/ layout detected.")
    except:
        pass  # Old layout — search panel slides in on the same page.

    log(f"Current URL: {page.url}")

    # --- Wait for input to exist in DOM ---
    log("Waiting for search input in DOM...")
    found = False
    for timeout in [4000, 7000, 10000]:
        try:
            el = page.wait_for_selector(
                'input[aria-label="Search input"], input[placeholder="Search"][type="text"]',
                state="attached",
                timeout=timeout,
            )
            if el:
                found = True
                log(f"Search input found in DOM.")
                break
        except:
            log(f"Not found yet (tried {timeout}ms)...")

    if not found:
        # Last resort — check via JS
        el = _get_search_input(page)
        if not el:
            log("❌ Search input not found by any method.")
            return None
        log("Found input via JS fallback.")

    # --- Activate the input ---
    if on_explore:
        # On /explore/, a div[role="button"] sits over the input and blocks all
        # pointer events. Skip hover entirely — go straight to JS focus.
        log("Using JS focus (explore layout — overlay blocks pointer events).")
        if not _activate_input_via_js(page, log):
            log("❌ JS activation failed.")
            return None
    else:
        # Old layout: slide-in panel. Native Playwright click works fine here.
        try:
            el = page.wait_for_selector(
                'input[aria-label="Search input"], input[placeholder="Search"][type="text"]',
                state="visible",
                timeout=5000,
            )
            el.scroll_into_view_if_needed()
            time.sleep(random.uniform(0.2, 0.4))
            el.click()
            log("Search input activated via Playwright click (slide-in layout).")
        except Exception as e:
            log(f"Native click failed ({e}), falling back to JS focus...")
            if not _activate_input_via_js(page, log):
                log("❌ JS activation failed.")
                return None

    time.sleep(random.uniform(0.4, 0.8))

    # Return a fresh handle after activation
    return _get_search_input(page)


def type_search_term(page, search_term, log=print):
    log(f"Typing '{search_term}'...")
    time.sleep(random.uniform(0.2, 0.5))

    # After JS focus, the input is active — type directly via keyboard
    # so we don't need to re-query the element handle.
    try:
        # Clear existing value first
        page.evaluate("""
            () => {
                let el = document.querySelector('input[aria-label="Search input"]');
                if (!el) el = document.querySelector('input[placeholder="Search"][type="text"]');
                if (el) { el.value = ''; el.dispatchEvent(new Event('input', {bubbles: true})); }
            }
        """)
        time.sleep(random.uniform(0.1, 0.3))

        for char in search_term:
            if random.random() < 0.08:
                time.sleep(random.uniform(0.15, 0.35))
            page.keyboard.type(char, delay=random.uniform(80, 160))
            time.sleep(random.uniform(0.02, 0.08))

        log(f"✅ Typed: {search_term}")
        return True

    except Exception as e:
        log(f"❌ Error typing: {e}")
        return False


def click_search_result(page, search_type="hashtag", log=print, max_retries=3):
    if search_type == "hashtag":
        log("Looking for hashtag results...")
        result_selectors = [
            'xpath=//a[contains(@href, "/explore/tags/")]',
            'xpath=//span[contains(text(), "#")]/ancestor::a',
            'xpath=//div[@role="none"]//a[contains(@href, "/explore/")]',
        ]
    else:
        log("Looking for user results...")
        result_selectors = [
            'xpath=//a[contains(@href, "/") and not(contains(@href, "/explore/"))]',
            'xpath=//div[@role="none"]//a',
        ]

    for attempt in range(max_retries):
        wait_time = random.uniform(2.0, 3.0) + (attempt * 1.5)  # longer waits on retries
        log(f"  Waiting {wait_time:.1f}s for results to load (attempt {attempt + 1}/{max_retries})...")
        time.sleep(wait_time)

        for selector in result_selectors:
            try:
                results = page.query_selector_all(selector)
                if results:
                    visible = [r for r in results[:5] if r.is_visible()]
                    if visible:
                        target = visible[0]
                        time.sleep(random.uniform(0.3, 0.6))
                        target.hover()
                        time.sleep(random.uniform(0.3, 0.6))
                        target.click()
                        log("✅ Clicked on search result!")
                        return True
            except:
                continue

        log(f"  No visible results found on attempt {attempt + 1}")

    log("❌ Could not find any search result after all retries")
    return False


PERFORM_SEARCH_TIMEOUT = 45  # seconds — hard cap for the entire search flow


def perform_search(page, search_term, search_type="hashtag", log=print):
    """Execute the full search flow with an overall timeout so it never hangs."""
    deadline = time.time() + PERFORM_SEARCH_TIMEOUT

    def _timed_out():
        return time.time() > deadline

    log(f"🔍 [Search] Navigation directly to '{search_term}' (type={search_type})...")

    # Bypass the UI completely to avoid headless detection / missing DOM issues
    try:
        if search_type == "hashtag":
            clean_term = search_term.lstrip("#")
            target_url = f"https://www.instagram.com/explore/tags/{clean_term}/"
        else:
            clean_term = search_term.lstrip("@")
            target_url = f"https://www.instagram.com/{clean_term}/"

        log(f"  🔗 Navigating to: {target_url}")
        page.goto(target_url, wait_until="domcontentloaded")
        
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass

        if "login" in page.url.lower():
            log(f"  ⚠️ Redirected to login when visiting {target_url}.")
            return False

        log("  ✅ Navigation successful")
        return True

    except Exception as e:
        log(f"❌ [Search] Failed to navigate: {e}")
        return False


def search_instagram(
    cookies: list[dict],
    search_term,
    search_type="hashtag",
    stop_flag=None,
    log_callback=None,
    keep_open=True,
    headless=DEFAULT_HEADLESS,
    browser_type: BrowserType = DEFAULT_BROWSER,
):
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    def should_stop():
        if stop_flag and callable(stop_flag):
            return stop_flag()
        return False

    if headless:
        log("Running in headless mode (browser hidden)")
    else:
        log("Running with visible browser")

    log(f"Launching {browser_type} browser...")

    with sync_playwright() as p:
        browser, context, page = launch_with_cookies(
            p,
            cookies,
            browser_type=browser_type,
            headless=headless,
        )

        log("✅ Browser launched and Instagram loaded")

        time.sleep(random.uniform(1.5, 2.5))

        log("🔍 Starting search process...")
        if not perform_search(page, search_term, search_type, log):
            log("❌ Search failed")
            context.close()
            return

        time.sleep(random.uniform(2.0, 3.0))
        log(f"🎉 Search completed for: {search_term}")

        if keep_open:
            log("📌 Browser staying open. Click 'Stop' to close.")
            while not should_stop():
                try:
                    page.wait_for_timeout(1000)
                except:
                    break

        try:
            context.close()
            browser.close()
        except:
            pass