"""
Lead Generation Pipeline — Full orchestrator.

Connects:
  1. Discovery Brain (AI #1) — user intent → search plan
  2. Profile Scraper (Playwright) — search plan → profile data
  3. Qualification Brain (AI #2) — inline per-profile scoring

Implements the spec's required flow:
  for profile in discovered_profiles:
      scrape profile
      analyze with Qualification Brain
      if is_target: store lead

Designed for: scalability, low token cost, Instagram safety.
"""

import asyncio
from typing import Callable


async def run_lead_generation_pipeline(
    target_interest: str,
    cookies: list[dict],
    optional_keywords: list[str] | None = None,
    max_profiles: int = 50,
    headless: bool = False,
    browser_type: str = "chrome",
    model: str = "gpt-4.1-mini",
    log_fn: Callable | None = None,
    stop_fn: Callable | None = None,
) -> dict:
    """
    Run the full lead-generation pipeline.

    Flow:
      1. Discovery Brain generates search plan from user intent
      2. Playwright scrapes profiles following the plan
      3. Each profile is scored inline by Qualification Brain
      4. Only is_target=true profiles are kept as leads

    Returns:
        {
            "leads": [...qualified profiles sorted by total_score DESC...],
            "all_results": [...all scored profiles...],
            "total_scanned": int,
            "total_qualified": int,
            "discovery_plan": dict,
        }
    """
    _log = log_fn or (lambda msg: print(f"[Pipeline] {msg}"))
    _stop = stop_fn or (lambda: False)

    # ── Step 1: Discovery Brain ─────────────────────────────────────
    _log("Step 1/2: Generating discovery plan with AI...")

    from agents.discovery_brain import generate_discovery_plan

    discovery_plan = generate_discovery_plan(
        target_interest=target_interest,
        optional_keywords=optional_keywords,
        max_profiles=max_profiles,
        model=model,
    )

    _log(
        f"Discovery plan ready: "
        f"{len(discovery_plan.get('hashtags', []))} hashtags, "
        f"{len(discovery_plan.get('search_queries', []))} queries, "
        f"{len(discovery_plan.get('seed_accounts', []))} seed accounts"
    )

    if _stop():
        return {"leads": [], "all_results": [], "total_scanned": 0, "total_qualified": 0, "discovery_plan": discovery_plan}

    # ── Step 2: Scrape + Inline Qualify ─────────────────────────────
    _log("Step 2/2: Scraping profiles & qualifying inline with AI...")

    from agents.qualification_brain import make_inline_qualifier
    from browser.profile_scraper import scrape_profiles

    qualify_fn = make_inline_qualifier(model=model)

    result = await scrape_profiles(
        discovery_plan=discovery_plan,
        cookies=cookies,
        max_profiles=max_profiles,
        headless=headless,
        browser_type=browser_type,
        log_fn=_log,
        stop_fn=_stop,
        qualify_fn=qualify_fn,
    )

    leads = result.get("leads", [])
    all_profiles = result.get("profiles", [])
    total_scanned = result.get("total_scanned", 0)
    total_qualified = result.get("total_qualified", 0)

    # Sort leads by total_score DESC
    leads.sort(key=lambda x: -(x.get("total_score") or 0))

    _log(f"Pipeline complete: {total_qualified} leads from {total_scanned} profiles")

    return {
        "leads": leads,
        "all_results": leads,  # Only qualified leads in all_results for frontend
        "total_scanned": total_scanned,
        "total_qualified": total_qualified,
        "discovery_plan": discovery_plan,
    }


def run_pipeline_sync(
    target_interest: str,
    cookies: list[dict],
    optional_keywords: list[str] | None = None,
    max_profiles: int = 50,
    headless: bool = False,
    browser_type: str = "chrome",
    model: str = "gpt-4.1-mini",
    log_fn: Callable | None = None,
    stop_fn: Callable | None = None,
) -> dict:
    """
    Synchronous wrapper for the lead-generation pipeline.
    Used by FastAPI background tasks.
    """
    return asyncio.run(
        run_lead_generation_pipeline(
            target_interest=target_interest,
            cookies=cookies,
            optional_keywords=optional_keywords,
            max_profiles=max_profiles,
            headless=headless,
            browser_type=browser_type,
            model=model,
            log_fn=log_fn,
            stop_fn=stop_fn,
        )
    )
