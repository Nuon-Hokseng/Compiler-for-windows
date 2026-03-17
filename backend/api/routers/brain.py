"""
Brain (Analysis) Router
=======================
Two AI analysis endpoints:
  1. General niche analysis via OllamaBrain
  2. Target customer identification via TargetIdentificationBrain
"""

from fastapi import APIRouter, BackgroundTasks
from api.shared.models import (
    AnalyzeAccountsRequest,
    ClassifyAccountsRequest,
    TaskResponse,
    create_task, update_task, make_log_fn, TaskStatus,
)

router = APIRouter(prefix="/brain", tags=["Brain (Analysis)"])


# ── Synchronous helpers (Ollama calls are blocking) ──────────────────

def _analyze_worker(task_id: str, users: list[dict], target_customer: str, model: str):
    log = make_log_fn(task_id)
    update_task(task_id, status=TaskStatus.RUNNING)
    log(f"Starting niche analysis for '{target_customer}' ({len(users)} users, model={model})")

    try:
        from agents.ollama_brain import analyze_accounts
        results = analyze_accounts(users, target_customer=target_customer, model=model)
        log(f"Analysis complete – {len(results)} relevant accounts returned")
        update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            message=f"{len(results)} accounts passed filter",
            result={"accounts": results},
        )
    except Exception as e:
        log(f"Error: {e}")
        update_task(task_id, status=TaskStatus.FAILED, message=str(e))


def _classify_worker(task_id: str, users: list[dict], model: str):
    log = make_log_fn(task_id)
    update_task(task_id, status=TaskStatus.RUNNING)
    log(f"Starting target identification ({len(users)} profiles, model={model})")

    try:
        from agents.target_identification_brain import classify_target_accounts
        results = classify_target_accounts(users, model=model)

        ideal = [r for r in results if r.get("classification") == "IDEAL TARGET"]
        possible = [r for r in results if r.get("classification") == "POSSIBLE TARGET"]
        non = [r for r in results if r.get("classification") == "NON-TARGET"]

        log(f"Done – IDEAL: {len(ideal)}, POSSIBLE: {len(possible)}, NON-TARGET: {len(non)}")
        update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            message=f"IDEAL={len(ideal)} POSSIBLE={len(possible)} NON-TARGET={len(non)}",
            result={"accounts": results},
        )
    except Exception as e:
        log(f"Error: {e}")
        update_task(task_id, status=TaskStatus.FAILED, message=str(e))


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/analyze", response_model=TaskResponse)
async def analyze_accounts_endpoint(req: AnalyzeAccountsRequest, bg: BackgroundTasks):
    """
    Send a list of Instagram usernames through the **OllamaBrain** niche filter.

    The brain classifies each account into a niche (e.g. *car enthusiast*,
    *skincare brand*) and scores relevance 1-10. Results are available via
    `GET /tasks/{task_id}` once completed.
    """
    task = create_task(f"Niche analysis – {req.target_customer}")
    bg.add_task(_analyze_worker, task.task_id, req.users, req.target_customer, req.model)
    return TaskResponse(
        task_id=task.task_id,
        status="accepted",
        message=f"Analysis queued. Poll /tasks/{task.task_id}",
    )


@router.post("/classify", response_model=TaskResponse)
async def classify_accounts_endpoint(req: ClassifyAccountsRequest, bg: BackgroundTasks):
    """
    Send profiles through the **Target Identification Brain** which scores
    them 0-100 and classifies as IDEAL TARGET / POSSIBLE TARGET / NON-TARGET
    using the Japan-focused demographic model.
    """
    task = create_task("Target identification")
    bg.add_task(_classify_worker, task.task_id, req.users, req.model)
    return TaskResponse(
        task_id=task.task_id,
        status="accepted",
        message=f"Classification queued. Poll /tasks/{task.task_id}",
    )
