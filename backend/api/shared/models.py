"""Shared Pydantic models and task manager for all API routers."""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum
import uuid
from datetime import datetime


# ── Browser type ────────────────────────────────────────────────────

BROWSER_TYPE_CHOICES = Literal["chromium", "chrome", "msedge", "brave", "opera", "firefox", "webkit", "safari"]


# ── Task Management ─────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class CampaignRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class TaskInfo(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: str
    message: str = ""
    result: Optional[dict] = None
    logs: list[str] = []


class CampaignRunInfo(BaseModel):
    campaign_id: int
    user_id: int
    cookie_id: int
    task_id: str
    target_interest: str
    status: CampaignRunStatus
    message: str = ""
    created_at: str
    updated_at: str


# In-memory store for background tasks
_tasks: dict[str, TaskInfo] = {}
_stop_flags: dict[str, bool] = {}
_campaign_runs: dict[int, CampaignRunInfo] = {}


def _now_iso() -> str:
    return datetime.now().isoformat()


def create_task(description: str = "") -> TaskInfo:
    task_id = str(uuid.uuid4())[:8]
    task = TaskInfo(
        task_id=task_id,
        status=TaskStatus.PENDING,
        created_at=datetime.now().isoformat(),
        message=description,
    )
    _tasks[task_id] = task
    _stop_flags[task_id] = False
    return task


def get_task(task_id: str) -> Optional[TaskInfo]:
    return _tasks.get(task_id)


def update_task(task_id: str, **kwargs):
    if task_id in _tasks:
        task = _tasks[task_id]
        for k, v in kwargs.items():
            setattr(task, k, v)


def add_task_log(task_id: str, msg: str):
    if task_id in _tasks:
        _tasks[task_id].logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def stop_task(task_id: str):
    """Signal a task to stop and immediately mark it as STOPPED."""
    _stop_flags[task_id] = True
    if task_id in _tasks:
        task = _tasks[task_id]
        if task.status in (TaskStatus.RUNNING, TaskStatus.PENDING):
            task.status = TaskStatus.STOPPED
            task.message = "Stopped by user"


def stop_all_tasks() -> list[str]:
    """Set the stop flag for ALL running/pending tasks. Returns list of stopped task IDs."""
    stopped = []
    for task_id, task in _tasks.items():
        if task.status in (TaskStatus.RUNNING, TaskStatus.PENDING):
            _stop_flags[task_id] = True
            task.status = TaskStatus.STOPPED
            task.message = "Stopped by stop-all"
            stopped.append(task_id)
    return stopped


def is_stopped(task_id: str) -> bool:
    return _stop_flags.get(task_id, False)


def list_all_tasks() -> list[TaskInfo]:
    return list(_tasks.values())


def get_campaign_run(campaign_id: int) -> Optional[CampaignRunInfo]:
    return _campaign_runs.get(campaign_id)


def get_active_campaign_run_for_user(user_id: int) -> Optional[CampaignRunInfo]:
    for run in _campaign_runs.values():
        if run.user_id == user_id and run.status in (CampaignRunStatus.PENDING, CampaignRunStatus.RUNNING):
            return run
    return None


def get_active_campaign_run_for_cookie(user_id: int, cookie_id: int) -> Optional[CampaignRunInfo]:
    for run in _campaign_runs.values():
        if (
            run.user_id == user_id
            and run.cookie_id == cookie_id
            and run.status in (CampaignRunStatus.PENDING, CampaignRunStatus.RUNNING)
        ):
            return run
    return None


def register_campaign_run(campaign_id: int, user_id: int, cookie_id: int, task_id: str, target_interest: str) -> CampaignRunInfo:
    now = _now_iso()
    run = CampaignRunInfo(
        campaign_id=campaign_id,
        user_id=user_id,
        cookie_id=cookie_id,
        task_id=task_id,
        target_interest=target_interest,
        status=CampaignRunStatus.PENDING,
        message="Campaign queued",
        created_at=now,
        updated_at=now,
    )
    _campaign_runs[campaign_id] = run
    return run


def update_campaign_run(
    campaign_id: int,
    *,
    status: CampaignRunStatus | None = None,
    message: str | None = None,
    task_id: str | None = None,
) -> Optional[CampaignRunInfo]:
    run = _campaign_runs.get(campaign_id)
    if not run:
        return None
    if status is not None:
        run.status = status
    if message is not None:
        run.message = message
    if task_id is not None:
        run.task_id = task_id
    run.updated_at = _now_iso()
    return run


