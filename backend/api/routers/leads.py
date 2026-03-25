"""
Lead Generation Router
======================
Full AI-powered Instagram lead-generation pipeline.

Endpoints:
  POST /leads/discover  — Generate discovery plan only (AI #1)
  POST /leads/qualify   — Qualify profiles only (AI #2)
  POST /leads/run       — Full pipeline: discover → scrape → qualify
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from api.shared.models import (
    LeadGenRequest,
    SmartLeadRequest,
    DiscoveryPlanRequest,
    QualifyProfilesRequest,
    TaskResponse,
    create_task, update_task, make_log_fn, make_stop_fn, is_stopped, TaskStatus,
    get_task, stop_task,
    CampaignRunStatus,
    get_campaign_run, get_active_campaign_run_for_cookie,
    register_campaign_run, update_campaign_run,
)
from api.shared.db import (
    fetch_latest_user_cookies,
    fetch_cookies_by_id,
    insert_qualified_leads_batch,
    fetch_qualified_leads,
    fetch_qualified_lead_niches,
    delete_qualified_lead,
)

router = APIRouter(prefix="/leads", tags=["Lead Generation"])


# ── Discovery Plan (synchronous, fast) ──────────────────────────────

@router.post("/discover")
async def generate_discovery_plan(req: DiscoveryPlanRequest):
    """
    Generate an Instagram discovery plan from user intent.
    Returns the plan immediately (no background task).
    """
    try:
        from agents.discovery_brain import generate_discovery_plan as gen_plan
        plan = gen_plan(
            target_interest=req.target_interest,
            optional_keywords=req.optional_keywords,
            max_profiles=req.max_profiles,
            model=req.model,
        )
        return {"status": "ok", "discovery_plan": plan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Qualify Profiles (synchronous) ──────────────────────────────────

@router.post("/qualify")
async def qualify_profiles_endpoint(req: QualifyProfilesRequest):
    """
    Score and qualify a list of profiles using the Qualification Brain.
    Returns results immediately.
    """
    try:
        from agents.qualification_brain import qualify_profiles
        results = qualify_profiles(req.profiles, model=req.model)
        leads = [r for r in results if r.get("is_target", False)]
        return {
            "status": "ok",
            "leads": leads,
            "all_results": results,
            "total_scanned": len(req.profiles),
            "total_qualified": len(leads),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Full Pipeline (background task) ────────────────────────────────

def _lead_gen_worker(
    task_id: str,
    target_interest: str,
    cookies: list[dict],
    optional_keywords: list[str] | None,
    max_profiles: int,
    headless: bool,
    browser_type: str,
    model: str,
):
    """Background worker for the full lead-generation pipeline."""
    log = make_log_fn(task_id)
    stop = make_stop_fn(task_id)
    update_task(task_id, status=TaskStatus.RUNNING)
    log(f"Starting lead generation – interest='{target_interest}', max={max_profiles}, model={model}")

    try:
        from pipeline.lead_generation import run_pipeline_sync

        result = run_pipeline_sync(
            target_interest=target_interest,
            cookies=cookies,
            optional_keywords=optional_keywords,
            max_profiles=max_profiles,
            headless=headless,
            browser_type=browser_type,
            model=model,
            log_fn=log,
            stop_fn=stop,
        )

        leads = result.get("leads", [])
        total_scanned = result.get("total_scanned", 0)
        total_qualified = result.get("total_qualified", 0)

        log(f"Pipeline complete: {total_qualified} leads from {total_scanned} profiles")

        update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            message=f"{total_qualified} leads found from {total_scanned} profiles",
            result={
                "leads": leads,
                "all_results": result.get("all_results", []),
                "total_scanned": total_scanned,
                "total_qualified": total_qualified,
                "discovery_plan": result.get("discovery_plan", {}),
            },
        )
    except Exception as e:
        log(f"Pipeline error: {e}")
        update_task(task_id, status=TaskStatus.FAILED, message=str(e))


@router.post("/run", response_model=TaskResponse)
async def run_lead_generation(req: LeadGenRequest, bg: BackgroundTasks):
    """
    Launch the full lead-generation pipeline as a background task.

    Flow:
      1. Discovery Brain generates search plan
      2. Playwright scrapes discovered profiles
      3. Qualification Brain scores each profile
      4. Returns ranked leads

    Poll GET /tasks/{task_id} for progress and results.
    """
    # Validate cookies exist
    row = fetch_latest_user_cookies(req.user_id)
    if not row or not row.get("cookies"):
        raise HTTPException(
            status_code=400,
            detail=f"No Instagram cookies for user_id={req.user_id}. Save session first.",
        )

    cookies = row["cookies"]

    task = create_task(f"Lead generation – {req.target_interest}")
    bg.add_task(
        _lead_gen_worker,
        task.task_id,
        req.target_interest,
        cookies,
        req.optional_keywords,
        req.max_profiles,
        req.headless,
        req.browser_type,
        req.model,
    )

    return TaskResponse(
        task_id=task.task_id,
        status="accepted",
        message=f"Lead generation started. Poll /tasks/{task.task_id}",
    )


# ── Smart Pipeline (scroll + collect + qualify + follow) ────────────

def _smart_lead_gen_worker(
    task_id: str,
    target_interest: str,
    cookies: list[dict],
    optional_keywords: list[str] | None,
    max_profiles: int,
    headless: bool,
    browser_type: str,
    model: str,
    user_id: int | None = None,
    cookie_id: int | None = None,
    campaign_id: int | None = None,
):
    """Background worker for the unified smart lead-generation pipeline."""
    log = make_log_fn(task_id)
    stop = make_stop_fn(task_id)
    update_task(task_id, status=TaskStatus.RUNNING)
    if campaign_id:
        update_campaign_run(campaign_id, status=CampaignRunStatus.RUNNING, message="Campaign is running")
    log(f"Starting smart pipeline – interest='{target_interest}', max={max_profiles}, model={model}")

    def on_plan_ready(plan):
        """Surface the discovery plan as soon as it's available."""
        update_task(task_id, result={"discovery_plan": plan, "phase": "collecting"})

    try:
        from pipeline.smart_lead_pipeline import run_smart_lead_pipeline

        result = run_smart_lead_pipeline(
            cookies=cookies,
            target_interest=target_interest,
            optional_keywords=optional_keywords,
            max_profiles=max_profiles,
            headless=headless,
            browser_type=browser_type,
            model=model,
            stop_flag=stop,
            log_callback=log,
            on_plan_ready=on_plan_ready,
        )

        leads = result.get("leads", [])
        total_scanned = result.get("total_scanned", 0)
        total_qualified = result.get("total_qualified", 0)
        profiles_followed = result.get("profiles_followed", 0)

        if is_stopped(task_id):
            log(f"Pipeline stopped: {total_qualified} leads from {total_scanned} profiles")
            update_task(
                task_id,
                status=TaskStatus.STOPPED,
                message=f"Stopped – {total_qualified} leads found, {profiles_followed} followed",
                result=result,
            )
            if campaign_id:
                update_campaign_run(
                    campaign_id,
                    status=CampaignRunStatus.STOPPED,
                    message=f"Stopped – {total_qualified} leads found",
                )
        else:
            log(f"Pipeline complete: {total_qualified} leads from {total_scanned} profiles, {profiles_followed} followed")
            update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                message=f"{total_qualified} leads found, {profiles_followed} followed from {total_scanned} profiles",
                result=result,
            )
            if campaign_id:
                update_campaign_run(
                    campaign_id,
                    status=CampaignRunStatus.COMPLETED,
                    message=f"Completed – {total_qualified} leads found",
                )
        # ── Save qualified leads to database ──
        if leads and user_id and cookie_id:
            try:
                rows = []
                for lead in leads:
                    rows.append({
                        "user_id": user_id,
                        "cookie_id": cookie_id,
                        "campaign_id": campaign_id,
                        "niche": target_interest,
                        "username": lead.get("username", ""),
                        "full_name": lead.get("full_name", ""),
                        "bio": lead.get("bio", ""),
                        "followers_count": lead.get("followers_count", 0),
                        "following_count": lead.get("following_count", 0),
                        "profile_image_url": lead.get("profile_image_url", ""),
                        "detected_language": lead.get("detected_language", ""),
                        "total_score": lead.get("total_score", 0),
                        "scores": lead.get("scores", {}),
                        "confidence": lead.get("confidence", "low"),
                        "reasoning": lead.get("reasoning", ""),
                        "discovery_source": lead.get("discovery_source", ""),
                        "followed": bool(lead.get("followed", False)),
                    })
                saved = insert_qualified_leads_batch(rows)
                log(f"\U0001f4be Saved {len(saved)} qualified leads to database")
            except Exception as db_err:
                log(f"\u26a0\ufe0f DB save warning: {db_err}")
    except Exception as e:
        log(f"Pipeline error: {e}")
        update_task(task_id, status=TaskStatus.FAILED, message=str(e))
        if campaign_id:
            update_campaign_run(
                campaign_id,
                status=CampaignRunStatus.FAILED,
                message=f"Failed: {e}",
            )


