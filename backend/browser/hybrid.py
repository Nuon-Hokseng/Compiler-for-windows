from playwright.sync_api import sync_playwright
import time
import random
from browser.search_engine import perform_search
from utils.csv_loader import load_targets_from_csv
from browser.scraper_integration import run_scraper_pipeline_sync
from browser.launcher import (
    BrowserType,
    DEFAULT_BROWSER,
    DEFAULT_HEADLESS,
)
from browser.scrolling import (
    create_log_function,
    create_stop_checker,
    do_single_scroll,
    try_random_like,
    launch_instagram_browser,
    run_infinite_mode
)


def go_back_to_feed(page, log=print):
    log("Returning to main feed...")
    try:
        # natural going back using navigation
        for i in range(3): 
            page.go_back()
            time.sleep(random.uniform(0.5, 1.0))
            
            # Check if we're on the main feed
            current_url = page.url
            if current_url == "https://www.instagram.com/" or current_url == "https://www.instagram.com":
                log("Reached main feed via back navigation")
                break
        
        # Wait for page to stabilize
        try:
            page.wait_for_load_state('networkidle', timeout=3000)
        except:
            pass
        
        time.sleep(random.uniform(1.0, 2.0))
        
        #  try clicking the Home button if navigation didn't work
        current_url = page.url
        if "instagram.com" in current_url and current_url not in ["https://www.instagram.com/", "https://www.instagram.com"]:
            log("Clicking Home button as fallback...")
            try:
                home_selectors = [
                    'a[href="/"]',
                    'xpath=//a[@href="/"]',
                    'xpath=//svg[@aria-label="Home"]/ancestor::a',
                    'xpath=//span[text()="Home"]/ancestor::a',
                ]
                
                for selector in home_selectors:
                    try:
                        home_btn = page.query_selector(selector)
                        if home_btn and home_btn.is_visible():
                            home_btn.click()
                            log("✅ Clicked Home button")
                            time.sleep(random.uniform(1.5, 2.5))
                            break
                    except:
                        continue
            except:
                pass
        
        # activate scrolling
        try:
            page.click('xpath=//main')
        except:
            pass
    # if everything fails, do direct navigation
    except Exception as e:
        log(f"Back navigation failed: {e}, using direct navigation...")
        page.goto("https://www.instagram.com")
        time.sleep(random.uniform(2.0, 3.0))


def scroll_to_top_and_follow(page, username, log=print):
    """Scroll to the top of a profile page and click the Follow button."""
    try:
        log(f"⬆️ Scrolling to top of @{username}'s profile...")
        page.keyboard.press("Home")
        time.sleep(random.uniform(1.0, 2.0))

        # Look for the Follow button (not "Following" or "Requested")
        follow_selectors = [
            'button:has-text("Follow"):not(:has-text("Following")):not(:has-text("Requested"))',
            'xpath=//button[.//div[text()="Follow"] and not(.//div[text()="Following"]) and not(.//div[text()="Requested"])]',
            'xpath=//header//button[contains(text(),"Follow") and not(contains(text(),"Following")) and not(contains(text(),"Requested"))]',
        ]

        for selector in follow_selectors:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    btn_text = btn.inner_text().strip()
                    # Double-check: only click if the text is exactly "Follow"
                    if btn_text == "Follow":
                        time.sleep(random.uniform(0.5, 1.2))
                        btn.click()
                        log(f"✅ Followed @{username}!")
                        time.sleep(random.uniform(1.0, 2.0))
                        return True
            except:
                continue

        log(f"⚠️ Follow button not found for @{username} (may already be following)")
        return False

    except Exception as e:
        log(f"❌ Error following @{username}: {e}")
        return False


def scroll_on_page(page, scroll_count, should_stop, log=print, like_chance=0.10):
    like_count = 0
    
    for i in range(scroll_count):
        if should_stop():
            break
            
        page.press('body', 'PageDown')
        time.sleep(random.uniform(0.8, 1.5))
        
        # Small chance to scroll up 
        if random.uniform(0, 1) < 0.15:
            page.press('body', 'PageUp')
            time.sleep(random.uniform(0.3, 0.6))
            page.press('body', 'PageDown')
            time.sleep(random.uniform(0.3, 0.7))
        
        # Random like based on like_chance
        if random.uniform(0, 1) < like_chance:
            try:
                like_buttons = page.query_selector_all('svg[aria-label="Like"]')
                if like_buttons:
                    random_button = random.choice(like_buttons)
                    try:
                        random_button.click(timeout=200)
                        like_count += 1
                        log("Liked a post!")
                        time.sleep(0.5)
                    except:
                        pass
            except:
                pass
        
        log(f"Profile scroll {i+1}/{scroll_count}")
    
    return like_count


