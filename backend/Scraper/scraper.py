import asyncio
import random
import os
import re
from collections import Counter
from playwright.async_api import async_playwright
from config.targets import get_target_config

SESSION_DIR = "instagram_session"
USERNAME_PATTERN = re.compile(r'^/([a-zA-Z0-9_.]{1,30})/$')

MAX_ACCOUNTS_PER_SESSION = 30
MAX_HASHTAGS_PER_SESSION = 3
MAX_POSTS_PER_HASHTAG = 5
MAX_COMMENTERS_PER_POST = 15
MAX_COMMENT_SCROLLS = 3

EXCLUDED_PATHS = {
    '/', '/explore/', '/p/', '/reel/', '/reels/', '/stories/',
    '/accounts/', '/direct/', '/tags/', '/locations/'
}
SYSTEM_USERNAMES = {'explore', 'p', 'reel', 'reels', 'stories', 'accounts', 'direct'}

# Shared delay map used by both async and sync helpers
DELAY_MAP = {
    "page_load": (3, 6),
    "read_content": (2, 5),
    "between_posts": (4, 8),
    "between_hashtags": (15, 30),
    "scroll": (1, 3),
    "comment_scroll": (2, 4),
    "default": (2, 4)
}

# Selectors shared between async and sync scrapers
VIEW_MORE_SELECTORS = [
    'button:has-text("View")',
    'span:has-text("View all")',
    'button[type="button"]:has-text("more")',
]
COMMENT_SELECTORS = [
    'ul li a[href^="/"]',
    'div[role="button"] a[href^="/"]',
    'article ul a[href^="/"]',
    'section a[href^="/"]',
]


def is_valid_username(username: str, logged_in_user: str = None) -> bool:
    """Standalone username validator shared by async and sync scrapers."""
    if not username:
        return False
    if username in SYSTEM_USERNAMES:
        return False
    if username == logged_in_user:
        return False
    return True


def get_delay(action: str = "default") -> tuple[float, float]:
    """Return (min_sec, max_sec) for a given action."""
    return DELAY_MAP.get(action, DELAY_MAP["default"])


async def human_delay(action: str = "default"):
    min_sec, max_sec = get_delay(action)
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def maybe_take_break():
    if random.random() < 0.2:
        print("      [Taking a short break...]")
        await asyncio.sleep(random.uniform(8, 15))


async def login_and_save_session():
    print("Opening Instagram for login...")
    print("Please login manually. You have 120 seconds.")
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            SESSION_DIR,
            headless=False,
            viewport={"width": 1280, "height": 720}
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.instagram.com/accounts/login/")
        await asyncio.sleep(120)
        await context.close()
    
    print(f"Session saved to '{SESSION_DIR}/'")


def session_exists() -> bool:
    return os.path.exists(SESSION_DIR) and os.path.isdir(SESSION_DIR)


