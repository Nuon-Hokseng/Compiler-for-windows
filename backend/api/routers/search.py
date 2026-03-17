"""
Search & Explore Router
========================
Instagram search automation – search for hashtags or usernames.
Cookies are fetched from Supabase using the user_id.
"""

from fastapi import APIRouter, BackgroundTasks
from api.shared.models import (
    SearchRequest, TaskResponse,
    create_task, update_task, make_log_fn, make_stop_fn, TaskStatus,
)
from api.shared.db import fetch_latest_user_cookies

router = APIRouter(prefix="/search", tags=["Search & Explore"])


def _search_worker(task_id: str, user_id: int, search_term: str,
                   search_type: str, headless: bool, keep_open: bool, browser_type: str):
    log = make_log_fn(task_id)
    stop = make_stop_fn(task_id)
    update_task(task_id, status=TaskStatus.RUNNING)
    log(f"Search – term='{search_term}', type={search_type}, headless={headless}, browser={browser_type}")

    try:
        # Fetch cookies from DB
        row = fetch_latest_user_cookies(user_id)
        if not row or not row.get("cookies"):
            raise RuntimeError(f"No cookies for user_id={user_id}. Call POST /session/save first.")
        cookies = row["cookies"]
        log(f"Loaded {len(cookies)} cookies from DB for user_id={user_id}")

        from browser.search_engine import search_instagram
        search_instagram(
            cookies=cookies,
            search_term=search_term,
            search_type=search_type,
            stop_flag=stop,
            log_callback=log,
            keep_open=keep_open,
            headless=headless,
            browser_type=browser_type,
        )
        update_task(task_id, status=TaskStatus.COMPLETED, message=f"Search for '{search_term}' completed")
    except Exception as e:
        log(f"Error: {e}")
        update_task(task_id, status=TaskStatus.FAILED, message=str(e))


@router.post("/run", response_model=TaskResponse)
async def run_search(req: SearchRequest, bg: BackgroundTasks):
    """
    Open Instagram and perform a human-like search for a hashtag or username.

    The browser types the term character-by-character with random delays,
    then clicks the first matching result. If `keep_open` is true the browser
    stays open until you call `POST /tasks/{task_id}/stop`.
    """
    task = create_task(f"Search – {req.search_term}")
    bg.add_task(
        _search_worker,
        task.task_id, req.user_id, req.search_term,
        req.search_type, req.headless, req.keep_open, req.browser_type,
    )
    return TaskResponse(
        task_id=task.task_id, status="accepted",
        message=f"Search started. Poll /tasks/{task.task_id}",
    )