def perform_search_and_explore(page, search_targets, profile_scroll_count, should_stop, log=print):
    if not search_targets or len(search_targets) == 0:
        return False
    
    # Pick a random target
    target = random.choice(search_targets)
    is_hashtag = target.startswith('#')
    search_type = "hashtag" if is_hashtag else "username"
    
    log(f"\n{'='*40}")
    log(f"Searching for: {target}")
    log(f"{'='*40}")
    
    try:
        if not perform_search(page, target, search_type, log):
            log("Search failed, returning to feed...")
            go_back_to_feed(page, log)
            return False
        
        # Wait to load
        time.sleep(random.uniform(2.5, 4.0))
        
        # Scroll on the profile/hashtag page
        scroll_count = random.randint(profile_scroll_count[0], profile_scroll_count[1])
        log(f"Scrolling {scroll_count} times on {search_type} page...")
        like_count = scroll_on_page(page, scroll_count, should_stop, log)
        log(f"Explored {target} - {scroll_count} scrolls, {like_count} likes")
        go_back_to_feed(page, log)
        log("✅ Back on main feed!")
        log(f"{'='*40}\n")
        return True
        
    except Exception as e:
        log(f"⚠️ Error during explore: {e}")
        log("Attempting to return to feed...")
        try:
            go_back_to_feed(page, log)
        except:
            pass
        return False


def run_scroll_session(cookies: list[dict], session_duration, should_stop, log, headless, search_targets, search_chance, profile_scroll_count, browser_type: BrowserType = DEFAULT_BROWSER):
    """Run a single scroll session and return stats."""
    with sync_playwright() as p:
        browser, context, page = launch_instagram_browser(p, cookies, headless, log, browser_type=browser_type)
        
        log(f"Starting combined scroll session ({session_duration}s)...")
        if search_targets:
            log(f"Search targets: {', '.join(search_targets)}")
            log(f"Search chance: {int(search_chance * 100)}%")
        
        start_time = time.time()
        scroll_count = 0
        like_count = 0
        explore_count = 0
        last_explore_time = start_time
        min_time_between_explores = 30
        
        while time.time() - start_time < session_duration and not should_stop():
            scroll_count += 1
            elapsed = round(time.time() - start_time, 1)
            log(f"Scroll #{scroll_count} | {elapsed}s / {session_duration}s | Likes: {like_count} | Explores: {explore_count}")
            
            did_scroll_up = do_single_scroll(page, log)
            if did_scroll_up:
                log("Scrolling up (natural behavior)")
            
            if try_random_like(page, log=log):
                like_count += 1
                log(f"❤️ Liked a post! (Total: {like_count})")
            
            time_since_last_explore = time.time() - last_explore_time
            if (search_targets and 
                len(search_targets) > 0 and 
                time_since_last_explore > min_time_between_explores and
                random.uniform(0, 1) < search_chance):
                
                if perform_search_and_explore(page, search_targets, profile_scroll_count, should_stop, log):
                    explore_count += 1
                    last_explore_time = time.time()
        
        log(f"Session complete: {scroll_count} scrolls, {like_count} likes, {explore_count} explores")
        log("Closing browser...")
        context.close()
        browser.close()
    
    return {'scrolls': scroll_count, 'likes': like_count, 'explores': explore_count}, not should_stop()


def run_combined_scroll(
    cookies: list[dict], 
    duration=60, 
    stop_flag=None, 
    log_callback=None, 
    headless=DEFAULT_HEADLESS, 
    infinite_mode=False,
    search_targets=None,
    search_chance=0.30,
    profile_scroll_count=(3, 8),
    browser_type: BrowserType = DEFAULT_BROWSER,
):
    log = create_log_function(log_callback)
    should_stop = create_stop_checker(stop_flag)
    
    if headless:
        log("Running in headless mode (browser hidden)")
    else:
        log("Running with visible browser")
    
    log(f"Browser: {browser_type}")
    
    if search_targets:
        log(f"Combined Mode: Will randomly explore {len(search_targets)} targets")
    
    if infinite_mode:
        def session_runner(session_duration):
            return run_scroll_session(cookies, session_duration, should_stop, log, headless, search_targets, search_chance, profile_scroll_count, browser_type=browser_type)
        run_infinite_mode(session_runner, should_stop, log)
    else:
        run_scroll_session(cookies, duration, should_stop, log, headless, search_targets, search_chance, profile_scroll_count, browser_type=browser_type)
    
    log("✅ Done!")


