import os
import csv
import random
import re
import time
from collections import Counter

from agents.ollama_brain import analyze_accounts
from output.csv_export import export_to_csv
from config.targets import get_target_config
from browser.search_engine import perform_search

# Reuse all shared constants and helpers from scraper.py — single source of truth
from browser.scraper import (
    USERNAME_PATTERN,
    MAX_ACCOUNTS_PER_SESSION,
    MAX_HASHTAGS_PER_SESSION,
    MAX_POSTS_PER_HASHTAG,
    MAX_COMMENTERS_PER_POST,
    MAX_COMMENT_SCROLLS,
    EXCLUDED_PATHS,
    VIEW_MORE_SELECTORS,
    COMMENT_SELECTORS,
    is_valid_username,
    get_delay,
)


# =====================================================================
#  Thin sync wrappers — only contain the sync-specific sleep call,
#  all config / constants come from scraper.py
# =====================================================================

def _human_delay_sync(action: str = "default"):
    """Sync version of human_delay using the shared delay map."""
    min_sec, max_sec = get_delay(action)
    time.sleep(random.uniform(min_sec, max_sec))


def _maybe_take_break_sync(log=print):
    """Sync version of maybe_take_break."""
    if random.random() < 0.2:
        log("      [Taking a short break...]")
        time.sleep(random.uniform(8, 15))


# =====================================================================
#  Sync playwright helpers — same logic as InstagramScraper methods
#  but using sync API.  Pure-logic decisions (username validation,
#  selectors, constants) are imported from scraper.py.
# =====================================================================

def _extract_post_owner(page, logged_in_user: str = None) -> str | None:
    """Extract the post owner from the current page (sync)."""
    # Strategy 1: Meta tag
    try:
        meta = page.get_attribute('meta[property="og:description"]', 'content')
        if meta and '@' in meta:
            match = re.search(r'@([a-zA-Z0-9_.]+)', meta)
            if match and is_valid_username(match.group(1), logged_in_user):
                return match.group(1)
    except:
        pass

    # Strategy 2: Page title
    try:
        title = page.title()
        if title and ' on Instagram' in title:
            username = title.split(' on Instagram')[0].strip()
            if re.match(r'^[a-zA-Z0-9_.]+$', username) and is_valid_username(username, logged_in_user):
                return username
    except:
        pass

    # Strategy 3: Link scanning
    try:
        all_links = page.query_selector_all('a[href^="/"]')
        candidates = []
        for link in all_links:
            href = link.get_attribute("href")
            if not href or href in EXCLUDED_PATHS:
                continue
            if any(href.startswith(ex) for ex in ['/explore/', '/p/', '/reel/', '/tags/']):
                continue
            match = USERNAME_PATTERN.match(href)
            if match:
                uname = match.group(1)
                if is_valid_username(uname, logged_in_user):
                    candidates.append(uname)
        if candidates:
            return Counter(candidates).most_common(1)[0][0]
    except:
        pass

    return None


def _scroll_comments(page, log=print):
    """Click 'View more comments' / scroll the comment area (sync)."""
    try:
        for scroll_num in range(MAX_COMMENT_SCROLLS):
            clicked = False
            for selector in VIEW_MORE_SELECTORS:
                try:
                    btn = page.query_selector(selector)
                    if btn:
                        btn.click()
                        clicked = True
                        log(f"        Loaded more comments ({scroll_num + 1}/{MAX_COMMENT_SCROLLS})")
                        _human_delay_sync("comment_scroll")
                        break
                except:
                    continue

            if not clicked:
                try:
                    comment_section = page.query_selector('ul[class*="comment"], div[class*="comment"]')
                    if comment_section:
                        comment_section.scroll_into_view_if_needed()
                        page.keyboard.press("PageDown")
                        _human_delay_sync("comment_scroll")
                except:
                    pass

            if random.random() < 0.3:
                break

            _maybe_take_break_sync(log)
    except:
        pass