def make_log_fn(task_id: str):
    """Create a log function that appends to the task's log list."""
    def log(msg: str):
        add_task_log(task_id, msg)
    return log


def make_stop_fn(task_id: str):
    """Create a stop-flag callable for Playwright loops."""
    def should_stop() -> bool:
        return is_stopped(task_id)
    return should_stop


# ── Request / Response Models ───────────────────────────────────────

class SignupRequest(BaseModel):
    username: str = Field(..., description="Username for the web app (authentication table)")
    password: str = Field(..., min_length=6, description="Password (min 6 chars)")


class LoginRequest(BaseModel):
    username: str = Field(..., description="Web-app username")
    password: str = Field(..., description="Password")


class LoginResponse(BaseModel):
    user_id: int
    username: str
    message: str = "Login successful"


class SessionRequest(BaseModel):
    user_id: int = Field(..., description="User id from the authentication table")
    timeout: int = Field(120, description="Seconds to wait for manual Instagram login")
    browser_type: BROWSER_TYPE_CHOICES = Field("chrome", description="Browser engine: chrome, firefox, or webkit")


class ExtensionSessionRequest(BaseModel):
    user_id: int = Field(..., description="User id from the authentication table")
    cookies: list[dict] = Field(..., description="Array of cookies extracted from the Chrome extension")
    instagram_username: Optional[str] = Field(None, description="Optional Instagram username if known")


class AnalyzeAccountsRequest(BaseModel):
    users: list[dict] = Field(..., description="List of user dicts with at least a 'username' key")
    target_customer: str = Field(..., description="Target customer key, e.g. 'car', 'skincare', 'ideal'")
    model: str = Field("claude-3-haiku-20240307", description="Model name")


class ClassifyAccountsRequest(BaseModel):
    users: list[dict] = Field(..., description="List of user dicts (username, bio, post_summary, etc.)")
    model: str = Field("claude-3-haiku-20240307", description="Model name")


class ExportCSVRequest(BaseModel):
    results: list[dict] = Field(..., description="List of analyzed result dicts")
    target_customer: str = Field(..., description="Target customer key")
    output_dir: str = Field("output", description="Directory to save CSV files")


class ValidateCSVRequest(BaseModel):
    csv_path: str = Field(..., description="Path to the CSV file to validate")


class CreateSampleCSVRequest(BaseModel):
    output_path: str = Field(..., description="Path to save the sample CSV file")
    target_type: str = Field("hashtag", description="'hashtag' or 'username'")
    samples: Optional[list[str]] = Field(None, description="Custom sample values")


class ScrapeRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table (cookies loaded from DB)")
    target_customer: str = Field(..., description="Target customer key")
    headless: bool = Field(True, description="Run browser in headless mode (default: visible)")
    max_commenters: int = Field(15, description="Max commenters to extract per post")
    model: str = Field("claude-3-haiku-20240307", description="Model for analysis")
    browser_type: BROWSER_TYPE_CHOICES = Field("chrome", description="Browser engine: chrome, firefox, or webkit")


class ScrollRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table (cookies loaded from DB)")
    duration: int = Field(60, description="Session duration in seconds")
    headless: bool = Field(True, description="Run browser in headless mode (default: visible)")
    infinite_mode: bool = Field(False, description="Enable infinite scroll mode with rest cycles")
    browser_type: BROWSER_TYPE_CHOICES = Field("chrome", description="Browser engine: chrome, firefox, or webkit")


class CombinedScrollRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table (cookies loaded from DB)")
    duration: int = Field(60, description="Session duration in seconds")
    headless: bool = Field(True, description="Run browser in headless mode (default: visible)")
    infinite_mode: bool = Field(False, description="Enable infinite mode with rest cycles")
    search_targets: Optional[list[str]] = Field(None, description="Targets to randomly search/explore")
    search_chance: float = Field(0.30, description="Probability of exploring a target per scroll cycle")
    profile_scroll_count_min: int = Field(3, description="Min scrolls on a profile page")
    profile_scroll_count_max: int = Field(8, description="Max scrolls on a profile page")
    browser_type: BROWSER_TYPE_CHOICES = Field("chromium", description="Browser engine: chromium, firefox, or webkit")


class ScraperScrollRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table (cookies loaded from DB)")
    duration: int = Field(60, description="Session duration in seconds")
    headless: bool = Field(True, description="Run browser in headless mode (default: visible)")
    infinite_mode: bool = Field(False, description="Enable infinite mode")
    target_customer: str = Field("car", description="Target customer key for scraper pipeline")
    scraper_chance: float = Field(0.20, description="Probability of triggering scraper per scroll")
    model: str = Field("claude-3-haiku-20240307", description="Model name")
    search_targets: Optional[list[str]] = Field(None, description="Extra search targets")
    search_chance: float = Field(0.30, description="Probability of random explore")
    profile_scroll_count_min: int = Field(3)
    profile_scroll_count_max: int = Field(8)
    browser_type: BROWSER_TYPE_CHOICES = Field("chromium", description="Browser engine: chromium, firefox, or webkit")


class CSVProfileVisitRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table (cookies loaded from DB)")
    csv_path: str = Field(..., description="Path to CSV file containing targets to visit")
    headless: bool = Field(True, description="Run browser in headless mode (default: visible)")
    scroll_count_min: int = Field(3, description="Min scrolls per profile")
    scroll_count_max: int = Field(8, description="Max scrolls per profile")
    delay_min: int = Field(5, description="Min seconds delay between profile visits")
    delay_max: int = Field(15, description="Max seconds delay between profile visits")
    like_chance: float = Field(0.10, description="Probability of liking a post while scrolling")
    browser_type: BROWSER_TYPE_CHOICES = Field("chromium", description="Browser engine: chromium, firefox, or webkit")


class SearchRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table (cookies loaded from DB)")
    search_term: str = Field(..., description="The term to search for")
    search_type: str = Field("hashtag", description="'hashtag' or 'username'")
    headless: bool = Field(True, description="Run browser in headless mode (default: visible)")
    keep_open: bool = Field(False, description="Keep browser open after search (blocks until stopped)")
    browser_type: BROWSER_TYPE_CHOICES = Field("chromium", description="Browser engine: chromium, firefox, or webkit")


# ── Campaigns ───────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    user_id: int = Field(..., description="User ID from authentication table")
    name: str = Field(..., description="Name of the campaign")
    target_interest: str = Field(..., description="Target interest / customer description")
    optional_keywords: Optional[list[str]] = Field(None, description="Additional search keywords")
    max_profiles: int = Field(50, description="Max profiles to discover")


class CampaignResponse(BaseModel):
    id: int
    user_id: int
    name: str
    target_interest: str
    optional_keywords: Optional[list[str]] = None
    max_profiles: int
    created_at: str
    updated_at: str


# ── Lead Generation Pipeline ────────────────────────────────────────

class LeadGenRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table (cookies loaded from DB)")
    target_interest: str = Field(..., description="Target interest / customer description")
    optional_keywords: Optional[list[str]] = Field(None, description="Additional search keywords")
    max_profiles: int = Field(50, ge=1, le=200, description="Max profiles to discover and analyze")
    headless: bool = Field(True, description="Run browser in headless mode")
    browser_type: BROWSER_TYPE_CHOICES = Field("chromium", description="Browser engine")
    model: str = Field("gpt-4.1-mini", description="OpenAI model for both AI brains")
    campaign_id: Optional[int] = Field(None, description="Campaign ID to associate leads with")


class SmartLeadRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table")
    cookie_id: Optional[int] = Field(None, description="Specific cookie row id – when set, uses that IG account instead of the latest")
    target_interest: str = Field(..., description="Target interest / customer description")
    optional_keywords: Optional[list[str]] = Field(None, description="Additional search keywords")
    max_profiles: int = Field(50, ge=1, le=200, description="Max profiles to discover and qualify")
    headless: bool = Field(True, description="Run browser in headless mode")
    browser_type: BROWSER_TYPE_CHOICES = Field("chromium", description="Browser engine")
    model: str = Field("gpt-4.1-mini", description="AI model for both brains")
    campaign_id: Optional[int] = Field(None, description="Campaign ID to associate leads with")


class DiscoveryPlanRequest(BaseModel):
    target_interest: str = Field(..., description="Target interest / customer description")
    optional_keywords: Optional[list[str]] = Field(None, description="Additional search keywords")
    max_profiles: int = Field(50, ge=1, le=200, description="Max profiles to discover")
    model: str = Field("gpt-4.1-mini", description="OpenAI model for Discovery Brain")


class QualifyProfilesRequest(BaseModel):
    profiles: list[dict] = Field(..., description="List of profile dicts with username, bio, etc.")
    model: str = Field("gpt-4.1-mini", description="OpenAI model for Qualification Brain")


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TargetListResponse(BaseModel):
    targets: list[str]
    details: dict[str, str] = {}