def run_csv_profile_visit(
    cookies: list[dict],
    csv_path,
    stop_flag=None,
    log_callback=None,
    headless=DEFAULT_HEADLESS,
    scroll_count_range=(3, 8),
    delay_between_profiles=(5, 15),
    like_chance=0.10,
    browser_type: BrowserType = DEFAULT_BROWSER,
):
    log = create_log_function(log_callback)
    should_stop = create_stop_checker(stop_flag)
    
    # Load targets from CSV
    csv_data = load_targets_from_csv(csv_path, log)
    if not csv_data:
        log("❌ Failed to load CSV file. Aborting.")
        return
    
    targets = csv_data['targets']
    target_type = csv_data['type']
    total_count = csv_data['count']
    
    log(f"\n{'='*50}")
    log(f" CSV PROFILE VISIT MODE")
    log(f"{'='*50}")
    log(f"CSV File: {csv_path}")
    log(f"Type: {target_type}")
    log(f"Total targets: {total_count}")
    log(f"Scrolls per profile: {scroll_count_range[0]}-{scroll_count_range[1]}")
    log(f"Delay between profiles: {delay_between_profiles[0]}-{delay_between_profiles[1]}s")
    log(f"{'='*50}\n")
    
    if headless:
        log("Running in headless mode (browser hidden)")
    else:
        log("Running with visible browser")
    
    # Stats tracking
    visited_count = 0
    total_likes = 0
    total_scrolls = 0
    failed_visits = []
    
    with sync_playwright() as p:
        browser, context, page = launch_instagram_browser(p, cookies, headless, log, browser_type=browser_type)
        
        time.sleep(random.uniform(1.0, 2.0))
        
        # Visit each target one by one
        for index, target in enumerate(targets, 1):
            if should_stop():
                log("🛑 Stop requested. Ending profile visits...")
                break
            
            log(f"\n{'='*40}")
            log(f" VISITING {index}/{total_count}: {target}")
            log(f"{'='*40}")
            
            try:
                # Perform search for this target
                search_type = "hashtag" if target_type == "hashtag" else "username"
                
                if not perform_search(page, target, search_type, log):
                    log(f"⚠️ Failed to find: {target}")
                    failed_visits.append(target)
                    continue
                
                # Wait for profile/hashtag page to load
                time.sleep(random.uniform(2.5, 4.0))
                visited_count += 1
                
                # Scroll on the profile/hashtag page
                scroll_count = random.randint(scroll_count_range[0], scroll_count_range[1])
                log(f" Scrolling {scroll_count} times on {target}...")
                
                like_count = scroll_on_page(page, scroll_count, should_stop, log, like_chance)
                total_likes += like_count
                total_scrolls += scroll_count
                
                log(f" Visited {target} - {scroll_count} scrolls, {like_count} likes")
                
                # Return to main feed
                go_back_to_feed(page, log)
                
                # Delay before next profile visit for better simulation
                if index < total_count and not should_stop():
                    delay = random.uniform(delay_between_profiles[0], delay_between_profiles[1])
                    log(f" Waiting {delay:.1f}s before next profile...")
                    time.sleep(delay)
                
            except Exception as e:
                log(f"❌ Error visiting {target}: {e}")
                failed_visits.append(target)
                # Try to recover by going back to feed
                try:
                    go_back_to_feed(page, log)
                except:
                    pass
        
        log("Closing browser...")
        context.close()
        browser.close()
    
    # Final summary
    log(f"\n{'='*50}")
    log(f"CSV VISIT SUMMARY")
    log(f"{'='*50}")
    log(f"✅ Successfully visited: {visited_count}/{total_count}")
    log(f"Total scrolls: {total_scrolls}")
    log(f"Total likes: {total_likes}")
    if failed_visits:
        log(f"Failed visits ({len(failed_visits)}): {', '.join(failed_visits)}")
    log(f"{'='*50}")
    log("✅ Done!")