@router.post("/smart-run", response_model=TaskResponse)
async def run_smart_lead_generation(req: SmartLeadRequest, bg: BackgroundTasks):
    """
    Launch the unified smart lead-generation pipeline as a background task.

    Three-phase flow:
      1. Discovery Brain generates search plan (runs in parallel with scrolling)
      2. Scroll Instagram feed + collect accounts from plan targets
      3. Visit each profile → qualify with AI → follow if qualified

    Poll GET /tasks/{task_id} for progress and results.
    """
    # Keep same-campaign starts idempotent.
    if req.campaign_id:
        existing = get_campaign_run(req.campaign_id)
        if existing and existing.user_id == req.user_id:
            existing_task = get_task(existing.task_id)
            if existing_task and existing_task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                return TaskResponse(
                    task_id=existing.task_id,
                    status="accepted",
                    message=f"Campaign already running. Poll /tasks/{existing.task_id}",
                )

    # ── Resolve cookies: prefer explicit cookie_id, fallback to latest ──
    cookie_id = None
    if req.cookie_id:
        row = fetch_cookies_by_id(req.cookie_id)
        if not row or not row.get("cookies"):
            raise HTTPException(
                status_code=400,
                detail=f"No cookies found for cookie_id={req.cookie_id}.",
            )
        cookie_id = req.cookie_id
    else:
        row = fetch_latest_user_cookies(req.user_id)
        if not row or not row.get("cookies"):
            raise HTTPException(
                status_code=400,
                detail=f"No Instagram cookies for user_id={req.user_id}. Save session first.",
            )
        cookie_id = row.get("id")

    cookies = row["cookies"]

    # Allow many campaigns per user, but only one running campaign per IG account (cookie_id).
    if req.campaign_id and cookie_id is not None:
        active_run = get_active_campaign_run_for_cookie(req.user_id, cookie_id)
        if active_run and active_run.campaign_id != req.campaign_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"This Instagram account is already running another campaign "
                    f"(campaign_id={active_run.campaign_id}, task_id={active_run.task_id}). "
                    f"Use a different account cookie or stop the running campaign first."
                ),
            )

    task = create_task(f"Smart lead pipeline \u2013 {req.target_interest}")
    if req.campaign_id:
        register_campaign_run(
            campaign_id=req.campaign_id,
            user_id=req.user_id,
            cookie_id=cookie_id,
            task_id=task.task_id,
            target_interest=req.target_interest,
        )
    bg.add_task(
        _smart_lead_gen_worker,
        task.task_id,
        req.target_interest,
        cookies,
        req.optional_keywords,
        req.max_profiles,
        req.headless,
        req.browser_type,
        req.model,
        req.user_id,
        cookie_id,
        req.campaign_id,
    )

    return TaskResponse(
        task_id=task.task_id,
        status="accepted",
        message=f"Smart pipeline started. Poll /tasks/{task.task_id}",
    )


