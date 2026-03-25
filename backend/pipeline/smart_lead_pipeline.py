"""
Smart Lead Pipeline — Unified scrolling + scraping + qualification + follow.

Orchestrates three phases in a single Playwright session:
  Phase 1: Discovery Brain generates search plan (background thread)
           while the browser scrolls normally on the feed.
  Phase 2: Scraper agent visits hashtag pages from the plan, opens
           individual posts, extracts post owners + commenters to build
           a username list.  Interleaved with normal scrolling.
  Phase 3: Qualification loop — scroll normally on feed, 30 % chance
           per scroll to visit the next profile from the list → search
           → scroll profile → extract data → qualify with AI → follow
           if qualified → go back to home → keep scrolling.
"""

import re
import time
import random
import threading
from typing import Callable

from playwright.sync_api import sync_playwright

from browser.scrolling import (
    create_log_function,
    create_stop_checker,
    do_single_scroll,
    try_random_like,
    launch_instagram_browser,
)
from browser.search_engine import perform_search
from browser.hybrid import scroll_on_page, go_back_to_feed, scroll_to_top_and_follow
from browser.launcher import DEFAULT_BROWSER, DEFAULT_HEADLESS
from browser.scraper import (
    is_valid_username,
    USERNAME_PATTERN,
    MAX_POSTS_PER_HASHTAG,
    MAX_COMMENTERS_PER_POST,
    get_delay,
)
from browser.scraper_integration import (
    _human_delay_sync,
    _maybe_take_break_sync,
    _extract_post_owner,
    _extract_commenters,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _parse_count(val: str) -> int:
    """
    Parse follower / following count strings like '1,234' or '12.3K'.

    FIX Bug 1: strip both commas AND spaces before processing, and use
    a more permissive float conversion so '12.3K' is handled correctly.
    """
    val = val.strip().replace(",", "").replace(" ", "")
    multiplier = 1
    if val.lower().endswith("k"):
        multiplier = 1_000
        val = val[:-1]
    elif val.lower().endswith("m"):
        multiplier = 1_000_000
        val = val[:-1]
    try:
        return int(float(val) * multiplier)
    except (ValueError, TypeError):
        return 0


def _extract_sync_profile_data(page, username: str, log=print) -> dict:
    """
    Extract profile data from the current profile page (sync Playwright).
    Returns a dict suitable for qualification_brain.
    """
    data = {"username": username}

    try:
        # ── Full name from og:title ──
        try:
            og_title = page.get_attribute('meta[property="og:title"]', "content")
            if og_title and "(" in og_title:
                data["full_name"] = og_title.split("(")[0].strip()
            elif og_title:
                data["full_name"] = og_title.split("•")[0].strip()
            else:
                data["full_name"] = ""
        except Exception:
            data["full_name"] = ""

        # ── Bio + follower / following counts from og:description ──
        try:
            og_desc = page.get_attribute('meta[property="og:description"]', "content")
            if og_desc:
                parts = og_desc.split(" - ", 1)
                data["bio"] = parts[1][:300].strip() if len(parts) > 1 else ""

                # FIX Bug 1: more permissive regex — dot is outside the
                # character class so decimal values like "12.3K" are captured.
                # Also matches plurals (Followers, Posts) for robustness.
                nums = re.findall(
                    r"([\d,]+\.?\d*\s*[KkMm]?)\s+(Followers?|Following|Posts?)",
                    og_desc,
                )
                for val, label in nums:
                    parsed = _parse_count(val)
                    if "ollower" in label:       # Follower / Followers
                        data["followers_count"] = parsed
                    elif "ollowing" in label:
                        data["following_count"] = parsed
            else:
                data["bio"] = ""
        except Exception:
            data["bio"] = ""

        data.setdefault("followers_count", 0)
        data.setdefault("following_count", 0)

        # ── Profile image ──
        try:
            og_img = page.get_attribute('meta[property="og:image"]', "content")
            data["profile_image_url"] = og_img or ""
        except Exception:
            data["profile_image_url"] = ""

        # ── Recent captions from alt text ──
        captions: list[str] = []
        try:
            imgs = page.query_selector_all("article img[alt]")
            for img in imgs[:5]:
                alt = img.get_attribute("alt")
                if alt and len(alt) > 10:
                    captions.append(alt[:300])
        except Exception:
            pass
        data["recent_captions"] = captions
        data["recent_comments"] = []

        # ── Language detection ──
        all_text = " ".join([data.get("bio", ""), data.get("full_name", "")])
        all_text += " ".join(captions)
        jp_chars = len(re.findall(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", all_text))
        total = max(len(all_text), 1)
        data["detected_language"] = "ja" if jp_chars / total > 0.1 else "en"

    except Exception as e:
        log(f"    Profile extraction error: {e}")

    return data


# ── Work / lifestyle signal keywords (used by pre-filter) ───────────
# FIX Bug 3: all entries are lowercased so they match `all_text.lower()`
# without any case mismatch (was: "IT", "DIY", "SNS" etc. never matched).

WORK_LIFESTYLE_SIGNALS = [s.lower() for s in [
    # English signals
    "ceo", "founder", "coach", "mentor", "entrepreneur", "business",
    "consultant", "freelance", "creator", "artist", "photographer",
    "designer", "developer", "writer", "trainer", "influencer",
    "brand", "shop", "store", "link in bio", "dm for", "bookings",
    "available", "services", "portfolio", "www.", "http", ".com",
    "\U0001f4e7", "\U0001f4e9", "\U0001f4bc", "\U0001f517", "\U0001f447", "\u2b07\ufe0f",
    "collab", "partnership", "work with me", "enquiries", "management",
    # Japanese work/lifestyle signals
    "看護師", "介護", "工場", "運送", "バイト", "副業", "パート",
    "転職", "仕事", "働く", "社会人", "新卒", "正社員", "派遣",
    "車", "ドライブ", "大学", "専門学校", "卒業",
    "稼ぐ", "お金", "収入", "フリーランス",
    "地方", "田舎", "先生", "会計士", "公務員", "教師", "IT", "エンジニア",
    "プログラマー", "デザイナー", "編集者", "ライター", "営業", "看護師",
    "医師", "歯科", "薬剤師", "保育士", "介護士", "弁護士",
    "司法書士", "行政書士", "税理士", "教師", "秘書", "店員", "事務",
    "受付", "美容師", "モデル", "俳優", "女優", "歌手", "ミュージシャン",
    "クリエイター", "イラストレーター", "カメラマン", "フォトグラファー",
    "動画編集", "youtuber", "インフルエンサー", "通訳", "翻訳", "学生",
    "大学生", "短大生", "高校生", "専門学生", "大学院生", "新卒", "社会人",
    "転職", "独立", "副業", "兼業", "在宅", "リモート", "起業", "経営者",
    "自営業", "飲食", "バリスタ", "シェフ", "師匠", "オーナー", "カフェ",
    "ショップ", "ブランド", "スタイリスト", "カウンセラー", "コーチ",
    "コンサル", "トレーナー", "インストラクター", "ヨガ", "ピラティス",
    "体育", "スポーツ選手", "サッカー", "野球", "テニス", "バスケットボール",
    "陸上", "スポーツ", "ボディビル", "ダンサー", "俳優", "声優", "作家",
    "ディレクター", "編集者", "主婦", "主夫", "ママ", "パパ", "子育て",
    "ペット", "犬", "猫", "うさぎ", "趣味", "旅行", "バックパッカー",
    "世界一周", "海外移住", "英語", "留学", "交換留学", "国際", "外国人",
    "国際結婚", "婚活", "恋愛", "保険", "金融", "投資", "資産運用", "節約",
    "副収入", "おうち時間", "DIY", "料理", "カフェ巡り", "食べ歩き",
    "グルメ", "アウトドア", "キャンプ", "釣り", "登山", "ランニング",
    "ジョギング", "筋トレ", "フィットネス", "健康", "美容", "スキンケア",
    "ネイル", "メイク", "ファッション", "コーデ", "アクセサリー", "着物",
    "着付け", "和装", "茶道", "華道", "書道", "音楽", "演奏", "ピアノ",
    "ギター", "バイオリン", "カラオケ", "映画", "ドラマ", "アニメ", "漫画",
    "イラスト", "ゲーム", "コスプレ", "旅行好き", "温泉", "ドライブ",
    "愛車", "自転車", "整体", "マッサージ", "エステ", "カウンセリング",
    "心理", "ライフコーチ", "自己啓発", "起業家", "副業女子", "副業男子",
    "資産形成", "年収アップ", "転職活動", "転職エージェント", "会社員",
    "正社員", "アルバイト", "パート", "フリーター", "物販", "せどり",
    "ハンドメイド", "輸入", "輸出", "クラウドワークス", "ランサーズ",
    "ココナラ", "fiverr", "スキルシェア", "ネットビジネス", "SNS運用",
    "集客", "LINE公式", "note", "ブログ", "アフィリエイト", "EC",
    "ネットショップ", "動画制作", "ライブ配信", "写真", "インスタ映え",
    "観光", "旅行記", "食レポ", "お菓子作り", "パン作り", "ヴィーガン",
    "ベジタリアン", "子ども", "家庭", "教育", "塾", "教師", "教室",
    "ワークショップ", "ボランティア", "地域活性化", "農業", "自然",
    "地方創生", "移住", "サブスク",
]]


def _pre_filter_profile(
    page,
    username: str,
    target_interest: str,
    optional_keywords: list[str] | None = None,
    log=print,
) -> bool:
    """
    Quick profile visit to decide if a commenter is worth qualifying.

        Returns **True** to KEEP the profile (premium candidate).

        The pre-filter is intentionally conservative: it should only reject
        profiles when signals are broadly weak across follower, niche, bio,
        and lifestyle checks. This avoids dropping niche-fit users just
        because one field is sparse.

    NOTE: This function navigates the page to the profile URL.
    Callers must handle restoring page state after this returns
    (e.g. page.go_back() to return to the hashtag listing).
    """
    try:
        page.goto(
            f"https://www.instagram.com/{username}/",
            wait_until="domcontentloaded",
        )
        try:
            page.wait_for_selector(
                'meta[property="og:description"]', timeout=8_000
            )
        except Exception:
            pass
        _human_delay_sync("read_content")

        data = _extract_sync_profile_data(page, username, log)

        bio = data.get("bio", "").strip()
        full_name = (data.get("full_name") or "").strip()
        followers = data.get("followers_count", 0)
        captions = data.get("recent_captions", [])

        # ── Build niche keywords from the user's target interest ──
        niche_keywords: set[str] = set()

        def _add_keywords(source: str):
            # Keep non-Latin tokens with length >= 2, and Latin tokens > 2.
            for token in re.split(r"[\s,/#|:;()\[\]{}+_-]+", source.lower()):
                word = token.strip()
                if not word:
                    continue
                if re.search(r"[a-z]", word):
                    if len(word) > 2:
                        niche_keywords.add(word)
                elif len(word) >= 2:
                    niche_keywords.add(word)

        _add_keywords(target_interest)
        if optional_keywords:
            for kw in optional_keywords:
                _add_keywords(kw)

        # Combine all available profile text so signals don't depend only on bio.
        combined_text = " ".join([
            username,
            full_name,
            bio,
            " ".join(captions),
        ]).lower()

        niche_hit = any(kw in combined_text for kw in niche_keywords)
        lifestyle_hit = any(sig in combined_text for sig in WORK_LIFESTYLE_SIGNALS)

        # Bio check: treat >= 8 non-whitespace chars as meaningful.
        bio_chars = len(re.sub(r"\s+", "", bio))
        bio_substantive = bio_chars >= 8

        # Follower tiers. Very low is only used for hard reject.
        followers_very_low = followers < 40
        followers_low = followers < 120

        # Keep quickly when we have at least one strong positive combination.
        if niche_hit:
            log(f"      ✅ @{username} pre-filter PASSED (niche match)")
            return True
        if lifestyle_hit and not followers_very_low:
            log(f"      ✅ @{username} pre-filter PASSED (lifestyle signal + followers={followers})")
            return True
        if bio_substantive and not followers_low:
            log(f"      ✅ @{username} pre-filter PASSED (substantive bio + followers={followers})")
            return True

        # Reject only when all channels are weak at the same time.
        if (not bio_substantive) and (not niche_hit) and (not lifestyle_hit) and followers_very_low:
            log(
                f"      ❌ @{username} filtered out: "
                f"weak bio, no niche match, no lifestyle signals, "
                f"very low followers ({followers})"
            )
            return False

        reasons: list[str] = []
        if bio_substantive:
            reasons.append("bio")
        if niche_hit:
            reasons.append("niche match")
        if lifestyle_hit:
            reasons.append("lifestyle signals")
        if not followers_low:
            reasons.append(f"{followers} followers")
        elif followers > 0:
            reasons.append(f"{followers} followers (low)")

        if not reasons:
            reasons.append("uncertain but not hard-reject")

        log(f"      ✅ @{username} pre-filter PASSED ({', '.join(reasons)})")
        return True

    except Exception as e:
        log(f"      ⚠️ Pre-filter error for @{username}: {e}")
        return True  # keep on error — let qualification decide


# ══════════════════════════════════════════════════════════════════════
#  Scraper agent — visits hashtag pages → opens posts → extracts
#  post owners + commenters.  Adapted from scraper_integration.py but
#  takes hashtags directly from the discovery plan (no config lookup).
# ══════════════════════════════════════════════════════════════════════

MAX_ACCOUNTS_TO_SCRAPE = 120  # hard cap per scrape run


def _scrape_hashtags_from_plan(
    page,
    hashtags: list[str],
    should_stop: Callable,
    log=print,
    visited_posts: set | None = None,
    max_accounts: int = 50,
    target_interest: str = "",
    optional_keywords: list[str] | None = None,
) -> list[str]:
    """
    Navigate to hashtag pages from the discovery plan, open individual
    posts, and extract post owners + commenters.

    FIX Bug 2: raw_candidates are fully collected from each post FIRST,
    then pre-filtering runs as a dedicated second pass. This ensures
    _pre_filter_profile's page.goto() calls don't clobber the page state
    mid-extraction. After pre-filtering, page.go_back() restores the
    hashtag listing so subsequent post links remain accessible.

    Returns a list of unique usernames that passed the pre-filter.
    """
    if visited_posts is None:
        visited_posts = set()

    max_accounts = min(max_accounts, MAX_ACCOUNTS_TO_SCRAPE)
    session_hashtags = random.sample(hashtags, min(5, len(hashtags)))

    log(f"🔍 [Scraper] Hashtags to scrape: {session_hashtags}")

    all_usernames: list[str] = []
    seen: set[str] = set()
    collected = 0

    for hashtag in session_hashtags:
        if collected >= max_accounts or should_stop():
            break

        clean_tag = hashtag.lstrip("#")
        direct_url = f"https://www.instagram.com/explore/tags/{clean_tag}/"
        log(f"  🏷️ Navigating to #{clean_tag} via direct URL...")

        try:
            # Always use direct URL for hashtags — the search bar UI
            # does not render reliably in headless mode (e.g. on Render).
            try:
                page.goto(direct_url, wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass
                log(f"  ✅ Loaded #{clean_tag} hashtag page")
            except Exception as e:
                log(f"  ❌ Failed to navigate to #{clean_tag}: {e}")
                continue

            _human_delay_sync("page_load")

            if "login" in page.url.lower():
                log("  ⚠️ Redirected to login — skipping this hashtag")
                continue

            # Scroll to load posts on the hashtag page
            for _ in range(random.randint(1, 3)):
                page.keyboard.press("PageDown")
                _human_delay_sync("scroll")

            # Collect post links visible on the hashtag page
            post_links = page.query_selector_all('a[href*="/p/"]')
            post_urls: list[str] = []
            for link in post_links[:MAX_POSTS_PER_HASHTAG * 2]:
                href = link.get_attribute("href")
                if href and "/p/" in href:
                    full_url = (
                        f"https://www.instagram.com{href}"
                        if href.startswith("/")
                        else href
                    )
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

            # Visit each post, extract candidates, then pre-filter
            for i, post_url in enumerate(new_post_urls):
                if collected >= max_accounts or should_stop():
                    break

                visited_posts.add(post_url)
                log(f"    📄 Post {i + 1}/{len(new_post_urls)}...")

                try:
                    page.goto(post_url, wait_until="domcontentloaded")
                    try:
                        page.wait_for_selector("article", timeout=10_000)
                    except Exception:
                        pass
                    _human_delay_sync("read_content")

                    # ── Phase A: collect all candidates from this post ──
                    # (no navigation happens here — page stays on the post)
                    raw_candidates: list[str] = []

                    owner = _extract_post_owner(page)
                    if owner:
                        log(f"      👤 Owner: @{owner}")
                        raw_candidates.append(owner)

                        log("      💬 Scrolling comments...")
                        commenters = _extract_commenters(
                            page, owner, MAX_COMMENTERS_PER_POST, log
                        )
                        if commenters:
                            log(f"      💬 Found {len(commenters)} commenters")
                            raw_candidates.extend(commenters)
                        else:
                            log("      💬 No commenters found")

                    # De-duplicate against already-seen before pre-filtering
                    raw_candidates = [c for c in raw_candidates if c not in seen]

                    # ── Phase B: pre-filter (navigates away per candidate) ──
                    # FIX Bug 2: this now runs AFTER all extraction is done,
                    # so page state is not corrupted mid-post.
                    if raw_candidates and target_interest:
                        log(f"      🔍 Pre-filtering {len(raw_candidates)} candidates...")
                        for candidate in raw_candidates:
                            if collected >= max_accounts or should_stop():
                                break
                            passed = _pre_filter_profile(
                                page, candidate, target_interest,
                                optional_keywords, log,
                            )
                            if passed:
                                seen.add(candidate)
                                all_usernames.append(candidate)
                                collected += 1
                            _human_delay_sync("between_posts")

                        # Restore the hashtag page so the next post link works
                        log(f"  🔙 Returning to #{clean_tag} listing...")
                        page.go_back()
                        try:
                            page.wait_for_selector('a[href*="/p/"]', timeout=8_000)
                        except Exception:
                            pass

                    elif raw_candidates:
                        # No target_interest — skip pre-filter, keep all
                        for candidate in raw_candidates:
                            if candidate not in seen and collected < max_accounts:
                                seen.add(candidate)
                                all_usernames.append(candidate)
                                collected += 1

                except Exception as e:
                    log(f"      ❌ Post error: {e}")

                _human_delay_sync("between_posts")
                _maybe_take_break_sync(log)

        except Exception as e:
            log(f"  ❌ Hashtag error: {e}")

        # Wait between hashtags
        if hashtag != session_hashtags[-1]:
            log("  ⏳ Waiting before next hashtag...")
            _human_delay_sync("between_hashtags")

    log(f"📊 [Scraper] Total collected: {collected} usernames")
    return all_usernames


# ── Main pipeline ────────────────────────────────────────────────────


def run_smart_lead_pipeline(
    cookies: list[dict],
    target_interest: str,
    optional_keywords: list[str] | None = None,
    max_profiles: int = 50,
    headless: bool = False,
    browser_type: str = "chrome",
    model: str = "gpt-4.1-mini",
    stop_flag=None,
    log_callback=None,
    on_plan_ready: Callable | None = None,
) -> dict:
    """
    Unified lead-generation pipeline: scroll → scrape → qualify → follow.

    Flow
    ----
    1. **Discovery Brain** generates a search plan in a background thread
       while the browser scrolls the feed naturally.
    2. Once the plan arrives the **scraper agent** takes over the page:
       visits hashtag pages from the plan → opens individual posts →
       extracts post owners + commenters → builds a username list.
    3. After scraping completes, enters the **qualification loop**:
       scroll normally on feed → 30 % chance per scroll to visit the
       next profile from the list → search username → scroll profile →
       extract data → qualify with AI → follow if qualified → go back
       to home → keep scrolling → repeat until all profiles done.

    Returns a result dict: leads, all_results, total_scanned,
    total_qualified, profiles_followed, discovery_plan, stats.
    """
    log = create_log_function(log_callback)
    should_stop = create_stop_checker(stop_flag)

    # ── Shared state between threads ──
    plan_holder: dict = {"ready": False, "plan": None, "error": None}
    plan_lock = threading.Lock()

    # ── Phase 1: Discovery Brain (background thread) ──────────────
    def _run_discovery():
        try:
            log("🧠 Phase 1: Generating discovery plan with AI...")
            from agents.discovery_brain import generate_discovery_plan as gen_plan

            plan = gen_plan(
                target_interest=target_interest,
                optional_keywords=optional_keywords,
                max_profiles=max_profiles,
                model=model,
            )
            with plan_lock:
                plan_holder["plan"] = plan
                plan_holder["ready"] = True

            hashtags = plan.get("hashtags", [])
            queries = plan.get("search_queries", [])
            seeds = plan.get("seed_accounts", [])
            log(
                f"✅ Discovery plan ready: "
                f"{len(hashtags)} hashtags, {len(queries)} queries, {len(seeds)} seeds"
            )

            if on_plan_ready:
                on_plan_ready(plan)

        except Exception as e:
            with plan_lock:
                plan_holder["error"] = str(e)
                plan_holder["ready"] = True
            log(f"❌ Discovery plan error: {e}")

    discovery_thread = threading.Thread(target=_run_discovery, daemon=True)
    discovery_thread.start()

    # ── Prepare Qualification Brain ──
    log("Loading Qualification Brain...")
    from agents.qualification_brain import make_inline_qualifier

    qualify_fn = make_inline_qualifier(model=model)

    # ── State ──
    collected_usernames: list[str] = []
    visited_posts: set[str] = set()
    qualified_leads: list[dict] = []
    stats = {
        "scrolls": 0,
        "likes": 0,
        "scraper_runs": 0,
        "profiles_visited": 0,
        "profiles_followed": 0,
        "total_scanned": 0,
        "total_qualified": 0,
    }
    plan_received = False
    scraping_done = False

    # ── Launch browser ──
    with sync_playwright() as p:
        browser, context, page = launch_instagram_browser(
            p, cookies, headless, log, browser_type=browser_type,
        )

        # ════════════════════════════════════════════════════════════
        #  Phase 2 — Scroll normally while waiting for the discovery
        #  plan, then run the scraper agent to collect usernames.
        # ════════════════════════════════════════════════════════════
        log(f"\n🔄 Phase 2: Scrolling & waiting for discovery plan...")

        while not should_stop() and not scraping_done:
            # ── Normal feed scroll ──
            stats["scrolls"] += 1
            status = "🧠 Waiting for plan..." if not plan_received else "🔍 Scraping..."
            log(
                f"📜 Scroll #{stats['scrolls']} | "
                f"❤️ {stats['likes']} | "
                f"📋 {len(collected_usernames)} collected | {status}"
            )

            do_single_scroll(page, log)
            if try_random_like(page, log=log):
                stats["likes"] += 1

            # ── Check if discovery plan arrived ──
            if not plan_received:
                with plan_lock:
                    if plan_holder["ready"]:
                        if plan_holder["error"]:
                            log(f"❌ Discovery failed: {plan_holder['error']}. Stopping.")
                            break
                        plan_received = True
                        log("📋 Discovery plan received! Starting scraper agent...")

            # ── Scraper: runs once the plan is ready ──
            if plan_received and not scraping_done:
                plan = plan_holder["plan"]
                hashtags = plan.get("hashtags", [])

                if not hashtags:
                    log("⚠️ No hashtags in discovery plan. Skipping scraping phase.")
                    scraping_done = True
                    continue

                stats["scraper_runs"] += 1
                log(f"\n🔬 SCRAPER AGENT STARTING (run #{stats['scraper_runs']})")
                log(f"📌 {len(visited_posts)} posts already scraped")

                new_usernames = _scrape_hashtags_from_plan(
                    page=page,
                    hashtags=hashtags,
                    should_stop=should_stop,
                    log=log,
                    visited_posts=visited_posts,
                    max_accounts=max_profiles,
                    target_interest=target_interest,
                    optional_keywords=optional_keywords,
                )

                # De-duplicate and store
                existing_set = set(collected_usernames)
                for uname in new_usernames:
                    if uname not in existing_set:
                        collected_usernames.append(uname)
                        existing_set.add(uname)

                log(
                    f"📊 Scraper collected {len(new_usernames)} usernames "
                    f"(total unique: {len(collected_usernames)})"
                )

                go_back_to_feed(page, log)
                scraping_done = True

                log("📜 Resuming natural scrolling before qualification phase...")
                for _ in range(random.randint(2, 4)):
                    if should_stop():
                        break
                    do_single_scroll(page, log)
                    if try_random_like(page, log=log):
                        stats["likes"] += 1
                    stats["scrolls"] += 1

        # ── Early exit if stopped or nothing collected ──
        if should_stop() or not collected_usernames:
            log("No accounts collected or stopped. Closing browser...")
            context.close()
            browser.close()
            return _build_result(
                plan_holder.get("plan") or {}, qualified_leads, stats
            )

        # ════════════════════════════════════════════════════════════
        #  Phase 3 — Infinite qualification mode.
        #  Keep cycling scrape + qualify until `max_profiles` qualified
        #  leads are reached or the user stops the task.
        #  If progress is dry for too long, enter "rest mode" and just
        #  scroll feed normally before the next scrape cycle.
        # ════════════════════════════════════════════════════════════
        visit_index = 0
        stagnant_scrape_rounds = 0
        last_qualification_ts = time.time()

        REST_IDLE_SECONDS = 12 * 60
        REST_SCROLLS_MIN = 8
        REST_SCROLLS_MAX = 16
        RESCRAPE_BATCH_MIN = 60

        stats.setdefault("rest_cycles", 0)

        def _run_rest_mode(reason: str):
            rest_scrolls = random.randint(REST_SCROLLS_MIN, REST_SCROLLS_MAX)
            stats["rest_cycles"] += 1
            log(
                f"😴 Rest mode #{stats['rest_cycles']} ({reason}) — "
                f"scrolling feed naturally x{rest_scrolls}"
            )
            go_back_to_feed(page, log)
            for _ in range(rest_scrolls):
                if should_stop() or stats["total_qualified"] >= max_profiles:
                    break
                do_single_scroll(page, log)
                stats["scrolls"] += 1
                if try_random_like(page, log=log):
                    stats["likes"] += 1
                time.sleep(random.uniform(1.0, 2.5))

        log(
            f"\n🎯 Phase 3: Infinite qualification loop — target {max_profiles} qualified leads "
            f"(runs until quota reached or manually stopped)"
        )

        while stats["total_qualified"] < max_profiles and not should_stop():
            # ── If candidates exhausted, keep re-scraping indefinitely ──
            if visit_index >= len(collected_usernames):
                plan = plan_holder.get("plan") or {}
                hashtags = plan.get("hashtags", [])

                if not hashtags:
                    log("⚠️ Discovery plan has no hashtags. Entering feed rest mode before retry...")
                    _run_rest_mode("missing hashtags")
                    continue

                stats["scraper_runs"] += 1
                remaining = max_profiles - stats["total_qualified"]
                batch_size = max(remaining * 3, RESCRAPE_BATCH_MIN)
                log(
                    f"\n🔄 Re-scrape run #{stats['scraper_runs']} "
                    f"— need {remaining} more qualified leads (batch={batch_size})"
                )

                go_back_to_feed(page, log)
                new_usernames = _scrape_hashtags_from_plan(
                    page=page,
                    hashtags=hashtags,
                    should_stop=should_stop,
                    log=log,
                    visited_posts=visited_posts,
                    max_accounts=batch_size,
                    target_interest=target_interest,
                    optional_keywords=optional_keywords,
                )

                existing_set = set(collected_usernames)
                before_total = len(collected_usernames)
                for uname in new_usernames:
                    if uname not in existing_set:
                        collected_usernames.append(uname)
                        existing_set.add(uname)
                added = len(collected_usernames) - before_total

                go_back_to_feed(page, log)
                log(f"📊 Re-scrape added {added} new usernames (pool: {len(collected_usernames)})")

                if added == 0:
                    stagnant_scrape_rounds += 1
                    if stagnant_scrape_rounds >= 3:
                        # Allow revisiting old post URLs after long drought.
                        visited_posts.clear()
                        stagnant_scrape_rounds = 0
                        log("♻️ Reset visited post cache after repeated dry scrapes.")
                    _run_rest_mode("no new candidates found")
                    continue

                stagnant_scrape_rounds = 0
                continue

            # ── Regular feed behavior between profile visits ──
            stats["scrolls"] += 1
            remaining_quota = max_profiles - stats["total_qualified"]
            log(
                f"📜 Scroll #{stats['scrolls']} | "
                f"❤️ {stats['likes']} | "
                f"👤 {stats['profiles_visited']} visited | "
                f"✅ {stats['total_qualified']}/{max_profiles} qualified | "
                f"🎯 {remaining_quota} more needed"
            )

            do_single_scroll(page, log)
            if try_random_like(page, log=log):
                stats["likes"] += 1

            # Long dry period -> cool down with natural feed scrolling.
            idle_seconds = time.time() - last_qualification_ts
            if idle_seconds >= REST_IDLE_SECONDS:
                _run_rest_mode(f"{int(idle_seconds // 60)} min without new qualified leads")
                last_qualification_ts = time.time()
                continue

            # 30 % chance to visit the next profile
            if random.random() >= 0.30:
                continue

            username = collected_usernames[visit_index]
            visit_index += 1

            log(f"\n{'=' * 40}")
            log(f"👤 Visiting @{username} ({stats['profiles_visited'] + 1} visited total)")
            log(f"{'=' * 40}")

            try:
                # Navigate directly to the profile page — search bar UI
                # does not render reliably in headless mode (e.g. on Render).
                profile_url = f"https://www.instagram.com/{username}/"
                log(f"🔗 Navigating directly to {profile_url}")
                try:
                    page.goto(profile_url, wait_until="domcontentloaded")
                    try:
                        page.wait_for_load_state("networkidle", timeout=10_000)
                    except Exception:
                        pass
                except Exception as e:
                    log(f"⚠️ Could not load @{username}: {e}")
                    go_back_to_feed(page, log)
                    continue

                # Check if redirected to login
                if "login" in page.url.lower():
                    log(f"⚠️ Redirected to login when visiting @{username}, skipping...")
                    go_back_to_feed(page, log)
                    continue

                time.sleep(random.uniform(2.5, 4.0))
                stats["profiles_visited"] += 1
                stats["total_scanned"] += 1

                num_scrolls = random.randint(3, 6)
                log(f"📜 Scrolling {num_scrolls} times on profile...")
                scroll_on_page(page, num_scrolls, should_stop, log)

                # Force full page load to refresh meta tags
                log(f"🔄 Reloading @{username} profile for fresh data...")
                page.goto(
                    f"https://www.instagram.com/{username}/",
                    wait_until="domcontentloaded",
                )
                try:
                    page.wait_for_selector(
                        'meta[property="og:description"]',
                        timeout=8_000,
                    )
                except Exception:
                    pass
                _human_delay_sync("read_content")

                profile_data = _extract_sync_profile_data(page, username, log)
                profile_data["discovery_source"] = "smart_pipeline"

                log(f"🧠 Qualifying @{username}...")
                scored = qualify_fn(profile_data)

                if scored and scored.get("is_target"):
                    stats["total_qualified"] += 1
                    qualified_leads.append(scored)
                    last_qualification_ts = time.time()

                    log(
                        f"✅ @{username} QUALIFIED! "
                        f"(score={scored.get('total_score', 0)}, "
                        f"confidence={scored.get('confidence', '?')}) "
                        f"[{stats['total_qualified']}/{max_profiles}]"
                    )

                    followed = scroll_to_top_and_follow(page, username, log)
                    if followed:
                        stats["profiles_followed"] += 1
                        log(f"➕ Followed @{username}!")

                    if stats["total_qualified"] >= max_profiles:
                        log(f"🎉 Quota reached! {max_profiles} qualified leads found.")
                        break
                else:
                    score = scored.get("total_score", 0) if scored else 0
                    log(f"✗ @{username} not qualified (score={score})")

                go_back_to_feed(page, log)
                time.sleep(random.uniform(3, 8))

            except Exception as e:
                log(f"❌ Error with @{username}: {e}")
                try:
                    go_back_to_feed(page, log)
                except Exception:
                    pass

        # ── Summary ──
        log(f"\n{'=' * 50}")
        log("🏁 SMART PIPELINE COMPLETE")
        log(f"{'=' * 50}")
        log(f"📜 Total scrolls: {stats['scrolls']}")
        log(f"❤️ Total likes: {stats['likes']}")
        log(f"🔬 Scraper runs: {stats['scraper_runs']}")
        log(f"👤 Profiles visited: {stats['profiles_visited']}")
        log(f"✅ Qualified leads: {stats['total_qualified']}")
        log(f"➕ Profiles followed: {stats['profiles_followed']}")
        log(f"{'=' * 50}")

        log("Closing browser...")
        context.close()
        browser.close()

    return _build_result(plan_holder.get("plan") or {}, qualified_leads, stats)


# ── Result builder ───────────────────────────────────────────────────


def _build_result(plan: dict, leads: list[dict], stats: dict) -> dict:
    """Build the final result dict matching the LeadGenResult shape."""
    leads_sorted = sorted(leads, key=lambda x: -(x.get("total_score") or 0))
    return {
        "leads": leads_sorted,
        "all_results": leads_sorted,
        "total_scanned": stats.get("total_scanned", 0),
        "total_qualified": stats.get("total_qualified", 0),
        "profiles_followed": stats.get("profiles_followed", 0),
        "discovery_plan": plan or {},
        "stats": stats,
    }
