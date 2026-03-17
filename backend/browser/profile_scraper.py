"""
Profile Scraper — Playwright-based Instagram profile data extractor.

Given a discovery plan (hashtags, search queries, seed accounts),
visits Instagram profiles and extracts structured data.

Extends the EXISTING scraper loop with inline AI qualification:
  for url in discovered_profiles:
      profile_data = scrape_profile(url)
      score = qualify(profile_data)
      if score.is_target:
          store lead

Reuses shared functions from browser.scraper and browser.session
to avoid code duplication.
"""

import asyncio
import random
import re
from typing import Callable

from playwright.async_api import Page

from browser.launcher import BrowserType, DEFAULT_BROWSER
from browser.session import CookieBrowser
from browser.scraper import (
    human_delay,
    maybe_take_break,
    is_valid_username,
    USERNAME_PATTERN,
    COMMENT_SELECTORS,
    VIEW_MORE_SELECTORS,
    MAX_COMMENT_SCROLLS,
    extract_post_owner,
    collect_post_urls_from_hashtag,
)

# ── Limits (token optimization) ─────────────────────────────────────

MAX_BIO_CHARS = 300
MAX_CAPTIONS = 5
MAX_CAPTION_CHARS = 300
MAX_COMMENTS = 10
MAX_COMMENT_CHARS = 200
MAX_PROFILES_PER_HASHTAG = 15
MAX_PROFILES_PER_SEARCH = 10


# ── Data extraction helpers ─────────────────────────────────────────


async def _extract_profile_data(page: Page) -> dict | None:
    """
    Extract structured profile data from a profile page.

    Returns dict with: username, full_name, bio, followers_count,
    following_count, profile_image_url, recent_captions, recent_comments,
    detected_language.
    """
    data: dict = {}

    try:
        # Wait for profile content
        try:
            await page.wait_for_selector("header", timeout=8000)
        except Exception:
            pass

        await human_delay("read_content")

        # ── Username ────────────────────────────────────────────────
        # From URL
        url_path = page.url.rstrip("/").split("/")[-1]
        if re.match(r"^[a-zA-Z0-9_.]{1,30}$", url_path):
            data["username"] = url_path
        else:
            # Fallback: meta tag
            try:
                og_url = await page.get_attribute('meta[property="og:url"]', "content")
                if og_url:
                    match = re.search(r"instagram\.com/([a-zA-Z0-9_.]+)", og_url)
                    if match:
                        data["username"] = match.group(1)
            except Exception:
                pass

        if not data.get("username"):
            return None

        # ── Full name ───────────────────────────────────────────────
        try:
            # Try og:title first
            og_title = await page.get_attribute('meta[property="og:title"]', "content")
            if og_title and "(" in og_title:
                data["full_name"] = og_title.split("(")[0].strip()
            elif og_title:
                data["full_name"] = og_title.split("•")[0].strip()
            else:
                data["full_name"] = ""
        except Exception:
            data["full_name"] = ""

        # ── Bio ─────────────────────────────────────────────────────
        try:
            og_desc = await page.get_attribute('meta[property="og:description"]', "content")
            if og_desc:
                # OG description often has "X Followers, Y Following, Z Posts - BIO"
                parts = og_desc.split(" - ", 1)
                bio_text = parts[1] if len(parts) > 1 else ""
                data["bio"] = bio_text[:MAX_BIO_CHARS].strip()
            else:
                data["bio"] = ""
        except Exception:
            data["bio"] = ""

        # ── Follower / following counts ─────────────────────────────
        try:
            og_desc = await page.get_attribute('meta[property="og:description"]', "content")
            if og_desc:
                nums = re.findall(r"([\d,.KkMm]+)\s+(Follower|Following|Post)", og_desc)
                for val, label in nums:
                    parsed = _parse_count(val)
                    if "Follower" in label:
                        data["followers_count"] = parsed
                    elif "Following" in label:
                        data["following_count"] = parsed
        except Exception:
            pass
        data.setdefault("followers_count", 0)
        data.setdefault("following_count", 0)

        # ── Profile image URL ───────────────────────────────────────
        try:
            og_img = await page.get_attribute('meta[property="og:image"]', "content")
            data["profile_image_url"] = og_img or ""
        except Exception:
            data["profile_image_url"] = ""

        # ── Recent captions ─────────────────────────────────────────
        data["recent_captions"] = await _extract_recent_captions(page)

        # ── Recent comments (sample) ────────────────────────────────
        data["recent_comments"] = await _extract_recent_comments(page)

        # ── Detected language ───────────────────────────────────────
        all_text = " ".join([data.get("bio", ""), data.get("full_name", "")])
        all_text += " ".join(data.get("recent_captions", []))
        data["detected_language"] = _detect_language(all_text)

        return data

    except Exception as e:
        print(f"    Profile extraction error: {e}")
        return None


