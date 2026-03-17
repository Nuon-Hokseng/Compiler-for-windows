"""
Scrolling Automation Router
============================
Four automation modes, all run as background tasks:
  1. Basic timed scroll
  2. Combined scroll + search/explore
  3. Combined scroll + scraper pipeline + profile visits
  4. CSV-based profile visiting

All modes require a ``user_id`` — cookies are fetched from Supabase
so no local browser profile is needed.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from api.shared.models import (
    ScrollRequest, CombinedScrollRequest, ScraperScrollRequest,
    CSVProfileVisitRequest, TaskResponse,
    create_task, update_task, make_log_fn, make_stop_fn, TaskStatus,
)
from api.shared.db import fetch_latest_user_cookies

router = APIRouter(prefix="/scrolling", tags=["Scrolling Automation"])


def _get_cookies_or_fail(user_id: int, log) -> list[dict]:
    """Fetch cookies from DB. Raises if none found."""
    row = fetch_latest_user_cookies(user_id)
    if not row or not row.get("cookies"):
        raise RuntimeError(f"No Instagram cookies found for user_id={user_id}. Call POST /session/save first.")
    cookies = row["cookies"]
    log(f"Loaded {len(cookies)} cookies from database for user_id={user_id}")
    return cookies


# ── Workers ──────────────────────────────────────────────────────────

def _basic_scroll_worker(task_id: str, user_id: int, duration: int,
                         headless: bool, infinite_mode: bool, browser_type: str):
    log = make_log_fn(task_id)
    stop = make_stop_fn(task_id)
    update_task(task_id, status=TaskStatus.RUNNING)
    log(f"Basic scroll – duration={duration}s, headless={headless}, infinite={infinite_mode}, browser={browser_type}")

    try:
        cookies = _get_cookies_or_fail(user_id, log)
        from browser.scrolling import run_instagram_scroll
        run_instagram_scroll(
            cookies=cookies,
            duration=duration,
            stop_flag=stop,
            log_callback=log,
            headless=headless,
            infinite_mode=infinite_mode,
            browser_type=browser_type,
        )
        update_task(task_id, status=TaskStatus.COMPLETED, message="Scroll session finished")
    except Exception as e:
        log(f"Error: {e}")
        update_task(task_id, status=TaskStatus.FAILED, message=str(e))


def _combined_scroll_worker(task_id: str, user_id: int, duration: int,
                            headless: bool, infinite_mode: bool,
                            search_targets: list[str] | None, search_chance: float,
                            profile_scroll_min: int, profile_scroll_max: int,
                            browser_type: str):
    log = make_log_fn(task_id)
    stop = make_stop_fn(task_id)
    update_task(task_id, status=TaskStatus.RUNNING)
    log(f"Combined scroll – targets={search_targets}, chance={search_chance}, browser={browser_type}")

    try:
        cookies = _get_cookies_or_fail(user_id, log)
        from browser.hybrid import run_combined_scroll
        run_combined_scroll(
            cookies=cookies,
            duration=duration,
            stop_flag=stop,
            log_callback=log,
            headless=headless,
            infinite_mode=infinite_mode,
            search_targets=search_targets,
            search_chance=search_chance,
            profile_scroll_count=(profile_scroll_min, profile_scroll_max),
            browser_type=browser_type,
        )
        update_task(task_id, status=TaskStatus.COMPLETED, message="Combined scroll finished")
    except Exception as e:
        log(f"Error: {e}")
        update_task(task_id, status=TaskStatus.FAILED, message=str(e))


def _scraper_scroll_worker(task_id: str, user_id: int, duration: int,
                           headless: bool, infinite_mode: bool,
                           target_customer: str, scraper_chance: float,
                           model: str, search_targets: list[str] | None,
                           search_chance: float,
                           profile_scroll_min: int, profile_scroll_max: int,
                           browser_type: str):
    log = make_log_fn(task_id)
    stop = make_stop_fn(task_id)
    update_task(task_id, status=TaskStatus.RUNNING)
    log(f"Scraper-scroll – target={target_customer}, scraper_chance={scraper_chance}, browser={browser_type}")

    try:
        cookies = _get_cookies_or_fail(user_id, log)
        from browser.hybrid import run_combined_scroll_with_scraper
        run_combined_scroll_with_scraper(
            cookies=cookies,
            duration=duration,
            stop_flag=stop,
            log_callback=log,
            headless=headless,
            infinite_mode=infinite_mode,
            target_customer=target_customer,
            scraper_chance=scraper_chance,
            model=model,
            search_targets=search_targets,
            search_chance=search_chance,
            profile_scroll_count=(profile_scroll_min, profile_scroll_max),
            browser_type=browser_type,
        )
        update_task(task_id, status=TaskStatus.COMPLETED, message="Scraper-scroll session finished")
    except Exception as e:
        log(f"Error: {e}")
        update_task(task_id, status=TaskStatus.FAILED, message=str(e))


def _csv_visit_worker(task_id: str, user_id: int, csv_path: str,
                      headless: bool, scroll_min: int, scroll_max: int,
                      delay_min: int, delay_max: int, like_chance: float,
                      browser_type: str):
    log = make_log_fn(task_id)
    stop = make_stop_fn(task_id)
    update_task(task_id, status=TaskStatus.RUNNING)
    log(f"CSV profile visit – csv={csv_path}, browser={browser_type}")

    try:
        cookies = _get_cookies_or_fail(user_id, log)
        from browser.hybrid import run_csv_profile_visit
        run_csv_profile_visit(
            cookies=cookies,
            csv_path=csv_path,
            stop_flag=stop,
            log_callback=log,
            headless=headless,
            scroll_count_range=(scroll_min, scroll_max),
            delay_between_profiles=(delay_min, delay_max),
            like_chance=like_chance,
            browser_type=browser_type,
        )
        update_task(task_id, status=TaskStatus.COMPLETED, message="CSV visit session finished")
    except Exception as e:
        log(f"Error: {e}")
        update_task(task_id, status=TaskStatus.FAILED, message=str(e))


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/basic", response_model=TaskResponse)
async def start_basic_scroll(req: ScrollRequest, bg: BackgroundTasks):
    """
    Start a basic Instagram feed scrolling session.
    Scrolls the main feed for `duration` seconds, randomly liking posts.
    Supports infinite mode (alternating active/rest cycles).
    Stop anytime via `POST /tasks/{task_id}/stop`.
    """
    task = create_task("Basic scroll")
    bg.add_task(
        _basic_scroll_worker,
        task.task_id, req.user_id, req.duration,
        req.headless, req.infinite_mode, req.browser_type,
    )
    return TaskResponse(
        task_id=task.task_id, status="accepted",
        message=f"Scroll started. Poll /tasks/{task.task_id}",
    )


@router.post("/combined", response_model=TaskResponse)
async def start_combined_scroll(req: CombinedScrollRequest, bg: BackgroundTasks):
    """
    Scroll the feed **and** randomly visit search targets (hashtags or usernames).
    While scrolling, there's a configurable chance to break away, search for a
    target, explore it, then return to the feed.
    """
    task = create_task("Combined scroll + explore")
    bg.add_task(
        _combined_scroll_worker,
        task.task_id, req.user_id, req.duration,
        req.headless, req.infinite_mode,
        req.search_targets, req.search_chance,
        req.profile_scroll_count_min, req.profile_scroll_count_max,
        req.browser_type,
    )
    return TaskResponse(
        task_id=task.task_id, status="accepted",
        message=f"Combined scroll started. Poll /tasks/{task.task_id}",
    )


@router.post("/scraper", response_model=TaskResponse)
async def start_scraper_scroll(req: ScraperScrollRequest, bg: BackgroundTasks):
    """
    The most advanced mode: scrolling + scraper pipeline + auto-visit.

    While scrolling:
    1. Random chance to trigger the **scraper pipeline** (hashtag → post owners/commenters → Ollama → CSV)
    2. Collected usernames are visited one-by-one between scrolls
    3. Optionally also explores extra search targets
    """
    task = create_task(f"Scraper-scroll – {req.target_customer}")
    bg.add_task(
        _scraper_scroll_worker,
        task.task_id, req.user_id, req.duration,
        req.headless, req.infinite_mode,
        req.target_customer, req.scraper_chance,
        req.model, req.search_targets, req.search_chance,
        req.profile_scroll_count_min, req.profile_scroll_count_max,
        req.browser_type,
    )
    return TaskResponse(
        task_id=task.task_id, status="accepted",
        message=f"Scraper-scroll started. Poll /tasks/{task.task_id}",
    )


@router.post("/csv-visit", response_model=TaskResponse)
async def start_csv_profile_visit(req: CSVProfileVisitRequest, bg: BackgroundTasks):
    """
    Visit profiles listed in a CSV file one-by-one.
    For each profile: search → navigate → scroll → optionally like → return to feed.
    Useful after exporting analyzed accounts from the scraper pipeline.
    """
    task = create_task(f"CSV visit – {req.csv_path}")
    bg.add_task(
        _csv_visit_worker,
        task.task_id, req.user_id, req.csv_path,
        req.headless, req.scroll_count_min, req.scroll_count_max,
        req.delay_min, req.delay_max, req.like_chance,
        req.browser_type,
    )
    return TaskResponse(
        task_id=task.task_id, status="accepted",
        message=f"CSV visit started. Poll /tasks/{task.task_id}",
    )
