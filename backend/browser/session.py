import asyncio
from playwright.async_api import async_playwright
from browser.launcher import (
    launch_persistent_async,
    launch_browser_async,
    get_page_async,
    dismiss_notification_popup_async,
    BrowserType,
    DEFAULT_BROWSER,
    DEFAULT_HEADLESS,
)


async def open_login_and_export_cookies(
    timeout: int = 120,
    browser_type: BrowserType = DEFAULT_BROWSER,
) -> tuple[list[dict], str | None]:
    """
    Open a completely fresh headful browser for Instagram login.

    Uses a non-persistent context (no leftover cookies/cache) to avoid
    the ``/#`` stale-session glitch.  Handles all three login flows:
      1. Direct IG username + password
      2. IG login with 2FA verification
      3. Login via Facebook (+ optional 2FA on FB side)

    Timer is paused while the user is on 2FA / challenge / Facebook pages
    so they have unlimited time to complete verification.
    """
    try:
        async with async_playwright() as p:
            # ── Launch a NON-persistent browser for a truly fresh session ──
            # This avoids any leftover cookies, cache, or session data that
            # caused the /#-then-profile glitch with persistent contexts.
            browser = await launch_browser_async(
                p,
                browser_type=browser_type,
                headless=False,          # always visible for manual login
                slow_mo=500,
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                locale="en-US",
                permissions=[],
            )

            # Ensure absolutely no leftover state
            await context.clear_cookies()

            page = await context.new_page()
            await page.goto("https://www.instagram.com/accounts/login/")

            # ── Track new pages/popups (Facebook login may open one) ──
            all_pages: list = [page]

            def _on_new_page(new_page):
                all_pages.append(new_page)

            context.on("page", _on_new_page)

            # ── Poll for successful login ────────────────────────────
            logged_in = False
            elapsed = 0
            poll_interval = 1

            # IG pages that are part of the login flow (not yet logged in)
            _login_flow_paths = (
                "/accounts/login",
                "/accounts/emailsignup",
                "/challenge",
                "/two_factor",
                "/login",
                "/accounts/onetap",
            )

            # Pages where the timer should be paused (user needs time)
            _pause_timer_paths = (
                "/two_factor",
                "/challenge",
            )

            # Track whether we already redirected from a stale /#
            _did_redirect_from_hash = False

            while True:
                # ── Primary: check for ds_user_id cookie ──
                # This works for ALL login methods once authentication succeeds.
                all_cookies = await context.cookies([
                    "https://www.instagram.com",
                    "https://instagram.com",
                    "https://i.instagram.com",
                ])
                has_ds_user_id = any(
                    c.get("name") in ("ds_user_id", "ds_user")
                    for c in all_cookies
                )
                if has_ds_user_id:
                    await asyncio.sleep(2)
                    logged_in = True
                    break

                # ── Get the active page URL ──
                # After Facebook login/popup, the active page may have changed.
                active_page = all_pages[-1]
                try:
                    current_url = active_page.url
                except Exception:
                    current_url = page.url

                # Determine if we should pause the timer
                on_facebook = "facebook.com" in current_url
                on_paused_page = (
                    any(path in current_url for path in _pause_timer_paths)
                    or on_facebook
                )

                # ── Detect stale-session /#  and redirect ──
                # Instagram shows /#  when it detects an expired or
                # incomplete session.  Navigate back to a clean login page.
                if "instagram.com" in current_url and not on_facebook:
                    from urllib.parse import urlparse
                    _parsed = urlparse(current_url)
                    _is_hash_page = (
                        _parsed.path in ("/", "")
                        and (_parsed.fragment != "" or current_url.endswith("/#"))
                    )
                    if _is_hash_page and not _did_redirect_from_hash:
                        # Give the browser 5 seconds to finish setting cookies 
                        # before we assume the session is actually "stale."
                        await asyncio.sleep(5) 
                        
                        # Re-check cookies one last time before forcing a redirect
                        temp_cookies = await context.cookies(["https://www.instagram.com"])
                        has_session = any(c.get("name") in ("ds_user_id", "ds_user") for c in temp_cookies)
                        
                        if not has_session:
                            _did_redirect_from_hash = True
                            try:
                                await active_page.goto(
                                    "https://www.instagram.com/accounts/login/",
                                    wait_until="domcontentloaded",
                                    timeout=15000,
                                )
                            except Exception:
                                pass
                            continue
                        await asyncio.sleep(poll_interval)
                        continue  # re-enter the loop — do NOT treat as logged-in

                # ── Secondary: URL-based detection ──
                # Only when we're on instagram.com and NOT on a login-flow page.
                if "instagram.com" in current_url and not on_facebook:
                    on_login_page = any(
                        path in current_url for path in _login_flow_paths
                    )
                    if not on_login_page:
                        # We reached the IG home/feed — wait a bit for
                        # cookies to propagate, then verify.
                        await asyncio.sleep(4)
                        recheck = await context.cookies([
                            "https://www.instagram.com",
                            "https://instagram.com",
                            "https://i.instagram.com",
                        ])
                        if any(
                            c.get("name") in ("ds_user_id", "ds_user")
                            for c in recheck
                        ):
                            logged_in = True
                            break
                        # No cookie yet — do NOT assume success.
                        # Keep polling; the session may still be establishing
                        # or URL might be a false-positive (e.g. '/# ').
                        pass

                # ── Also check if ANY page (including popups) landed on IG feed ──
                # This catches Facebook login popups that redirect back to IG.
                for p_ref in all_pages:
                    try:
                        p_url = p_ref.url
                        if (
                            "instagram.com" in p_url
                            and not any(path in p_url for path in _login_flow_paths)
                            and "facebook.com" not in p_url
                            and "/#" not in p_url  # skip stale-session hash
                            and p_url != current_url  # don't recheck same page
                        ):
                            await asyncio.sleep(3)
                            recheck = await context.cookies([
                                "https://www.instagram.com",
                                "https://instagram.com",
                                "https://i.instagram.com",
                            ])
                            if any(
                                c.get("name") in ("ds_user_id", "ds_user")
                                for c in recheck
                            ):
                                logged_in = True
                                break
                    except Exception:
                        continue
                if logged_in:
                    break

                await asyncio.sleep(poll_interval)

                # Only count elapsed time when NOT on a paused page
                if not on_paused_page:
                    elapsed += poll_interval
                    if elapsed >= timeout:
                        break

            # ── Export all cookies from all domains ───────────────────
            cookies = await context.cookies([
                "https://www.instagram.com",
                "https://instagram.com",
                "https://i.instagram.com",
                "https://www.facebook.com",
                "https://web.facebook.com",
            ])

            # ── Extract Instagram username ───────────────────────────
            instagram_username = None
            if logged_in:
                # Use whichever page is on instagram.com for extraction
                extract_page = page
                for p_ref in all_pages:
                    try:
                        if "instagram.com" in p_ref.url:
                            extract_page = p_ref
                            break
                    except Exception:
                        continue
                instagram_username = await _extract_username_from_browser(
                    context, extract_page, cookies
                )

            await context.close()
            await browser.close()
    except Exception as exc:
        # Re-raise but make sure resources are cleaned up
        raise

    return cookies, instagram_username


