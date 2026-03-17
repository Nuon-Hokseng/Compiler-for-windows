"""
Scraper Router
==============
CSV utilities and the full async Instagram scraper pipeline.
"""

import os

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from api.shared.models import (
    ExportCSVRequest, ValidateCSVRequest, CreateSampleCSVRequest,
    ScrapeRequest, TaskResponse,
    create_task, update_task, make_log_fn, TaskStatus,
)

router = APIRouter(prefix="/scraper", tags=["Scraper"])


# ── CSV Utility Endpoints (synchronous, lightweight) ─────────────────

@router.post("/csv/export", response_model=TaskResponse)
async def export_csv(req: ExportCSVRequest):
    """
    Export analysis results to a CSV file.
    Returns the file path immediately (no background task needed).
    """
    try:
        from output.csv_export import export_to_csv
        filepath = export_to_csv(req.results, req.target_customer, req.output_dir)
        return TaskResponse(task_id="sync", status="completed", message=f"Exported to {filepath}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Allowed directories for file serving (prevents path traversal)
_ALLOWED_DIRS = [os.path.abspath("output"), os.path.abspath("uploads")]


def _safe_path(filepath: str) -> str:
    """Resolve a path and ensure it falls inside an allowed directory."""
    resolved = os.path.abspath(filepath)
    if not any(resolved.startswith(d) for d in _ALLOWED_DIRS):
        raise HTTPException(status_code=403, detail="Access denied – path outside allowed directories")
    return resolved


@router.get("/csv/download")
async def download_csv(filepath: str):
    """
    Download a previously exported CSV file.
    Pass the `filepath` returned by `/scraper/csv/export`.
    """
    safe = _safe_path(filepath)
    if not os.path.isfile(safe):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(safe, media_type="text/csv", filename=os.path.basename(safe))


@router.post("/csv/validate")
async def validate_csv(req: ValidateCSVRequest):
    """Validate that a CSV file has the correct header format."""
    from utils.csv_loader import validate_csv_format
    is_valid, message, target_type = validate_csv_format(req.csv_path)
    return {"valid": is_valid, "message": message, "target_type": target_type}


@router.post("/csv/load")
async def load_csv(req: ValidateCSVRequest):
    """Load and parse targets from a CSV file."""
    from utils.csv_loader import load_targets_from_csv
    result = load_targets_from_csv(req.csv_path)
    if result is None:
        raise HTTPException(status_code=400, detail="Failed to load CSV – check format")
    return result


@router.post("/csv/sample")
async def create_sample(req: CreateSampleCSVRequest):
    """Create a sample CSV file for testing."""
    from utils.csv_loader import create_sample_csv
    ok = create_sample_csv(req.output_path, req.target_type, req.samples)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create sample CSV")
    return {"message": f"Sample CSV created at {req.output_path}"}


@router.post("/csv/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload a CSV file and save it to the server.
    Returns the saved path so you can pass it to other endpoints.
    """
    save_dir = "uploads"  # fixed directory – not user-controllable
    os.makedirs(save_dir, exist_ok=True)
    # Sanitize filename: strip path components, allow only safe chars
    import re as _re
    safe_name = os.path.basename(file.filename or "upload.csv")
    safe_name = _re.sub(r'[^a-zA-Z0-9_.-]', '_', safe_name)
    if not safe_name.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")
    dest = os.path.join(save_dir, safe_name)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    with open(dest, "wb") as f:
        f.write(content)
    return {"saved_path": dest, "filename": safe_name}


# ── Targets Config ───────────────────────────────────────────────────

@router.get("/targets")
async def list_targets():
    """List all available target customer presets and their display names."""
    from config.targets import list_available_targets, get_target_display_name
    keys = list_available_targets()
    return {
        "targets": keys,
        "details": {k: get_target_display_name(k) for k in keys},
    }


@router.get("/targets/{target_key}")
async def get_target_detail(target_key: str):
    """Get the full configuration for a specific target customer preset."""
    from config.targets import get_target_config
    config = get_target_config(target_key)
    if not config:
        raise HTTPException(status_code=404, detail=f"Unknown target: {target_key}")
    return config


# ── Full Async Scraper ──────────────────────────────────────────────

def _scrape_worker(task_id: str, target_customer: str, user_id: int,
                   headless: bool, max_commenters: int, model: str, browser_type: str):
    """Run the full async scraper + Ollama analysis + CSV export."""
    import asyncio
    log = make_log_fn(task_id)
    update_task(task_id, status=TaskStatus.RUNNING)
    log(f"Starting scraper pipeline – target={target_customer}, model={model}, browser={browser_type}")

    async def _run():
        try:
            # Fetch cookies from DB
            from api.shared.db import fetch_latest_user_cookies
            row = fetch_latest_user_cookies(user_id)
            if not row or not row.get("cookies"):
                raise RuntimeError(f"No cookies for user_id={user_id}. Call POST /session/save first.")
            cookies = row["cookies"]
            log(f"Loaded {len(cookies)} cookies from DB for user_id={user_id}")

            from browser.scraper import InstagramScraper
            scraper = InstagramScraper(
                target_customer=target_customer,
                headless=headless,
                max_commenters=max_commenters,
                browser_type=browser_type,
                cookies=cookies,
            )
            scraped = await scraper.run_session()
            log(f"Scraped {len(scraped)} raw accounts")

            if not scraped:
                update_task(task_id, status=TaskStatus.COMPLETED,
                            message="No accounts scraped", result={"accounts": []})
                return

            # Ollama analysis
            from agents.ollama_brain import analyze_accounts
            results = analyze_accounts(scraped, target_customer=target_customer, model=model)
            log(f"Ollama filtered to {len(results)} relevant accounts")

            # CSV export
            from output.csv_export import export_to_csv
            csv_path = export_to_csv(results, target_customer)
            log(f"Exported to {csv_path}")

            update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                message=f"{len(results)} relevant accounts exported to {csv_path}",
                result={"accounts": results, "csv_path": csv_path},
            )
        except Exception as e:
            log(f"Error: {e}")
            update_task(task_id, status=TaskStatus.FAILED, message=str(e))

    asyncio.run(_run())


@router.post("/run", response_model=TaskResponse)
async def run_scraper(req: ScrapeRequest, bg: BackgroundTasks):
    """
    Launch the full Instagram scraper pipeline in the background:
    1. Navigate to hashtag pages and collect post owners + commenters
    2. Send collected accounts to Ollama for niche analysis
    3. Export results to CSV

    Progress & results available via `GET /tasks/{task_id}`.
    """
    task = create_task(f"Scraper pipeline – {req.target_customer}")
    bg.add_task(
        _scrape_worker,
        task.task_id, req.target_customer, req.user_id,
        req.headless, req.max_commenters, req.model, req.browser_type,
    )
    return TaskResponse(
        task_id=task.task_id,
        status="accepted",
        message=f"Scraper started. Poll /tasks/{task.task_id}",
    )