@router.get("/campaigns/{campaign_id}/run-status")
async def get_campaign_run_status(campaign_id: int, user_id: int):
    """Return latest campaign run + task state so UI can recover after refresh."""
    run = get_campaign_run(campaign_id)
    if not run or run.user_id != user_id:
        return {"campaign_id": campaign_id, "active": False, "run": None, "task": None}

    task = get_task(run.task_id)
    if task:
        if task.status == TaskStatus.PENDING:
            update_campaign_run(campaign_id, status=CampaignRunStatus.PENDING, message=task.message or run.message)
        elif task.status == TaskStatus.RUNNING:
            update_campaign_run(campaign_id, status=CampaignRunStatus.RUNNING, message=task.message or run.message)
        elif task.status == TaskStatus.COMPLETED:
            update_campaign_run(campaign_id, status=CampaignRunStatus.COMPLETED, message=task.message or run.message)
        elif task.status == TaskStatus.FAILED:
            update_campaign_run(campaign_id, status=CampaignRunStatus.FAILED, message=task.message or run.message)
        elif task.status == TaskStatus.STOPPED:
            update_campaign_run(campaign_id, status=CampaignRunStatus.STOPPED, message=task.message or run.message)
        run = get_campaign_run(campaign_id)

    active = bool(run and run.status in (CampaignRunStatus.PENDING, CampaignRunStatus.RUNNING))
    return {
        "campaign_id": campaign_id,
        "active": active,
        "run": run,
        "task": task,
    }


@router.post("/campaigns/{campaign_id}/stop", response_model=TaskResponse)
async def stop_campaign_run(campaign_id: int, user_id: int):
    """Stop an active campaign background run."""
    run = get_campaign_run(campaign_id)
    if not run or run.user_id != user_id:
        raise HTTPException(status_code=404, detail="No campaign run found")

    task = get_task(run.task_id)
    if not task or task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        raise HTTPException(status_code=409, detail="Campaign is not currently running")

    stop_task(run.task_id)
    update_campaign_run(campaign_id, status=CampaignRunStatus.STOPPED, message="Stop signal sent")
    return TaskResponse(task_id=run.task_id, status="stopping", message="Stop signal sent")


# ── Saved Qualified Leads ───────────────────────────────────────────

@router.get("/saved")
async def get_saved_leads(
    user_id: int,
    niche: str | None = None,
    cookie_id: int | None = None,
    campaign_id: int | None = None,
    limit: int = 200,
):
    """Return saved qualified leads, optionally filtered by niche, cookie_id, or campaign_id."""
    rows = fetch_qualified_leads(user_id, niche=niche, cookie_id=cookie_id, campaign_id=campaign_id, limit=limit)
    return {"status": "ok", "leads": rows}


@router.get("/saved/niches")
async def get_saved_niches(user_id: int):
    """Return distinct niche values the user has saved leads for."""
    niches = fetch_qualified_lead_niches(user_id)
    return {"status": "ok", "niches": niches}


@router.delete("/saved/{lead_id}")
async def remove_saved_lead(lead_id: int):
    """Delete a single saved lead by its row id."""
    deleted = delete_qualified_lead(lead_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"status": "ok", "deleted": deleted}
