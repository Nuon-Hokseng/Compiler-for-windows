"""
Account & Session Router
========================
Authentication (signup / login) for the web app.
Instagram browser sessions: open headful browser → user logs in → cookies
are exported and stored in the Supabase ``user_cookies`` table.
"""

import asyncio
from functools import partial
from fastapi import APIRouter, BackgroundTasks, HTTPException
from api.shared.models import (
    SignupRequest, LoginRequest, LoginResponse,
    SessionRequest, TaskResponse,
    create_task, update_task, make_log_fn, TaskStatus,
)
from api.shared.db import (
    signup_user,
    login_user,
    get_user_by_id,
    insert_new_user_cookies,
    upsert_user_cookies,
    fetch_all_user_cookies,
    fetch_latest_user_cookies,
    delete_user_cookies,
)

router = APIRouter(prefix="/session", tags=["Account & Session"])


# ── Web-app authentication ──────────────────────────────────────────

@router.post("/signup")
async def signup(req: SignupRequest):
    """
    Create a new web-app account.
    Stores username + hashed password in the ``authentication`` table.
    """
    try:
        user = signup_user(req.username, req.password)
        return {
            "user_id": user["id"],
            "username": user["username"],
            "message": "Account created successfully",
        }
    except Exception as e:
        detail = str(e)
        if "duplicate" in detail.lower() or "unique" in detail.lower() or "409" in detail:
            raise HTTPException(status_code=409, detail="Username already exists")
        raise HTTPException(status_code=500, detail=detail)


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """
    Authenticate against the ``authentication`` table.
    Returns the ``user_id`` on success (use it for all subsequent calls).
    """
    user = login_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return LoginResponse(user_id=user["id"], username=user["username"])


# ── Instagram session (cookie export) ───────────────────────────────

async def _save_session_worker(
    task_id: str,
    user_id: int,
    timeout: int,
    browser_type: str,
):
    """Background worker – opens a headful browser for manual IG login,
    exports cookies and upserts them into Supabase."""
    log = make_log_fn(task_id)
    update_task(task_id, status=TaskStatus.RUNNING)
    log(f"Launching {browser_type} for IG login (timeout={timeout}s)")

    try:
        from browser.session import open_login_and_export_cookies

        cookies, instagram_username = await open_login_and_export_cookies(
            timeout=timeout,
            browser_type=browser_type,
        )
        log(f"Extracted {len(cookies)} cookies from browser")
        if instagram_username:
            log(f"Detected Instagram username: {instagram_username}")

        if not cookies:
            log("WARNING: No cookies extracted – did you log in?")
            update_task(task_id, status=TaskStatus.FAILED, message="No cookies extracted")
            return

        # Insert a NEW cookie row (each login creates a separate snapshot)
        # Run sync Supabase call in a thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        row = await loop.run_in_executor(
            None,
            partial(insert_new_user_cookies, user_id, cookies, instagram_username),
        )
        cookie_row_id = row.get("id", "?")
        log(f"Cookies stored in Supabase (row id={cookie_row_id}) for user_id={user_id}")

        update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            message=f"Instagram cookies saved – row id={cookie_row_id}",
            result={"cookie_row_id": cookie_row_id, "cookie_count": len(cookies)},
        )

    except Exception as e:
        log(f"Error: {e}")
        update_task(task_id, status=TaskStatus.FAILED, message=str(e))


@router.post("/save", response_model=TaskResponse)
async def save_session(req: SessionRequest, bg: BackgroundTasks):
    """
    Open a **headful** browser pointed at the Instagram login page.
    The user logs in manually; the browser **closes immediately** once
    login is detected (``ds_user`` cookie appears).  If the user hasn't
    logged in within ``timeout`` seconds, the browser closes anyway.

    Each call creates a **new** cookie snapshot – one user can have
    multiple stored sessions (use ``GET /session/cookies/{user_id}?latest=false``
    to see all of them).

    **Flow:**
    1. ``POST /session/signup`` or ``/session/login`` to get a ``user_id``
    2. ``POST /session/save`` with that ``user_id`` → browser opens
    3. Log in to Instagram in the browser window
    4. Browser closes immediately after login is detected
    5. All other endpoints (scroll, scrape, search) now work
    """
    # Validate user exists
    user = get_user_by_id(req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User id {req.user_id} not found in authentication table")

    task = create_task(f"IG login → user {req.user_id} ({user['username']})")
    bg.add_task(
        _save_session_worker,
        task.task_id,
        req.user_id,
        req.timeout,
        req.browser_type,
    )
    return TaskResponse(
        task_id=task.task_id,
        status="accepted",
        message=f"Browser opening for IG login. Poll /tasks/{task.task_id} for progress.",
    )


# ── Cookie retrieval endpoints ──────────────────────────────────────

@router.get("/cookies/{user_id}")
async def get_cookies(user_id: int, latest: bool = True):
    """
    Fetch stored Instagram cookies for a user.
    - ``latest=true`` (default): returns the most recent cookie set.
    - ``latest=false``: returns ALL cookie snapshots.
    """
    try:
        if latest:
            row = fetch_latest_user_cookies(user_id)
            if not row:
                raise HTTPException(status_code=404, detail="No cookies found for this user")
            return {"user_id": user_id, "cookies": row}
        else:
            rows = fetch_all_user_cookies(user_id)
            # Return empty list instead of 404 for collection queries
            if not rows:
                return {"user_id": user_id, "count": 0, "cookies": []}
            return {"user_id": user_id, "count": len(rows), "cookies": rows}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cookies/{cookie_id}")
async def remove_cookie(cookie_id: int):
    """Delete a specific cookie snapshot by its row id."""
    try:
        deleted = delete_user_cookies(cookie_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Cookie row not found")
        return {"deleted": True, "cookie_id": cookie_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _extract_instagram_username_from_cookies(cookies: list[dict] | None) -> str | None:
    """
    Fallback: extract Instagram identifier from stored cookies.
    Checks for 'ds_user_id' cookie (numeric IG user ID).
    """
    if not cookies or not isinstance(cookies, list):
        return None
    for c in cookies:
        if isinstance(c, dict) and c.get("name") in ("ds_user", "ds_user_id"):
            val = c.get("value")
            if val and isinstance(val, str) and val.strip():
                return val.strip()
    return None


@router.get("/check/{user_id}")
async def check_session(user_id: int):
    """Check whether a user has stored Instagram cookies (i.e. an active session)."""
    row = fetch_latest_user_cookies(user_id)
    has_cookies = bool(row and row.get("cookies"))
    instagram_username = None
    if has_cookies and row:
        # Primary: read from the dedicated column (set at save time)
        instagram_username = row.get("instagram_username")
        # Fallback: try to extract from cookie data
        if not instagram_username:
            instagram_username = _extract_instagram_username_from_cookies(row.get("cookies"))
    return {
        "user_id": user_id,
        "has_cookies": has_cookies,
        "instagram_username": instagram_username,
        "message": "Cookies ready" if has_cookies else "No cookies – call POST /session/save first",
    }

