from playwright.sync_api import sync_playwright
import time
import random
from browser.launcher import (
    launch_with_cookies,
    dismiss_notification_popup,
    BrowserType,
    DEFAULT_BROWSER,
    DEFAULT_HEADLESS,
)

def create_log_function(log_callback):
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)
    return log

def human_mouse_move(page, element):
    # Get element bounding box
    box = element.bounding_box()
    if box:
        # Add slight randomness to target position (not exact center)
        target_x = box['x'] + box['width'] / 2 + random.uniform(-5, 5)
        target_y = box['y'] + box['height'] / 2 + random.uniform(-3, 3)
        
        # Move mouse with slight delay to simulate natural movement
        page.mouse.move(target_x, target_y, steps=random.randint(5, 15))
        time.sleep(random.uniform(0.1, 0.3))
      
def create_stop_checker(stop_flag):

    def should_stop():
        if stop_flag and callable(stop_flag):
            return stop_flag()
        return False
    return should_stop


def do_single_scroll(page, log=print, scroll_up_chance=0.30):
    try:
        page.keyboard.press('PageDown')
    except Exception as e:
        log(f"⚠️ Scroll failed, retrying with JS fallback: {e}")
        try:
            page.evaluate("window.scrollBy(0, window.innerHeight)")
        except Exception:
            pass
    pause_time = random.uniform(0.8, 1.5)
    page.wait_for_timeout(int(pause_time * 1000))
    
    # Chance to scroll up for natural behavior
    did_scroll_up = False
    if random.uniform(0, 1) < scroll_up_chance:
        try:
            page.keyboard.press('PageUp')
        except Exception:
            pass
        time.sleep(random.uniform(0.5, 1.0))
        try:
            page.keyboard.press('PageDown')
        except Exception:
            pass
        time.sleep(random.uniform(0.3, 0.7))
        did_scroll_up = True
    
    return did_scroll_up


def try_random_like(page, like_chance_range=(0.10, 0.15), log=print):

    if random.uniform(0, 1) < random.uniform(like_chance_range[0], like_chance_range[1]):
        try:
            like_buttons = page.query_selector_all('svg[aria-label="Like"]')
            if like_buttons:
                random_button = random.choice(like_buttons)
                try:
                    random_button.click(timeout=200)
                    time.sleep(0.5)
                    return True
                except:
                    pass
        except:
            pass
    return False


def launch_instagram_browser(playwright, cookies: list[dict], headless=DEFAULT_HEADLESS, log=print, browser_type: BrowserType = DEFAULT_BROWSER):
    log(f"🚀 Launching {browser_type} browser (headless={headless})...")
    
    browser, context, page = launch_with_cookies(
        playwright,
        cookies,
        browser_type=browser_type,
        headless=headless,
    )
    
    log("✅ Browser launched successfully")
    log("✅ Instagram loaded")
    
    time.sleep(2)
    
    # Click on feed area to activate scrolling
    try:
        page.click('xpath=//main')
        log("📱 Feed area activated")
    except:
        pass
    
    return browser, context, page


def run_timed_scroll_loop(page, duration, should_stop, log=print, on_scroll_callback=None):
    start_time = time.time()
    scroll_count = 0
    like_count = 0
    
    while time.time() - start_time < duration and not should_stop():
        scroll_count += 1
        elapsed = round(time.time() - start_time, 1)
        
        # explore for extra actions
        extra_explores = 0
        if on_scroll_callback:
            continue_loop, extra_likes, extra_explores = on_scroll_callback(scroll_count, like_count, elapsed)
            like_count += extra_likes
            if not continue_loop:
                break
        
        log(f"📜Scroll #{scroll_count} | ⏱️ {elapsed}s / {duration}s | ❤️ {like_count}" + 
            (f" | {extra_explores}" if extra_explores else ""))
        
        # Perform scroll
        did_scroll_up = do_single_scroll(page, log)
        if did_scroll_up:
            log("⬆️ Scrolling up (natural behavior)")
        
        # Try random like
        if try_random_like(page, log=log):
            like_count += 1
            log(f"❤️ Liked a post! (Total: {like_count})")
    
    return scroll_count, like_count


