"""Supabase client helpers for authentication and cookie storage."""

from __future__ import annotations

import os
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any
from supabase import create_client, Client

_client: Client | None = None


def get_supabase() -> Client:
    """Return a singleton Supabase client."""
    global _client
    if _client is None:
        url = os.getenv("URL")
        key = os.getenv("ANNON")
        if not url or not key:
            raise RuntimeError("URL and ANNON must be set in .env")
        _client = create_client(url, key)
    return _client


# ── Password helpers ────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """Hash a password with a random salt using SHA-256."""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its stored hash."""
    if ":" not in password_hash:
        return False
    salt, stored_hash = password_hash.split(":", 1)
    computed = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return secrets.compare_digest(computed, stored_hash)


# ── Authentication CRUD ─────────────────────────────────────────────

def signup_user(username: str, password: str) -> dict:
    """
    Create a new user in the ``authentication`` table.
    Returns the inserted row.  Raises on duplicate username (Supabase
    will return a 409 because of the UNIQUE constraint).
    """
    sb = get_supabase()
    result = (
        sb.table("authentication")
        .insert({"username": username, "password_hash": _hash_password(password)})
        .execute()
    )
    if not result.data:
        raise RuntimeError("Signup failed – no row returned")
    return result.data[0]


def login_user(username: str, password: str) -> dict | None:
    """
    Validate credentials against the ``authentication`` table.
    Returns a safe user dict (no password_hash) on success, ``None`` on bad credentials.
    """
    sb = get_supabase()
    result = (
        sb.table("authentication")
        .select("*")
        .eq("username", username)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    user = result.data[0]
    if not _verify_password(password, user["password_hash"]):
        return None
    # Strip password_hash before returning
    return {k: v for k, v in user.items() if k != "password_hash"}


def get_user_by_id(user_id: int) -> dict | None:
    """Fetch a user row by its primary-key ``id`` (no password_hash)."""
    sb = get_supabase()
    result = (
        sb.table("authentication")
        .select("id, username, created_at")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_user_by_username(username: str) -> dict | None:
    """Fetch a user row by username (no password_hash)."""
    sb = get_supabase()
    result = (
        sb.table("authentication")
        .select("id, username, created_at")
        .eq("username", username)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


# ── Cookie CRUD ─────────────────────────────────────────────────────

def insert_new_user_cookies(user_id: int, cookies: list[dict], instagram_username: str | None = None) -> dict:
    """
    Always **INSERT** a new cookie row for the user.
    One user can accumulate multiple cookie snapshots (e.g. different
    IG accounts or re-logins).  The most recent row is used by default
    elsewhere via ``fetch_latest_user_cookies``.
    """
    sb = get_supabase()
    row_data = {"user_id": user_id, "cookies": cookies}
    if instagram_username:
        row_data["instagram_username"] = instagram_username
    result = (
        sb.table("user_cookies")
        .insert(row_data)
        .execute()
    )
    if not result.data:
        raise RuntimeError(f"Cookie insert failed for user_id={user_id} – no row returned")
    return result.data[0]


def upsert_user_cookies(user_id: int, cookies: list[dict]) -> dict:
    """
    Insert **or replace** cookies for a user.
    If the user already has a cookie row it is updated (so there is at
    most one active cookie per user).  Returns the upserted row.
    """
    sb = get_supabase()
    # Check for existing row
    existing = (
        sb.table("user_cookies")
        .select("id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        # Update existing row
        row_id = existing.data[0]["id"]
        result = (
            sb.table("user_cookies")
            .update({"cookies": cookies, "updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", row_id)
            .execute()
        )
    else:
        # Insert new row
        result = (
            sb.table("user_cookies")
            .insert({"user_id": user_id, "cookies": cookies})
            .execute()
        )
    if not result.data:
        raise RuntimeError(f"Cookie upsert failed for user_id={user_id} – no row returned")
    return result.data[0]


def insert_user_cookies(user_id: int, cookies: list[dict]) -> dict:
    """
    Insert a new cookie snapshot for a user.
    (Kept for backward compat – prefer ``upsert_user_cookies``.)
    """
    return upsert_user_cookies(user_id, cookies)


def fetch_all_user_cookies(user_id: int) -> list[dict]:
    """
    Fetch ALL cookie snapshots for a user (newest first).
    """
    sb = get_supabase()
    result = (
        sb.table("user_cookies")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def fetch_latest_user_cookies(user_id: int) -> dict | None:
    """Fetch only the most recent cookie snapshot for a user."""
    sb = get_supabase()
    result = (
        sb.table("user_cookies")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def delete_user_cookies(cookie_id: int) -> bool:
    """Delete a specific cookie row by its id."""
    sb = get_supabase()
    result = (
        sb.table("user_cookies")
        .delete()
        .eq("id", cookie_id)
        .execute()
    )
    return bool(result.data)


def fetch_cookies_by_id(cookie_id: int) -> dict | None:
    """Fetch a specific cookie row by its primary-key ``id``."""
    sb = get_supabase()
    result = (
        sb.table("user_cookies")
        .select("*")
        .eq("id", cookie_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


# ── Qualified Leads CRUD ────────────────────────────────────────────

def insert_qualified_lead(lead: dict) -> dict:
    """
    Insert a qualified lead row.  Uses upsert so duplicates
    (same cookie_id + niche + username) are updated instead of erroring.
    """
    sb = get_supabase()
    result = (
        sb.table("qualified_leads")
        .upsert(lead, on_conflict="cookie_id,niche,username")
        .execute()
    )
    if not result.data:
        raise RuntimeError("Failed to insert qualified lead")
    return result.data[0]


def insert_qualified_leads_batch(leads: list[dict]) -> list[dict]:
    """
    Bulk-insert qualified leads (upsert on conflict).
    """
    if not leads:
        return []
    sb = get_supabase()
    result = (
        sb.table("qualified_leads")
        .upsert(leads, on_conflict="cookie_id,niche,username")
        .execute()
    )
    return result.data or []


def fetch_qualified_leads(
    user_id: int,
    niche: str | None = None,
    cookie_id: int | None = None,
    limit: int = 200,
) -> list[dict]:
    """
    Fetch qualified leads for a web-app user.
    Optionally filter by niche and/or cookie_id (Instagram account).
    """
    sb = get_supabase()
    q = (
        sb.table("qualified_leads")
        .select("*")
        .eq("user_id", user_id)
        .order("total_score", desc=True)
        .limit(limit)
    )
    if niche:
        q = q.eq("niche", niche)
    if cookie_id:
        q = q.eq("cookie_id", cookie_id)
    result = q.execute()
    return result.data or []


def fetch_qualified_lead_niches(user_id: int) -> list[str]:
    """
    Return distinct niche values for a user's qualified leads.
    """
    sb = get_supabase()
    result = (
        sb.table("qualified_leads")
        .select("niche")
        .eq("user_id", user_id)
        .execute()
    )
    niches = sorted({r["niche"] for r in (result.data or []) if r.get("niche")})
    return niches


def delete_qualified_lead(lead_id: int) -> bool:
    """Delete a single qualified lead by id."""
    sb = get_supabase()
    result = (
        sb.table("qualified_leads")
        .delete()
        .eq("id", lead_id)
        .execute()
    )
    return bool(result.data)