def _extract_commenters(page, post_owner: str, max_commenters: int = MAX_COMMENTERS_PER_POST, log=print) -> list[str]:
    """Extract commenter usernames from the current post page (sync)."""
    commenters = []
    seen = set()

    _scroll_comments(page, log)

    for selector in COMMENT_SELECTORS:
        if len(commenters) >= max_commenters:
            break
        try:
            links = page.query_selector_all(selector)
            for link in links:
                if len(commenters) >= max_commenters:
                    break
                href = link.get_attribute("href")
                if not href:
                    continue
                match = USERNAME_PATTERN.match(href)
                if match:
                    uname = match.group(1)
                    if is_valid_username(uname) and uname != post_owner and uname not in seen:
                        seen.add(uname)
                        commenters.append(uname)
        except:
            continue

    # fallback: scan all article links
    if len(commenters) < 3:
        try:
            all_links = page.query_selector_all('article a[href^="/"]')
            for link in all_links:
                if len(commenters) >= max_commenters:
                    break
                href = link.get_attribute("href")
                if not href:
                    continue
                match = USERNAME_PATTERN.match(href)
                if match:
                    uname = match.group(1)
                    if is_valid_username(uname) and uname != post_owner and uname not in seen:
                        seen.add(uname)
                        commenters.append(uname)
        except:
            pass

    return commenters[:max_commenters]


# =====================================================================
#  Core sync scrape function — operates on an EXISTING page
# =====================================================================

def scrape_hashtags_sync(page, target_customer: str,
                         max_commenters: int = MAX_COMMENTERS_PER_POST,
                         log=print,
                         visited_posts: set = None) -> list[dict]:
    """
    Navigate to hashtag pages and scrape post owners + commenters.
    Uses the ALREADY-OPEN sync playwright page (same browser session the
    scrolling loop is using).

    visited_posts: a persistent set of post URLs already scraped.
                   Posts in this set will be skipped. New posts are added to it.

    Returns a list of dicts: [{username, source, source_hashtag, target_customer}, ...]
    """
    if visited_posts is None:
        visited_posts = set()
    config = get_target_config(target_customer)
    if not config:
        log(f"❌ Unknown target customer: {target_customer}")
        return []

    hashtags = config["hashtags"]
    session_hashtags = random.sample(hashtags, min(MAX_HASHTAGS_PER_SESSION, len(hashtags)))

    log(f"🔍 [Scraper] Target: {config['name']}")
    log(f"🔍 [Scraper] Hashtags: {session_hashtags}")

    all_users: list[dict] = []
    seen: set[str] = set()
    collected = 0

    for hashtag in session_hashtags:
        if collected >= MAX_ACCOUNTS_PER_SESSION:
            break

        log(f"  🏷️ Searching for #{hashtag} via search bar...")

        try:
            # Use the search engine to type the hashtag naturally
            search_term = f"#{hashtag}"
            if not perform_search(page, search_term, "hashtag", log):
                log(f"  ⚠️ Could not search for #{hashtag}, skipping...")
                continue

            # Wait for hashtag page to load
            _human_delay_sync("page_load")

            # check for login redirect
            if "login" in page.url.lower():
                log("  ⚠️ Redirected to login — skipping this hashtag")
                continue

            # scroll a bit to load posts
            for _ in range(random.randint(1, 2)):
                page.keyboard.press("PageDown")
                _human_delay_sync("scroll")

            # collect post links
            post_links = page.query_selector_all('a[href*="/p/"]')
            post_urls = []
            for link in post_links[:MAX_POSTS_PER_HASHTAG * 2]:
                href = link.get_attribute("href")
                if href and "/p/" in href:
                    full_url = f"https://www.instagram.com{href}" if href.startswith("/") else href
                    if full_url not in post_urls:
                        post_urls.append(full_url)
                        if len(post_urls) >= MAX_POSTS_PER_HASHTAG:
                            break

            # Filter out already-visited posts
            new_post_urls = [u for u in post_urls if u not in visited_posts]
            skipped = len(post_urls) - len(new_post_urls)
            if skipped > 0:
                log(f"  ⏭️ Skipping {skipped} already-scraped posts")
            log(f"  📝 {len(new_post_urls)} new posts to scrape")

            for i, post_url in enumerate(new_post_urls):
                if collected >= MAX_ACCOUNTS_PER_SESSION:
                    break

                # Mark this post as visited so it's never scraped again
                visited_posts.add(post_url)

                log(f"    📄 Post {i+1}/{len(new_post_urls)}...")
                try:
                    page.goto(post_url, wait_until="domcontentloaded")
                    try:
                        page.wait_for_selector('article', timeout=10000)
                    except:
                        pass
                    _human_delay_sync("read_content")

                    owner = _extract_post_owner(page)
                    if owner and owner not in seen:
                        seen.add(owner)
                        all_users.append({
                            "username": owner,
                            "source": "post_owner",
                            "source_hashtag": hashtag,
                            "target_customer": target_customer,
                        })
                        collected += 1
                        log(f"      👤 Owner: @{owner}")

                    if owner:
                        log("      💬 Scrolling comments...")
                        commenters = _extract_commenters(page, owner, max_commenters, log)
                        if commenters:
                            log(f"      💬 Found {len(commenters)} commenters")
                            for c in commenters:
                                if c not in seen:
                                    seen.add(c)
                                    all_users.append({
                                        "username": c,
                                        "source": "commenter",
                                        "source_hashtag": hashtag,
                                        "target_customer": target_customer,
                                    })
                                    collected += 1
                        else:
                            log("      💬 No commenters found")

                except Exception as e:
                    log(f"      ❌ Post error: {e}")

                _human_delay_sync("between_posts")
                _maybe_take_break_sync(log)

        except Exception as e:
            log(f"  ❌ Hashtag error: {e}")

        # wait between hashtags
        if hashtag != session_hashtags[-1]:
            log("  ⏳ Waiting before next hashtag...")
            _human_delay_sync("between_hashtags")

    log(f"📊 [Scraper] Total collected: {len(all_users)} accounts")
    return all_users