def run_infinite_mode(run_session_func, should_stop, log=print, 
                      active_range=(1800, 3600), rest_range=(600, 1200)):
    total_stats = {'scrolls': 0, 'likes': 0, 'explores': 0, 'sessions': 0}
    
    log("INFINITE MODE enabled ")
    log(f"⏰ Active: {active_range[0]//60}-{active_range[1]//60} min | Rest: {rest_range[0]//60}-{rest_range[1]//60} min")
    
    while not should_stop():
        total_stats['sessions'] += 1
        session_number = total_stats['sessions']
        
        # Random active duration
        active_duration = random.randint(active_range[0], active_range[1])
        active_mins = round(active_duration / 60, 1)
        
        log(f"\n{'='*40}")
        log(f"SESSION #{session_number} starting")
        log(f"Planned active time: {active_mins} minutes")
        log(f"{'='*40}")
        
        # Run the scroll session
        session_stats, should_continue = run_session_func(active_duration)
        
        # Accumulate stats
        total_stats['scrolls'] += session_stats.get('scrolls', 0)
        total_stats['likes'] += session_stats.get('likes', 0)
        total_stats['explores'] += session_stats.get('explores', 0)
        
        if not should_continue or should_stop():
            break
        
        # Random rest duration
        rest_duration = random.randint(rest_range[0], rest_range[1])
        rest_mins = round(rest_duration / 60, 1)
        
        log(f"\n{'='*40}")
        log(f"REST TIME - Taking a break for {rest_mins} minutes")
        log(f"💤 Browser closed, script still running...")
        log(f"{'='*40}")
        
        # Rest period
        rest_start = time.time()
        while time.time() - rest_start < rest_duration and not should_stop():
            remaining = round((rest_duration - (time.time() - rest_start)) / 60, 1)
            log(f"😴 Resting... {remaining} min remaining")
            time.sleep(30)
        
        if should_stop():
            break
        
        log(f"⏰ Rest complete! Waking up...")
    
    log(f"\n{'='*40}")
    log(f"INFINITE MODE ended")
    log(f"Total: {total_stats['sessions']} sessions, {total_stats['scrolls']} scrolls, "
        f"{total_stats['likes']} likes, {total_stats['explores']} explores")
    log(f"{'='*40}")
    
    return total_stats

def run_instagram_scroll(cookies: list[dict], duration=60, stop_flag=None, log_callback=None, headless=DEFAULT_HEADLESS, infinite_mode=False, on_scroll_callback=None, browser_type: BrowserType = DEFAULT_BROWSER):
    log = create_log_function(log_callback)
    should_stop = create_stop_checker(stop_flag)
    
    # Track total stats across sessions
    total_scrolls = 0
    total_likes = 0
    
    def run_scroll_session(session_duration):
        nonlocal total_scrolls, total_likes
        
        with sync_playwright() as p:
            browser, context, page = launch_instagram_browser(p, cookies, headless, log, browser_type=browser_type)
            
            log(f"Starting scroll session ({session_duration}s)...")
            scroll_count, like_count = run_timed_scroll_loop(
                page, session_duration, should_stop, log, on_scroll_callback=on_scroll_callback
            )
            
            total_scrolls += scroll_count
            total_likes += like_count
            log(f"Session complete: {scroll_count} scrolls, {like_count} likes")
            log("Closing browser...")
            context.close()
            browser.close()
        
        return {'scrolls': scroll_count, 'likes': like_count, 'explores': 0}, not should_stop()
    
    # Status updates
    if headless:
        log("Running in headless mode (browser hidden)")
    else:
        log("Running with visible browser")
    
    if infinite_mode:
        run_infinite_mode(run_scroll_session, should_stop, log)
    else:
        run_scroll_session(duration)
    
    log("✅ Done!")