async def _extract_username_from_browser(
    context,
    page,
    cookies: list[dict],
    max_retries: int = 3,
) -> str | None:
    instagram_username = None

    # ── Method 1: Navigate to IG home and call the edit-profile API ──
    # This is the most reliable method and returns the actual username.
    for attempt in range(max_retries):
        try:
            # Make sure we're on an instagram.com page first
            current = page.url
            if "instagram.com" not in current or "/accounts/login" in current:
                await page.goto(
                    "https://www.instagram.com/",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
            else:
                # Already on IG, but reload to ensure fresh context
                if attempt > 0:
                    await page.goto(
                        "https://www.instagram.com/",
                        wait_until="domcontentloaded",
                        timeout=15000,
                    )

            # Wait for network to settle (longer on first attempt for
            # 2FA/FB flows where session may still be establishing)
            settle_time = 8 if attempt == 0 else 4
            await asyncio.sleep(settle_time)

            # Try the web form data API (returns actual username)
            instagram_username = await page.evaluate("""
                async () => {
                    try {
                        const r = await fetch('/api/v1/accounts/edit/web_form_data/', {
                            headers: {
                                'X-IG-App-ID': '936619743392459',
                                'X-Requested-With': 'XMLHttpRequest',
                            },
                            credentials: 'include',
                        });
                        if (r.ok) {
                            const d = await r.json();
                            return d?.form_data?.username || null;
                        }
                    } catch(e) {}
                    return null;
                }
            """)

            if instagram_username:
                return instagram_username

        except Exception:
            pass

        # Short delay before retry
        if attempt < max_retries - 1:
            await asyncio.sleep(2)

    # ── Method 2: Try the web profile info API ──
    try:
        instagram_username = await page.evaluate("""
            async () => {
                try {
                    const r = await fetch('/api/v1/web/get_ruling_for_content/?content_type=profile', {
                        headers: {
                            'X-IG-App-ID': '936619743392459',
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                        credentials: 'include',
                    });
                    if (r.ok) {
                        const d = await r.json();
                        return d?.payload?.username || null;
                    }
                } catch(e) {}
                return null;
            }
        """)
        if instagram_username:
            return instagram_username
    except Exception:
        pass

    # ── Method 3: Parse username from profile link on the page ──
    try:
        # The IG web app renders the user's profile link in the sidebar/nav
        instagram_username = await page.evaluate("""
            () => {
                // Look for profile link in navigation
                const links = document.querySelectorAll('a[href]');
                for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    // Profile links look like: /<username>/  (single segment)
                    const m = href.match(/^\\/([a-zA-Z0-9._]{1,30})\\/$/);
                    if (m) {
                        const name = m[1];
                        // Skip known IG pages
                        const skip = ['explore', 'reels', 'direct', 'accounts',
                                      'stories', 'p', 'reel', 'tv', 'about',
                                      'nametag', 'directory', 'lite', 'legal',
                                      'terms', 'privacy', 'safety', 'support'];
                        if (!skip.includes(name.toLowerCase())) {
                            // Check if it has profile-like properties
                            const img = a.querySelector('img');
                            const span = a.querySelector('span');
                            if (img || (span && span.textContent.trim() === name)) {
                                return name;
                            }
                        }
                    }
                }
                return null;
            }
        """)
        if instagram_username:
            return instagram_username
    except Exception:
        pass

    # ── Method 4: Fallback — ds_user_id cookie (numeric user ID) ──
    for c in cookies:
        if c.get("name") == "ds_user_id":
            val = c.get("value")
            if val and isinstance(val, str) and val.strip():
                return val.strip()

    return None


class CookieBrowser:
    def __init__(
        self,
        cookies: list[dict],
        browser_type: BrowserType = DEFAULT_BROWSER,
        headless: bool = DEFAULT_HEADLESS,
        goto_url: str = "https://www.instagram.com/",
    ):
        self.cookies = cookies
        self.browser_type = browser_type
        self.headless = headless
        self.goto_url = goto_url
        self._pw = None
        self._browser = None
        self.context = None
        self.page = None

    async def __aenter__(self):
        from playwright.async_api import async_playwright as _ap

        self._pw = await _ap().start()
        self._browser = await launch_browser_async(
            self._pw,
            browser_type=self.browser_type,
            headless=self.headless,
        )
        self.context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
        )
        await self.context.add_cookies(self.cookies)
        self.page = await self.context.new_page()
        await self.page.goto(self.goto_url, wait_until="domcontentloaded")
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        await dismiss_notification_popup_async(self.page)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            await self.context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        return False


async def open_browser_with_cookies(
    cookies: list[dict],
    browser_type: BrowserType = DEFAULT_BROWSER,
    headless: bool = DEFAULT_HEADLESS,
    goto_url: str = "https://www.instagram.com/",
):
    cb = CookieBrowser(cookies, browser_type, headless, goto_url)
    await cb.__aenter__()
    return cb.context, cb.page