def run_scraper_scroll_session(cookies: list[dict], session_duration, should_stop, log, headless,
                               target_customer, scraper_chance=0.20, model="llama3:8b",
                               search_targets=None, search_chance=0.30,
                               profile_scroll_count=(3, 8),
                               max_scraped_accounts=30,
                               browser_type: BrowserType = DEFAULT_BROWSER):
    """
    Run a scroll session with 20% chance to trigger the scraper pipeline.
    Scraper only fires while we have < max_scraped_accounts usernames collected.
    Once enough accounts are found, the scraper stops and the session spends
    its time visiting those profiles one-by-one between normal scrolls.
    """
    with sync_playwright() as p:
        browser, context, page = launch_instagram_browser(p, cookies, headless, log, browser_type=browser_type)

        log(f"Starting scraper-enabled scroll session ({session_duration}s)...")
        log(f"🔬 Scraper chance: {int(scraper_chance * 100)}% | Target: {target_customer}")
        log(f"📊 Will collect up to {max_scraped_accounts} accounts before stopping scraper")
        if search_targets:
            log(f"🔀 Also has {len(search_targets)} search targets ({int(search_chance * 100)}% chance)")

        start_time = time.time()
        scroll_count = 0
        like_count = 0
        explore_count = 0
        scraper_runs = 0
        profiles_visited = 0
        last_explore_time = start_time
        last_scraper_time = start_time
        last_visit_time = start_time
        min_time_between_explores = 30
        min_time_between_scraper = 120  # At least 2 min between scraper runs
        min_time_between_visits = 30   # At least 30s between profile visits

        # Persistent state across scraper runs
        scraped_usernames: list[str] = []
        visited_posts: set[str] = set()  # Post URLs already scraped (never re-scan)
        visit_index = 0  # Tracks which username to visit next

        while time.time() - start_time < session_duration and not should_stop():
            scroll_count += 1
            elapsed = round(time.time() - start_time, 1)
            remaining_visits = len(scraped_usernames) - visit_index
            log(f"📜 Scroll #{scroll_count} | ⏱️ {elapsed}s / {session_duration}s | "
                f"❤️ {like_count} | 📋 {len(scraped_usernames)} scraped | "
                f"👤 {profiles_visited} visited | 📝 {remaining_visits} queued")

            # Perform scroll
            did_scroll_up = do_single_scroll(page, log)
            if did_scroll_up:
                log("⬆️ Scrolling up (natural behavior)")

            # Try random like
            if try_random_like(page, log=log):
                like_count += 1
                log(f"❤️ Liked a post! (Total: {like_count})")

            # === 20% CHANCE: TRIGGER SCRAPER (only if < 30 accounts collected) ===
            time_since_last_scraper = time.time() - last_scraper_time
            if (len(scraped_usernames) < max_scraped_accounts and
                    time_since_last_scraper > min_time_between_scraper and
                    random.random() < scraper_chance):

                log(f"\n🔬 SCRAPER TRIGGERED! ({len(scraped_usernames)}/{max_scraped_accounts} accounts so far)")
                scraper_runs += 1
                last_scraper_time = time.time()

                # Run the scraper pipeline on the SAME page
                # visited_posts is shared across runs — already-scraped posts are skipped
                new_usernames = run_scraper_pipeline_sync(
                    page=page,
                    target_customer=target_customer,
                    model=model,
                    log=log,
                    visited_posts=visited_posts
                )

                # Navigate back to the main feed after scraping
                go_back_to_feed(page, log)

                if new_usernames:
                    # Add only new unique usernames, respecting the cap
                    existing = set(scraped_usernames)
                    added = 0
                    for uname in new_usernames:
                        if len(scraped_usernames) >= max_scraped_accounts:
                            break
                        if uname not in existing:
                            scraped_usernames.append(uname)
                            existing.add(uname)
                            added += 1

                    log(f"✅ Added {added} new usernames (total: {len(scraped_usernames)}/{max_scraped_accounts})")

                    if len(scraped_usernames) >= max_scraped_accounts:
                        log(f"🎯 Reached {max_scraped_accounts} accounts! Scraper will no longer trigger.")
                else:
                    log("⚠️ Scraper pipeline returned no usernames, continuing scroll...")

                log("▶️ Resuming scroll session...\n")

            # === VISIT NEXT PROFILE from scraped list (one at a time between scrolls) ===
            time_since_last_visit = time.time() - last_visit_time
            if (visit_index < len(scraped_usernames) and
                    time_since_last_visit > min_time_between_visits and
                    random.random() < 0.30):

                username = scraped_usernames[visit_index]
                visit_index += 1
                remaining = len(scraped_usernames) - visit_index

                log(f"\n{'='*40}")
                log(f"👤 VISITING @{username} ({visit_index}/{len(scraped_usernames)}, {remaining} remaining)")
                log(f"{'='*40}")

                try:
                    if not perform_search(page, username, "username", log):
                        log(f"⚠️ Could not find @{username}, skipping...")
                    else:
                        time.sleep(random.uniform(2.5, 4.0))
                        profiles_visited += 1

                        # Scroll on profile page
                        num_scrolls = random.randint(profile_scroll_count[0], profile_scroll_count[1])
                        log(f"📜 Scrolling {num_scrolls} times on @{username}'s profile...")
                        visit_likes = scroll_on_page(page, num_scrolls, should_stop, log, like_chance=0.10)
                        like_count += visit_likes

                        # Scroll to top and follow
                        scroll_to_top_and_follow(page, username, log)

                        log(f"✅ Visited @{username} - {num_scrolls} scrolls, {visit_likes} likes")

                except Exception as e:
                    log(f"❌ Error visiting @{username}: {e}")

                try:
                    go_back_to_feed(page, log)
                except:
                    pass

                last_visit_time = time.time()

                # Delay before resuming scrolls
                delay = random.uniform(5, 15)
                log(f"⏳ Waiting {delay:.1f}s before resuming scroll...")
                time.sleep(delay)

            # === REGULAR SEARCH/EXPLORE (existing combined mode logic) ===
            time_since_last_explore = time.time() - last_explore_time
            if (search_targets and
                    len(search_targets) > 0 and
                    time_since_last_explore > min_time_between_explores and
                    random.random() < search_chance):

                if perform_search_and_explore(page, search_targets, profile_scroll_count, should_stop, log):
                    explore_count += 1
                    last_explore_time = time.time()

        # End-of-session summary
        remaining = len(scraped_usernames) - visit_index
        log(f"\nSession complete: {scroll_count} scrolls, {like_count} likes, "
            f"{explore_count} explores, {scraper_runs} scraper runs, "
            f"{profiles_visited} profiles visited, {remaining} still queued")
        log("Closing browser...")
        context.close()
        browser.close()

    return {
        'scrolls': scroll_count,
        'likes': like_count,
        'explores': explore_count,
        'scraper_runs': scraper_runs,
        'profiles_visited': profiles_visited
    }, not should_stop()