async def _extract_recent_captions(page: Page) -> list[str]:
    """Extract captions from the last few visible posts."""
    captions: list[str] = []
    try:
        # Try to get captions from post links or alt text
        img_elements = await page.query_selector_all("article img[alt]")
        for img in img_elements[:MAX_CAPTIONS]:
            alt = await img.get_attribute("alt")
            if alt and len(alt) > 10:
                captions.append(alt[:MAX_CAPTION_CHARS])

        # Fallback: og description sometimes has caption info
        if not captions:
            meta_els = await page.query_selector_all('meta[property="og:description"]')
            for el in meta_els[:1]:
                content = await el.get_attribute("content")
                if content and len(content) > 30:
                    captions.append(content[:MAX_CAPTION_CHARS])
    except Exception:
        pass

    return captions[:MAX_CAPTIONS]


async def _extract_recent_comments(page: Page) -> list[str]:
    """Sample comments from visible posts, reusing existing scraper selectors."""
    comments: list[str] = []
    try:
        # Reuse COMMENT_SELECTORS from existing scraper.py
        for selector in COMMENT_SELECTORS:
            if len(comments) >= MAX_COMMENTS:
                break
            els = await page.query_selector_all(selector)
            for el in els:
                if len(comments) >= MAX_COMMENTS:
                    break
                try:
                    text = await el.inner_text()
                    if text and len(text.strip()) > 3:
                        comments.append(text.strip()[:MAX_COMMENT_CHARS])
                except Exception:
                    continue

        # Fallback: generic span scan
        if not comments:
            comment_els = await page.query_selector_all(
                'ul li span:not([class*="username"]):not([class*="time"])'
            )
            for el in comment_els[:MAX_COMMENTS]:
                text = await el.inner_text()
                if text and len(text.strip()) > 3:
                    comments.append(text.strip()[:MAX_COMMENT_CHARS])
    except Exception:
        pass
    return comments[:MAX_COMMENTS]


def _parse_count(val: str) -> int:
    """Parse follower/following count strings like '1,234' or '12.3K'."""
    val = val.strip().replace(",", "")
    multiplier = 1
    if val.lower().endswith("k"):
        multiplier = 1_000
        val = val[:-1]
    elif val.lower().endswith("m"):
        multiplier = 1_000_000
        val = val[:-1]
    try:
        return int(float(val) * multiplier)
    except ValueError:
        return 0