# =====================================================================
#  Full pipeline: scrape ➜ ollama ➜ CSV ➜ usernames
# =====================================================================

def run_scraper_pipeline_sync(page, target_customer: str,
                              max_commenters: int = MAX_COMMENTERS_PER_POST,
                              model: str = "llama3:8b",
                              log=print,
                              visited_posts: set = None) -> list[str]:
    """
    Run the complete scraper pipeline on the existing sync page:
      1. scrape hashtag pages for usernames (skipping already-visited posts)
      2. send to ollama for analysis
      3. export to CSV
      4. return the username list

    visited_posts: persistent set of post URLs already scraped (shared across runs).
    The caller (hybrid.py) is responsible for visiting each username
    via search_engine.perform_search afterwards.
    """
    if visited_posts is None:
        visited_posts = set()

    log("\n" + "=" * 50)
    log("🚀 SCRAPER PIPELINE STARTED")
    log(f"📌 {len(visited_posts)} posts already scraped in previous runs")
    log("=" * 50)

    # Step 1 — scrape
    scraped = scrape_hashtags_sync(page, target_customer, max_commenters, log, visited_posts)
    if not scraped:
        log("⚠️ Pipeline ended: no accounts scraped")
        return []

    owners = [u for u in scraped if u.get("source") == "post_owner"]
    commenters = [u for u in scraped if u.get("source") == "commenter"]
    log(f"📊 Collected: {len(owners)} owners, {len(commenters)} commenters")

    # Step 2 — Ollama analysis
    log(f"🧠 [Ollama] Analyzing {len(scraped)} accounts...")
    results = analyze_accounts(scraped, target_customer=target_customer, model=model)
    log(f"🧠 [Ollama] Filtered to {len(results)} relevant accounts")

    if results:
        for r in results[:5]:
            log(f"   @{r.get('username','?')} – {r.get('niche','?')} – relevance: {r.get('relevance','?')}/10")
        if len(results) > 5:
            log(f"   ... and {len(results) - 5} more")

    if not results:
        log("⚠️ Pipeline ended: no relevant accounts after analysis")
        return []

    # Step 3 — export CSV
    csv_path = export_to_csv(results, target_customer)
    log(f"💾 [Export] Saved to: {csv_path}")

    # Step 4 — extract username column
    usernames: list[str] = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                uname = row.get("username", "").strip()
                if uname:
                    usernames.append(uname)
    except Exception as e:
        log(f"❌ Error reading CSV: {e}")

    log(f"\n✅ Pipeline complete! {len(usernames)} usernames ready for visiting")
    log("=" * 50 + "\n")
    return usernames