def run_combined_scroll_with_scraper(
    cookies: list[dict],
    duration=60,
    stop_flag=None,
    log_callback=None,
    headless=DEFAULT_HEADLESS,
    infinite_mode=False,
    target_customer="car",
    scraper_chance=0.20,
    model="llama3:8b",
    search_targets=None,
    search_chance=0.30,
    profile_scroll_count=(3, 8),
    browser_type: BrowserType = DEFAULT_BROWSER,
):
    """
    Combined scroll mode with scraper integration.
    While scrolling, there's a 20% chance to trigger the scraper pipeline.
    When triggered: scrape -> ollama analysis -> CSV export -> auto-visit profiles.
    """
    log = create_log_function(log_callback)
    should_stop = create_stop_checker(stop_flag)

    if headless:
        log("Running in headless mode (browser hidden)")
    else:
        log("Running with visible browser")

    log(f"Browser: {browser_type}")
    log(f"🔬 Scraper Mode: {int(scraper_chance * 100)}% chance during scrolling")
    log(f"🎯 Target customer: {target_customer}")
    if search_targets:
        log(f"🔀 Combined Mode: Will also randomly explore {len(search_targets)} targets")

    if infinite_mode:
        def session_runner(session_duration):
            return run_scraper_scroll_session(
                cookies, session_duration, should_stop, log, headless,
                target_customer, scraper_chance, model,
                search_targets, search_chance, profile_scroll_count,
                browser_type=browser_type,
            )
        run_infinite_mode(session_runner, should_stop, log)
    else:
        run_scraper_scroll_session(
            cookies, duration, should_stop, log, headless,
            target_customer, scraper_chance, model,
            search_targets, search_chance, profile_scroll_count,
            browser_type=browser_type,
        )

    log("✅ Done!")