def _detect_language(text: str) -> str:
    """Simple heuristic language detection."""
    if not text:
        return "unknown"
    # Japanese character ranges
    jp_chars = len(re.findall(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", text))
    kr_chars = len(re.findall(r"[\uAC00-\uD7AF]", text))
    total = len(text)
    if total == 0:
        return "unknown"
    if jp_chars / total > 0.1:
        return "ja"
    if kr_chars / total > 0.1:
        return "ko"
    return "en"


# ── Discovery flow ──────────────────────────────────────────────────


class ProfileScraper:
    """
    Playwright-based profile discovery and data extraction.

    Extends the existing scraper loop with inline qualification:
      for url in discovered_profiles:
          profile_data = scrape profile
          score = qualify(profile_data)   # Qualification Brain
          if score.is_target:
              store lead

    Preserves all existing anti-bot delays and randomization.
    """

    def __init__(
        self,
        cookies: list[dict],
        max_profiles: int = 50,
        headless: bool = False,
        browser_type: BrowserType = DEFAULT_BROWSER,
        log_fn: Callable | None = None,
        stop_fn: Callable | None = None,
        qualify_fn: Callable | None = None,
    ):
        self.cookies = cookies
        self.max_profiles = max_profiles
        self.headless = headless
        self.browser_type = browser_type
        self._log = log_fn or (lambda msg: print(f"  [ProfileScraper] {msg}"))
        self._stop = stop_fn or (lambda: False)
        self._qualify = qualify_fn  # inline qualifier: profile_dict -> scored_dict | None
        self._collected: list[dict] = []      # all scraped profiles (raw)
        self._leads: list[dict] = []          # qualified leads only
        self._seen_usernames: set[str] = set()

    async def run(self, discovery_plan: dict) -> dict:
        """
        Execute the full discovery + scrape + inline-qualify flow.

        Returns dict with profiles, leads, total_scanned, total_qualified.
        """
        priority = discovery_plan.get("priority_order", [])
        hashtags = discovery_plan.get("hashtags", [])
        search_queries = discovery_plan.get("search_queries", [])
        seed_accounts = discovery_plan.get("seed_accounts", [])

        # Store extra keyword lists so _build_task_queue can expand them
        self._plan_extra = {
            "bio_keywords": discovery_plan.get("bio_keywords", []),
            "japanese_keywords": discovery_plan.get("japanese_keywords", []),
            "caption_keywords": discovery_plan.get("caption_keywords", []),
        }

        tasks = self._build_task_queue(priority, hashtags, search_queries, seed_accounts)
        self._log(f"Discovery plan: {len(tasks)} tasks, max {self.max_profiles} profiles")

        async with CookieBrowser(
            self.cookies,
            browser_type=self.browser_type,
            headless=self.headless,
        ) as cb:
            page = cb.page
            for task_type, value in tasks:
                if self._stop() or len(self._collected) >= self.max_profiles:
                    break

                if task_type == "hashtag":
                    await self._scrape_hashtag(page, value)
                elif task_type == "search":
                    await self._scrape_search(page, value)
                elif task_type == "seed_account":
                    await self._scrape_seed_account(page, value)

                await asyncio.sleep(random.uniform(3, 8))

        self._log(f"Scraping complete: {len(self._collected)} profiles scraped, {len(self._leads)} qualified leads")
        return {
            "profiles": self._collected,
            "leads": sorted(self._leads, key=lambda x: -(x.get("total_score") or 0)),
            "total_scanned": len(self._collected),
            "total_qualified": len(self._leads),
        }

    def _build_task_queue(
        self,
        priority: list[str],
        hashtags: list[str],
        search_queries: list[str],
        seed_accounts: list[str],
    ) -> list[tuple[str, str]]:
        """
        Build an ordered list of (task_type, value) tuples.

        priority_order from the Discovery Brain contains **category names**
        (e.g. "search_queries", "hashtags", "seed_accounts") that define
        the order in which to process each group — NOT literal search terms.
        """
        tasks: list[tuple[str, str]] = []
        used: set[str] = set()

        # Map category names → (task_type, items list)
        category_map: dict[str, tuple[str, list[str]]] = {
            "hashtags":           ("hashtag",      hashtags),
            "search_queries":     ("search",       search_queries),
            "seed_accounts":      ("seed_account", seed_accounts),
            # Extra keyword categories from Discovery Brain → treat as searches
            "bio_keywords":       ("search",       self._plan_extra.get("bio_keywords", [])),
            "japanese_keywords":  ("search",       self._plan_extra.get("japanese_keywords", [])),
            "caption_keywords":   ("search",       self._plan_extra.get("caption_keywords", [])),
        }

        # Follow priority_order: expand each category into its items
        for category in priority:
            entry = category_map.get(category)
            if entry:
                task_type, items = entry
                for item in items:
                    clean = item.strip().lstrip("#@")
                    if clean and clean not in used:
                        used.add(clean)
                        tasks.append((task_type, clean))
            else:
                # Unknown category — treat as a literal search/hashtag/seed
                clean = category.strip().lstrip("#@")
                if clean and clean not in used:
                    used.add(clean)
                    if category.startswith("#") or clean in [h.strip().lstrip("#") for h in hashtags]:
                        tasks.append(("hashtag", clean))
                    elif category.startswith("@") or clean in [a.strip().lstrip("@") for a in seed_accounts]:
                        tasks.append(("seed_account", clean))
                    else:
                        tasks.append(("search", clean))

        # Append any items not yet covered (in case priority_order was incomplete)
        for h in hashtags:
            h_clean = h.strip().lstrip("#")
            if h_clean not in used:
                used.add(h_clean)
                tasks.append(("hashtag", h_clean))

        for q in search_queries:
            if q not in used:
                used.add(q)
                tasks.append(("search", q))

        for a in seed_accounts:
            a_clean = a.strip().lstrip("@")
            if a_clean not in used:
                used.add(a_clean)
                tasks.append(("seed_account", a_clean))

        return tasks

    async def _scrape_hashtag(self, page: Page, hashtag: str) -> None:
        """Visit a hashtag page, collect and visit profiles."""
        if len(self._collected) >= self.max_profiles:
            return

        self._log(f"Exploring hashtag #{hashtag}")

        try:
            # Reuse shared function: navigate, scroll, collect post URLs
            post_urls = await collect_post_urls_from_hashtag(
                page, hashtag, MAX_PROFILES_PER_HASHTAG
            )
            if not post_urls:
                self._log(f"  No posts found for #{hashtag}")
                return

            self._log(f"  Found {len(post_urls)} posts under #{hashtag}")

            # Visit each post to extract the owner username
            usernames: list[str] = []
            for post_url in post_urls:
                if self._stop() or len(self._collected) >= self.max_profiles:
                    break
                try:
                    await page.goto(post_url, wait_until="domcontentloaded")
                    await human_delay("read_content")
                    owner = await extract_post_owner(page)
                    if owner and owner not in self._seen_usernames:
                        usernames.append(owner)
                    await maybe_take_break()
                except Exception as e:
                    self._log(f"  Post visit error: {e}")
                    continue

            await self._visit_profiles(page, usernames, source=f"hashtag:#{hashtag}")

        except Exception as e:
            self._log(f"  Hashtag scrape error for #{hashtag}: {e}")

    async def _scrape_search(self, page: Page, query: str) -> None:
        """Use Instagram search to find profiles matching a query."""
        if len(self._collected) >= self.max_profiles:
            return

        self._log(f"Searching for '{query}'")

        try:
            await page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
            await human_delay("page_load")

            # Click the search icon / input
            search_btn = await page.query_selector(
                'a[href="/explore/"] , svg[aria-label="Search"] , '
                'a[role="link"] svg[aria-label="Search"]'
            )
            if search_btn:
                await search_btn.click()
                await asyncio.sleep(random.uniform(0.8, 1.5))

            # Type into search
            search_input = await page.query_selector(
                'input[aria-label="Search input"], input[placeholder="Search"]'
            )
            if search_input:
                await search_input.fill("")
                await asyncio.sleep(0.3)
                for char in query:
                    await search_input.type(char, delay=random.randint(50, 150))
                await asyncio.sleep(random.uniform(1.5, 3.0))

                # Collect suggested usernames from results
                result_links = await page.query_selector_all(
                    'a[href^="/"][role="link"], div[role="none"] a[href^="/"]'
                )
                usernames: list[str] = []
                for link in result_links[:MAX_PROFILES_PER_SEARCH]:
                    href = await link.get_attribute("href")
                    if href:
                        match = USERNAME_PATTERN.match(href)
                        if match and is_valid_username(match.group(1)):
                            usernames.append(match.group(1))

                self._log(f"  Search returned {len(usernames)} profiles")
                await self._visit_profiles(page, usernames, source=f"search:{query}")
            else:
                self._log("  Could not find search input")

        except Exception as e:
            self._log(f"  Search error for '{query}': {e}")

    async def _scrape_seed_account(self, page: Page, account: str) -> None:
        """Visit a seed account's followers to discover profiles."""
        if len(self._collected) >= self.max_profiles:
            return

        self._log(f"Visiting seed account @{account}")

        try:
            url = f"https://www.instagram.com/{account}/"
            await page.goto(url, wait_until="domcontentloaded")
            await human_delay("page_load")

            if "login" in page.url.lower():
                self._log("Redirected to login — skipping")
                return

            # Extract the seed account's profile first
            profile_data = await _extract_profile_data(page)
            if profile_data and profile_data["username"] not in self._seen_usernames:
                self._seen_usernames.add(profile_data["username"])
                profile_data["discovery_source"] = f"seed_account:@{account}"
                self._collected.append(profile_data)

                # Inline qualification for seed account itself
                if self._qualify:
                    scored = self._qualify(profile_data)
                    if scored and scored.get("is_target"):
                        self._leads.append(scored)

            # Try to open followers dialog for more profiles
            try:
                followers_link = await page.query_selector(
                    'a[href*="/followers/"], a[href*="/followers"]'
                )
                if followers_link:
                    await followers_link.click()
                    await asyncio.sleep(random.uniform(2, 4))

                    # Scroll the followers dialog
                    for _ in range(random.randint(2, 5)):
                        dialog = await page.query_selector(
                            'div[role="dialog"], div[class*="dialog"]'
                        )
                        if dialog:
                            await dialog.evaluate(
                                "el => el.scrollTop = el.scrollHeight"
                            )
                        await asyncio.sleep(random.uniform(1, 2.5))

                    # Collect follower usernames
                    follower_links = await page.query_selector_all(
                        'div[role="dialog"] a[href^="/"]'
                    )
                    usernames: list[str] = []
                    for link in follower_links:
                        if len(usernames) >= MAX_PROFILES_PER_SEARCH:
                            break
                        href = await link.get_attribute("href")
                        if href:
                            match = USERNAME_PATTERN.match(href)
                            if match and is_valid_username(match.group(1)):
                                usernames.append(match.group(1))

                    self._log(f"  Found {len(usernames)} followers from @{account}")

                    # Close dialog
                    close_btn = await page.query_selector(
                        'div[role="dialog"] button svg[aria-label="Close"]'
                    )
                    if close_btn:
                        await close_btn.click()
                        await asyncio.sleep(0.5)

                    await self._visit_profiles(
                        page, usernames, source=f"followers:@{account}"
                    )

            except Exception as e:
                self._log(f"  Followers extraction error: {e}")

        except Exception as e:
            self._log(f"  Seed account error for @{account}: {e}")

    async def _visit_profiles(
        self, page: Page, usernames: list[str], source: str
    ) -> None:
        """
        Visit profiles and extract data. If a qualify_fn is set,
        run inline qualification per the spec:
          profile_data = scrape profile
          score = qualify(profile_data)
          if score.is_target: store lead
        """
        for username in usernames:
            if self._stop() or len(self._collected) >= self.max_profiles:
                break
            if username in self._seen_usernames:
                continue

            self._seen_usernames.add(username)

            try:
                url = f"https://www.instagram.com/{username}/"
                await page.goto(url, wait_until="domcontentloaded")
                await human_delay("page_load")

                profile_data = await _extract_profile_data(page)
                if profile_data:
                    profile_data["discovery_source"] = source
                    self._collected.append(profile_data)

                    # ── Inline qualification (spec: scrape → qualify → store) ──
                    if self._qualify:
                        scored = self._qualify(profile_data)
                        if scored and scored.get("is_target"):
                            self._leads.append(scored)
                            self._log(
                                f"  ✓ @{username} QUALIFIED "
                                f"(score={scored.get('total_score', 0)}, "
                                f"confidence={scored.get('confidence', '?')}) "
                                f"[{len(self._leads)} leads / {len(self._collected)} scanned]"
                            )
                        else:
                            self._log(
                                f"  ✗ @{username} not qualified "
                                f"(score={scored.get('total_score', 0) if scored else 0}) "
                                f"[{len(self._collected)}/{self.max_profiles}]"
                            )
                    else:
                        self._log(
                            f"  Scraped @{username} "
                            f"({len(self._collected)}/{self.max_profiles})"
                        )

                # Human-like delay between profiles
                await asyncio.sleep(random.uniform(2, 5))
                await maybe_take_break()

            except Exception as e:
                self._log(f"  Profile visit error @{username}: {e}")
                continue


async def scrape_profiles(
    discovery_plan: dict,
    cookies: list[dict],
    max_profiles: int = 50,
    headless: bool = False,
    browser_type: str = "chromium",
    log_fn: Callable | None = None,
    stop_fn: Callable | None = None,
    qualify_fn: Callable | None = None,
) -> dict:
    """
    Entry point: discover, scrape, and optionally qualify Instagram profiles.

    When qualify_fn is provided, implements the inline qualification loop:
      for profile in discovered:
          data = scrape(profile)
          score = qualify_fn(data)
          if score.is_target: store as lead

    Args:
        discovery_plan: output from DiscoveryBrain.generate_plan()
        cookies: Instagram session cookies
        max_profiles: maximum profiles to scrape
        headless: run browser in headless mode
        browser_type: browser engine to use
        log_fn: optional logging callback
        stop_fn: optional stop-flag callable
        qualify_fn: optional inline qualifier (profile_dict -> scored_dict)

    Returns:
        {
            "profiles": [all scraped profiles],
            "leads": [qualified leads sorted by score],
            "total_scanned": int,
            "total_qualified": int,
        }
    """
    scraper = ProfileScraper(
        cookies=cookies,
        max_profiles=max_profiles,
        headless=headless,
        browser_type=browser_type,
        log_fn=log_fn,
        stop_fn=stop_fn,
        qualify_fn=qualify_fn,
    )
    return await scraper.run(discovery_plan)
