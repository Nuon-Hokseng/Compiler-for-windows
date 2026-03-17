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


class TaskInfo(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: str
    message: str = ""
    result: Optional[dict] = None
    logs: list[str] = []


# In-memory store for background tasks
_tasks: dict[str, TaskInfo] = {}
_stop_flags: dict[str, bool] = {}


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


class AnalyzeAccountsRequest(BaseModel):
    users: list[dict] = Field(..., description="List of user dicts with at least a 'username' key")
    target_customer: str = Field(..., description="Target customer key, e.g. 'car', 'skincare', 'ideal'")
    model: str = Field("llama3:8b", description="Ollama model name")


class ClassifyAccountsRequest(BaseModel):
    users: list[dict] = Field(..., description="List of user dicts (username, bio, post_summary, etc.)")
    model: str = Field("llama3:8b", description="Ollama model name")


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
    headless: bool = Field(False, description="Run browser in headless mode (default: visible)")
    max_commenters: int = Field(15, description="Max commenters to extract per post")
    model: str = Field("llama3:8b", description="Ollama model for analysis")
    browser_type: BROWSER_TYPE_CHOICES = Field("chrome", description="Browser engine: chrome, firefox, or webkit")


class ScrollRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table (cookies loaded from DB)")
    duration: int = Field(60, description="Session duration in seconds")
    headless: bool = Field(False, description="Run browser in headless mode (default: visible)")
    infinite_mode: bool = Field(False, description="Enable infinite scroll mode with rest cycles")
    browser_type: BROWSER_TYPE_CHOICES = Field("chrome", description="Browser engine: chrome, firefox, or webkit")


class CombinedScrollRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table (cookies loaded from DB)")
    duration: int = Field(60, description="Session duration in seconds")
    headless: bool = Field(False, description="Run browser in headless mode (default: visible)")
    infinite_mode: bool = Field(False, description="Enable infinite mode with rest cycles")
    search_targets: Optional[list[str]] = Field(None, description="Targets to randomly search/explore")
    search_chance: float = Field(0.30, description="Probability of exploring a target per scroll cycle")
    profile_scroll_count_min: int = Field(3, description="Min scrolls on a profile page")
    profile_scroll_count_max: int = Field(8, description="Max scrolls on a profile page")
    browser_type: BROWSER_TYPE_CHOICES = Field("chromium", description="Browser engine: chromium, firefox, or webkit")


class ScraperScrollRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table (cookies loaded from DB)")
    duration: int = Field(60, description="Session duration in seconds")
    headless: bool = Field(False, description="Run browser in headless mode (default: visible)")
    infinite_mode: bool = Field(False, description="Enable infinite mode")
    target_customer: str = Field("car", description="Target customer key for scraper pipeline")
    scraper_chance: float = Field(0.20, description="Probability of triggering scraper per scroll")
    model: str = Field("llama3:8b", description="Ollama model name")
    search_targets: Optional[list[str]] = Field(None, description="Extra search targets")
    search_chance: float = Field(0.30, description="Probability of random explore")
    profile_scroll_count_min: int = Field(3)
    profile_scroll_count_max: int = Field(8)
    browser_type: BROWSER_TYPE_CHOICES = Field("chromium", description="Browser engine: chromium, firefox, or webkit")


class CSVProfileVisitRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table (cookies loaded from DB)")
    csv_path: str = Field(..., description="Path to CSV file containing targets to visit")
    headless: bool = Field(False, description="Run browser in headless mode (default: visible)")
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
    headless: bool = Field(False, description="Run browser in headless mode (default: visible)")
    keep_open: bool = Field(False, description="Keep browser open after search (blocks until stopped)")
    browser_type: BROWSER_TYPE_CHOICES = Field("chromium", description="Browser engine: chromium, firefox, or webkit")


# ── Lead Generation Pipeline ────────────────────────────────────────

class LeadGenRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table (cookies loaded from DB)")
    target_interest: str = Field(..., description="Target interest / customer description")
    optional_keywords: Optional[list[str]] = Field(None, description="Additional search keywords")
    max_profiles: int = Field(50, ge=1, le=200, description="Max profiles to discover and analyze")
    headless: bool = Field(False, description="Run browser in headless mode")
    browser_type: BROWSER_TYPE_CHOICES = Field("chromium", description="Browser engine")
    model: str = Field("gpt-4.1-mini", description="OpenAI model for both AI brains")


class SmartLeadRequest(BaseModel):
    user_id: int = Field(..., description="User id from authentication table")
    cookie_id: Optional[int] = Field(None, description="Specific cookie row id – when set, uses that IG account instead of the latest")
    target_interest: str = Field(..., description="Target interest / customer description")
    optional_keywords: Optional[list[str]] = Field(None, description="Additional search keywords")
    max_profiles: int = Field(50, ge=1, le=200, description="Max profiles to discover and qualify")
    headless: bool = Field(False, description="Run browser in headless mode")
    browser_type: BROWSER_TYPE_CHOICES = Field("chromium", description="Browser engine")
    model: str = Field("gpt-4.1-mini", description="AI model for both brains")


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