class InstagramScraper:
    def __init__(self, target_customer: str, headless: bool = False, max_commenters: int = MAX_COMMENTERS_PER_POST):
        self.headless = headless
        self.target_customer = target_customer
        self.config = get_target_config(target_customer)
        self.max_commenters = max_commenters
        
        if not self.config:
            raise ValueError(f"Unknown target customer: {target_customer}")
        
        self.hashtags = self.config["hashtags"]
        self.collected_count = 0
        self.logged_in_user = None
        self.excluded_paths = EXCLUDED_PATHS
        self.system_usernames = SYSTEM_USERNAMES
    
    def _is_valid_username(self, username: str) -> bool:
        return is_valid_username(username, self.logged_in_user)
    
    async def _extract_post_owner(self, page) -> str | None:
        # Strategy 1: Meta tags
        try:
            meta = await page.get_attribute('meta[property="og:description"]', 'content')
            if meta and '@' in meta:
                match = re.search(r'@([a-zA-Z0-9_.]+)', meta)
                if match and self._is_valid_username(match.group(1)):
                    return match.group(1)
        except:
            pass
        
        # Strategy 2: Page title
        try:
            title = await page.title()
            if title and ' on Instagram' in title:
                username = title.split(' on Instagram')[0].strip()
                if re.match(r'^[a-zA-Z0-9_.]+$', username) and self._is_valid_username(username):
                    return username
        except:
            pass
        
        # Strategy 3: Link scanning
        all_links = await page.query_selector_all('a[href^="/"]')
        candidates = []
        
        for link in all_links:
            href = await link.get_attribute("href")
            if not href or href in EXCLUDED_PATHS:
                continue
            if any(href.startswith(ex) for ex in ['/explore/', '/p/', '/reel/', '/tags/']):
                continue
            
            match = USERNAME_PATTERN.match(href)
            if match:
                username = match.group(1)
                if self._is_valid_username(username):
                    candidates.append(username)
                elif not self.logged_in_user and username not in self.system_usernames:
                    self.logged_in_user = username
        
        if candidates:
            return Counter(candidates).most_common(1)[0][0]
        
        return None
    
    async def _scroll_comments(self, page) -> None:
        """Scroll through comment section to load more comments."""
        try:
            # Try to find and click "View more comments" or scroll comment area
            for scroll_num in range(MAX_COMMENT_SCROLLS):
                
                clicked = False
                for selector in VIEW_MORE_SELECTORS:
                    try:
                        btn = await page.query_selector(selector)
                        if btn:
                            await btn.click()
                            clicked = True
                            print(f"        Loaded more comments ({scroll_num + 1}/{MAX_COMMENT_SCROLLS})")
                            await human_delay("comment_scroll")
                            break
                    except:
                        continue
                
                if not clicked:
                    # Try scrolling the comment section directly
                    try:
                        comment_section = await page.query_selector('ul[class*="comment"], div[class*="comment"]')
                        if comment_section:
                            await comment_section.scroll_into_view_if_needed()
                            await page.keyboard.press("PageDown")
                            await human_delay("comment_scroll")
                    except:
                        pass
                
                # Random chance to stop early (conservative behavior)
                if random.random() < 0.3:
                    break
                
                await maybe_take_break()
                
        except Exception as e:
            pass
    
    async def _extract_commenters(self, page, post_owner: str) -> list[str]:
        """Extract commenters from post, with scrolling to load more."""
        commenters = []
        seen_usernames = set()
        
        # First scroll to load more comments
        await self._scroll_comments(page)
        
        try:
            for selector in COMMENT_SELECTORS:
                if len(commenters) >= self.max_commenters:
                    break
                
                links = await page.query_selector_all(selector)
                
                for link in links:
                    if len(commenters) >= self.max_commenters:
                        break
                    
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                    
                    match = USERNAME_PATTERN.match(href)
                    if match:
                        username = match.group(1)
                        if (self._is_valid_username(username) and 
                            username != post_owner and 
                            username not in seen_usernames):
                            seen_usernames.add(username)
                            commenters.append(username)
            
            # Strategy 2: Scan all article links as fallback
            if len(commenters) < 3:
                all_links = await page.query_selector_all('article a[href^="/"]')
                
                for link in all_links:
                    if len(commenters) >= self.max_commenters:
                        break
                    
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                    
                    match = USERNAME_PATTERN.match(href)
                    if match:
                        username = match.group(1)
                        if (self._is_valid_username(username) and 
                            username != post_owner and 
                            username not in seen_usernames):
                            seen_usernames.add(username)
                            commenters.append(username)
                            
        except Exception as e:
            print(f"        Comment extraction error: {e}")
        
        return commenters[:self.max_commenters]
    
    async def scrape_post(self, page, post_url: str, hashtag: str) -> list[dict]:
        """Scrape a single post for owner and commenters."""
        results = []
        
        try:
            await page.goto(post_url, wait_until="domcontentloaded")
            
            try:
                await page.wait_for_selector('article', timeout=10000)
            except:
                pass
            
            await human_delay("read_content")
            
            # Extract post owner
            post_owner = await self._extract_post_owner(page)
            
            if post_owner:
                results.append({
                    "username": post_owner,
                    "source": "post_owner",
                    "source_hashtag": hashtag,
                    "target_customer": self.target_customer
                })
                print(f"      Owner: @{post_owner}")
                
                # Extract commenters with scrolling
                print(f"      Scrolling comments...")
                commenters = await self._extract_commenters(page, post_owner)
                
                if commenters:
                    print(f"      Found {len(commenters)} commenters")
                    for commenter in commenters:
                        results.append({
                            "username": commenter,
                            "source": "commenter",
                            "source_hashtag": hashtag,
                            "target_customer": self.target_customer
                        })
                else:
                    print(f"      No commenters found")
            
        except Exception as e:
            print(f"      ERROR: {e}")
        
        return results
    
    async def scrape_hashtag(self, hashtag: str) -> list[dict]:
        """Scrape posts from a hashtag page."""
        users = []
        
        async with async_playwright() as p:
            if session_exists():
                context = await p.chromium.launch_persistent_context(
                    SESSION_DIR,
                    headless=self.headless,
                    viewport={"width": 1280, "height": 720}
                )
                page = context.pages[0] if context.pages else await context.new_page()
                browser = None
            else:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                )
                page = await context.new_page()
            
            url = f"https://www.instagram.com/explore/tags/{hashtag}/"
            print(f"  Visiting #{hashtag}...")
            await page.goto(url, wait_until="domcontentloaded")
            
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass
            
            await human_delay("page_load")
            
            if "login" in page.url.lower():
                print("  WARNING: Redirected to login!")
                await context.close()
                if browser:
                    await browser.close()
                return users
            
            for _ in range(random.randint(1, 2)):
                await page.keyboard.press("PageDown")
                await human_delay("scroll")
            
            await maybe_take_break()
            
            post_links = await page.query_selector_all('a[href*="/p/"]')
            post_urls = []
            
            for link in post_links[:MAX_POSTS_PER_HASHTAG * 2]:
                href = await link.get_attribute("href")
                if href and "/p/" in href:
                    full_url = f"https://www.instagram.com{href}" if href.startswith("/") else href
                    if full_url not in post_urls:
                        post_urls.append(full_url)
                        if len(post_urls) >= MAX_POSTS_PER_HASHTAG:
                            break
            
            print(f"  Found {len(post_urls)} posts")
            
            for i, post_url in enumerate(post_urls):
                if self.collected_count >= MAX_ACCOUNTS_PER_SESSION:
                    break
                
                print(f"    Post {i+1}/{len(post_urls)}...")
                post_results = await self.scrape_post(page, post_url, hashtag)
                
                for result in post_results:
                    if result["username"] not in [u["username"] for u in users]:
                        users.append(result)
                        self.collected_count += 1
                
                await human_delay("between_posts")
                await maybe_take_break()
            
            await context.close()
            if browser:
                await browser.close()
        
        return users
    
    async def run_session(self) -> list[dict]:
        """Run a complete scraping session."""
        all_users = []
        seen = set()
        
        session_hashtags = random.sample(
            self.hashtags,
            min(MAX_HASHTAGS_PER_SESSION, len(self.hashtags))
        )
        
        print(f"\nTarget: {self.config['name']}")
        print(f"Hashtags: {session_hashtags}")
        print(f"Max accounts: {MAX_ACCOUNTS_PER_SESSION}")
        print(f"Max commenters per post: {self.max_commenters}")
        
        for hashtag in session_hashtags:
            if self.collected_count >= MAX_ACCOUNTS_PER_SESSION:
                break
            
            users = await self.scrape_hashtag(hashtag)
            
            for user in users:
                if user["username"] not in seen:
                    seen.add(user["username"])
                    all_users.append(user)
            
            if hashtag != session_hashtags[-1]:
                print("  Waiting before next hashtag...")
                await human_delay("between_hashtags")
        
        return all_users


async def run_scraper(target_customer: str, max_commenters: int = MAX_COMMENTERS_PER_POST) -> list[dict]:
    """Entry point for scraping."""
    scraper = InstagramScraper(
        target_customer=target_customer, 
        headless=False,
        max_commenters=max_commenters
    )
    return await scraper.run_session()
