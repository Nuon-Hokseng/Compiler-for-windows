"""
Account & Session Router
========================
Authentication (signup / login) for the web app.
Instagram browser sessions: open headful browser -> user logs in -> cookies
are exported and stored in the Supabase ``user_cookies`` table.
"""

import asyncio
import time
from dataclasses import dataclass, field
from functools import partial

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from api.shared.models import (
	SignupRequest,
	LoginRequest,
	LoginResponse,
	SessionRequest,
	TaskResponse,
	create_task,
	update_task,
	make_log_fn,
	TaskStatus,
)
from api.shared.db import (
	signup_user,
	login_user,
	get_user_by_id,
	insert_new_user_cookies,
	fetch_all_user_cookies,
	fetch_latest_user_cookies,
	delete_user_cookies,
)

router = APIRouter(prefix="/session", tags=["Account & Session"])


@dataclass
class HeadlessLoginRuntime:
	session_id: str
	user_id: int
	timeout: int
	browser_type: str
	status: str = "initializing"
	message: str = "Starting headless login session"
	current_url: str | None = None
	requires_2fa: bool = False
	created_at: float = field(default_factory=time.time)
	updated_at: float = field(default_factory=time.time)
	credentials: tuple[str, str] | None = None
	two_factor_code: str | None = None
	credentials_event: asyncio.Event = field(default_factory=asyncio.Event)
	two_factor_event: asyncio.Event = field(default_factory=asyncio.Event)
	stop_requested: bool = False
	cookie_row_id: int | None = None
	cookie_count: int = 0
	instagram_username: str | None = None
	error: str | None = None


class HeadlessStartRequest(BaseModel):
	user_id: int = Field(..., description="User id from the authentication table")
	timeout: int = Field(180, ge=60, le=900, description="Session timeout in seconds")
	browser_type: str = Field("chrome", description="Browser engine")


class HeadlessCredentialRequest(BaseModel):
	identifier: str = Field(..., min_length=1, description="Instagram username / email")
	password: str = Field(..., min_length=1, description="Instagram password")


class HeadlessTwoFactorRequest(BaseModel):
	code: str = Field(..., min_length=4, description="2FA verification code")


_headless_sessions: dict[str, HeadlessLoginRuntime] = {}


def _set_headless_state(runtime: HeadlessLoginRuntime, *, status: str, message: str) -> None:
	runtime.status = status
	runtime.message = message
	runtime.updated_at = time.time()

	status_map = {
		"completed": TaskStatus.COMPLETED,
		"failed": TaskStatus.FAILED,
		"cancelled": TaskStatus.STOPPED,
	}
	update_task(
		runtime.session_id,
		status=status_map.get(status, TaskStatus.RUNNING),
		message=message,
		result={
			"current_url": runtime.current_url,
			"requires_2fa": runtime.requires_2fa,
			"cookie_row_id": runtime.cookie_row_id,
			"cookie_count": runtime.cookie_count,
			"instagram_username": runtime.instagram_username,
			"error": runtime.error,
		},
	)


def _headless_snapshot(runtime: HeadlessLoginRuntime) -> dict:
	return {
		"session_id": runtime.session_id,
		"user_id": runtime.user_id,
		"status": runtime.status,
		"message": runtime.message,
		"current_url": runtime.current_url,
		"requires_2fa": runtime.requires_2fa,
		"created_at": runtime.created_at,
		"updated_at": runtime.updated_at,
		"cookie_row_id": runtime.cookie_row_id,
		"cookie_count": runtime.cookie_count,
		"instagram_username": runtime.instagram_username,
		"error": runtime.error,
	}


async def _fill_first_visible(page, selectors: list[str], value: str) -> bool:
	for selector in selectors:
		loc = page.locator(selector).first
		try:
			if await loc.count() > 0 and await loc.is_visible(timeout=1500):
				await loc.fill(value)
				return True
		except Exception:
			continue
	return False


async def _fill_first_present_js(page, selectors: list[str], value: str) -> bool:
	for selector in selectors:
		try:
			filled = await page.evaluate(
				"""
				({ selector, value }) => {
					const el = document.querySelector(selector);
					if (!el) return false;
					el.focus();
					el.value = value;
					el.dispatchEvent(new Event('input', { bubbles: true }));
					el.dispatchEvent(new Event('change', { bubbles: true }));
					return true;
				}
				""",
				{"selector": selector, "value": value},
			)
			if filled:
				return True
		except Exception:
			continue
	return False


async def _click_first_visible(page, selectors: list[str]) -> bool:
	for selector in selectors:
		loc = page.locator(selector).first
		try:
			if await loc.count() > 0 and await loc.is_visible(timeout=1500):
				await loc.click()
				return True
		except Exception:
			continue
	return False


async def _click_first_present_js(page, selectors: list[str]) -> bool:
	for selector in selectors:
		try:
			clicked = await page.evaluate(
				"""
				(selector) => {
					const el = document.querySelector(selector);
					if (!el) return false;
					el.click();
					return true;
				}
				""",
				selector,
			)
			if clicked:
				return True
		except Exception:
			continue
	return False


async def _dismiss_cookie_banner_if_present(page) -> None:
	selectors = [
		"button:has-text('Allow all cookies')",
		"button:has-text('Allow all')",
		"button:has-text('Only allow essential cookies')",
		"button:has-text('Accept')",
		"button:has-text('Accept all')",
	]
	for selector in selectors:
		try:
			loc = page.locator(selector).first
			if await loc.count() > 0 and await loc.is_visible(timeout=1000):
				await loc.click()
				await asyncio.sleep(0.3)
				return
		except Exception:
			continue


async def _wait_for_login_form(page, timeout_ms: int = 20000) -> bool:
	try:
		await page.wait_for_selector(
			"input[name='username'], input[name='email'], input[autocomplete*='username'], input[type='password']",
			timeout=timeout_ms,
		)
		return True
	except Exception:
		return False


async def _submit_login_credentials(runtime: HeadlessLoginRuntime, page) -> None:
	identifier, password = runtime.credentials or ("", "")
	if not identifier or not password:
		raise RuntimeError("Missing credentials")

	try:
		await page.wait_for_load_state("domcontentloaded", timeout=10000)
	except Exception:
		pass

	await _dismiss_cookie_banner_if_present(page)
	form_ready = await _wait_for_login_form(page, timeout_ms=20000)
	if not form_ready:
		try:
			await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded", timeout=20000)
			await _dismiss_cookie_banner_if_present(page)
			form_ready = await _wait_for_login_form(page, timeout_ms=20000)
		except Exception:
			pass

	if not form_ready:
		raise RuntimeError("Instagram login form not ready yet")

	username_ok = await _fill_first_visible(
		page,
		[
			"input[name='username']",
			"input[name='email']",
			"input[aria-label='Phone number, username, or email']",
			"input[autocomplete='username']",
			"input[autocomplete*='username']",
			"input[autocomplete*='webauthn']",
		],
		identifier,
	)
	password_ok = await _fill_first_visible(
		page,
		[
			"input[name='password']",
			"input[type='password']",
			"input[autocomplete='current-password']",
		],
		password,
	)

	if not username_ok:
		username_ok = await _fill_first_present_js(
			page,
			[
				"input[name='username']",
				"input[name='email']",
				"input[aria-label='Phone number, username, or email']",
				"input[autocomplete='username']",
				"input[autocomplete*='username']",
				"input[autocomplete*='webauthn']",
			],
			identifier,
		)
	if not password_ok:
		password_ok = await _fill_first_present_js(
			page,
			[
				"input[name='password']",
				"input[type='password']",
				"input[autocomplete='current-password']",
			],
			password,
		)

	if not username_ok or not password_ok:
		try:
			inferred = await page.evaluate(
				"""
				({ identifier, password }) => {
					const inputs = Array.from(document.querySelectorAll('input'));
					const visible = inputs.filter((el) => {
						if (el.type === 'hidden') return false;
						const style = window.getComputedStyle(el);
						const rect = el.getBoundingClientRect();
						return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
					});

					const passwordInput =
						visible.find((el) => (el.type || '').toLowerCase() === 'password') ||
						inputs.find((el) => (el.type || '').toLowerCase() === 'password');

					const userCandidates = (visible.length ? visible : inputs).filter((el) => {
						const t = (el.type || '').toLowerCase();
						return ['username', 'email', 'tel', 'text'].includes(t);
					});

					const scoreUser = (el) => {
						const n = (el.name || '').toLowerCase();
						const ac = (el.autocomplete || '').toLowerCase();
						const id = (el.id || '').toLowerCase();
						const al = (el.getAttribute('aria-label') || '').toLowerCase();
						const ph = (el.getAttribute('placeholder') || '').toLowerCase();
						let s = 0;
						if (n === 'username') s += 120;
						if (n === 'email') s += 110;
						if (ac.includes('username')) s += 100;
						if (ac.includes('webauthn')) s += 20;
						if (al.includes('username')) s += 80;
						if (al.includes('email')) s += 70;
						if (al.includes('phone')) s += 40;
						if (id.includes('user') || id.includes('email')) s += 30;
						if (ph.includes('username') || ph.includes('email') || ph.includes('phone')) s += 20;
						return s;
					};

					userCandidates.sort((a, b) => scoreUser(b) - scoreUser(a));
					const userInput = userCandidates[0] || null;

					if (!userInput || !passwordInput) {
						return { ok: false };
					}

					const setVal = (el, val) => {
						el.focus();
						el.value = val;
						el.dispatchEvent(new Event('input', { bubbles: true }));
						el.dispatchEvent(new Event('change', { bubbles: true }));
					};

					setVal(userInput, identifier);
					setVal(passwordInput, password);

					const form = passwordInput.form || userInput.form || passwordInput.closest('form') || userInput.closest('form');
					if (form) {
						if (typeof form.requestSubmit === 'function') form.requestSubmit();
						else form.submit();
						return { ok: true };
					}

					const submitBtn =
						document.querySelector("button[type='submit']") ||
						Array.from(document.querySelectorAll('button, div[role=\"button\"]')).find((el) => {
							const t = (el.textContent || '').trim().toLowerCase();
							return t === 'log in' || t === 'login' || t.includes('log in');
						});

					if (submitBtn) {
						submitBtn.click();
						return { ok: true };
					}

					passwordInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
					passwordInput.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', bubbles: true }));
					return { ok: true };
				}
				""",
				{"identifier": identifier, "password": password},
			)
			if inferred and inferred.get("ok"):
				return
		except Exception:
			pass

	if not username_ok or not password_ok:
		try:
			input_count = await page.locator("input").count()
		except Exception:
			input_count = -1
		raise RuntimeError(f"Could not find Instagram login form fields (input_count={input_count})")

	clicked = await _click_first_visible(
		page,
		[
			"button[type='submit']",
			"button:has-text('Log in')",
			"button:has-text('Log In')",
			"div[role='button']:has-text('Log in')",
		],
	)
	if not clicked:
		clicked = await _click_first_present_js(
			page,
			[
				"button[type='submit']",
				"button:has-text('Log in')",
				"button:has-text('Log In')",
				"div[role='button']:has-text('Log in')",
			],
		)
	if not clicked:
		raise RuntimeError("Could not submit Instagram login form")


async def _submit_two_factor_code(runtime: HeadlessLoginRuntime, page) -> None:
	code = (runtime.two_factor_code or "").strip()
	if not code:
		raise RuntimeError("Missing two-factor code")

	code_ok = await _fill_first_visible(
		page,
		[
			"input[name='verificationCode']",
			"input[name='security_code']",
			"input[autocomplete='one-time-code']",
			"input[inputmode='numeric']",
		],
		code,
	)
	if not code_ok:
		raise RuntimeError("Could not find 2FA input field")

	clicked = await _click_first_visible(
		page,
		[
			"button:has-text('Confirm')",
			"button:has-text('Continue')",
			"button[type='submit']",
		],
	)
	if not clicked:
		raise RuntimeError("Could not submit 2FA code")


async def _headless_save_session_worker(runtime: HeadlessLoginRuntime) -> None:
	from browser.session import _extract_username_from_browser
	from browser.launcher import launch_browser_async

	login_url = "https://www.instagram.com/accounts/login/"
	browser = None
	context = None

	def _remaining_seconds(deadline: float) -> float:
		return max(0.0, deadline - time.monotonic())

	try:
		from playwright.async_api import async_playwright

		async with async_playwright() as p:
			browser = await launch_browser_async(
				p,
				browser_type=runtime.browser_type,
				headless=False,
			)
			context = await browser.new_context(
				viewport={"width": 1280, "height": 720},
				locale="en-US",
				permissions=[],
			)
			await context.clear_cookies()

			page = await context.new_page()

			def _on_main_navigation(frame):
				if frame == page.main_frame:
					runtime.current_url = frame.url
					runtime.updated_at = time.time()

			page.on("framenavigated", _on_main_navigation)

			await page.goto(login_url, wait_until="domcontentloaded")
			runtime.current_url = page.url
			_set_headless_state(runtime, status="awaiting_credentials", message="Ready for Instagram credentials")

			deadline = time.monotonic() + runtime.timeout
			await asyncio.wait_for(runtime.credentials_event.wait(), timeout=_remaining_seconds(deadline))

			if runtime.stop_requested:
				_set_headless_state(runtime, status="cancelled", message="Login cancelled")
				return

			_set_headless_state(runtime, status="submitting_credentials", message="Submitting credentials")
			await _submit_login_credentials(runtime, page)

			_set_headless_state(runtime, status="waiting_login_result", message="Waiting for login result")
			requires_2fa_reported = False
			credential_retry_count = 0
			max_credential_retries = 3
			submit_started_at = time.monotonic()

			while _remaining_seconds(deadline) > 0:
				if runtime.stop_requested:
					_set_headless_state(runtime, status="cancelled", message="Login cancelled")
					return

				current_url = page.url
				runtime.current_url = current_url
				runtime.updated_at = time.time()

				cookies = await context.cookies([
					"https://www.instagram.com",
					"https://instagram.com",
					"https://i.instagram.com",
				])
				if any(c.get("name") in ("ds_user", "ds_user_id") for c in cookies):
					instagram_username = await _extract_username_from_browser(context, page, cookies)
					loop = asyncio.get_running_loop()
					row = await loop.run_in_executor(
						None,
						partial(insert_new_user_cookies, runtime.user_id, cookies, instagram_username),
					)
					runtime.cookie_row_id = row.get("id")
					runtime.cookie_count = len(cookies)
					runtime.instagram_username = instagram_username
					_set_headless_state(runtime, status="completed", message="Instagram cookies saved")
					return

				if "facebook.com" in current_url.lower():
					runtime.error = "Facebook login is not supported in headless mode"
					_set_headless_state(runtime, status="failed", message=runtime.error)
					return

				challenge_url = any(path in current_url for path in ("/challenge", "/two_factor"))
				challenge_input = False
				try:
					challenge_input = await page.locator(
						"input[name='verificationCode'], input[name='security_code'], input[autocomplete='one-time-code']"
					).count() > 0
				except Exception:
					challenge_input = False

				if challenge_url or challenge_input:
					runtime.requires_2fa = True
					if not requires_2fa_reported:
						requires_2fa_reported = True
						_set_headless_state(runtime, status="awaiting_2fa", message="2FA code required")

					if runtime.two_factor_event.is_set():
						runtime.two_factor_event.clear()
						_set_headless_state(runtime, status="submitting_2fa", message="Submitting 2FA code")
						await _submit_two_factor_code(runtime, page)
						_set_headless_state(runtime, status="waiting_login_result", message="Verifying 2FA code")
						submit_started_at = time.monotonic()

				on_login_page = (
					"instagram.com" in current_url.lower()
					and "/accounts/login" in current_url.lower()
				)
				if on_login_page and not challenge_url and not challenge_input:
					elapsed_since_submit = time.monotonic() - submit_started_at

					login_error = None
					try:
						login_error = await page.evaluate(
							"""
							() => {
								const candidates = [
									...document.querySelectorAll('[role="alert"]'),
									...document.querySelectorAll('div'),
								];
								const phrases = [
									'incorrect',
									'wrong password',
									'try again',
									'invalid',
									'problem with your request',
									'suspicious login attempt',
									'couldn\'t log you in',
									'challenge required',
								];
								for (const el of candidates) {
									const txt = (el.textContent || '').trim();
									if (!txt) continue;
									const low = txt.toLowerCase();
									if (phrases.some((p) => low.includes(p))) {
										return txt.slice(0, 220);
									}
								}
								return null;
							}
							"""
						)
					except Exception:
						login_error = None

					should_reset_to_credentials = bool(login_error) or elapsed_since_submit >= 15
					if should_reset_to_credentials:
						if credential_retry_count >= max_credential_retries:
							runtime.error = (
								f"Login did not proceed after {max_credential_retries} attempts"
								if not login_error
								else f"Login rejected: {login_error}"
							)
							_set_headless_state(runtime, status="failed", message=runtime.error)
							return

						credential_retry_count += 1
						reason = login_error or "Still on login page after submit"
						_set_headless_state(
							runtime,
							status="awaiting_credentials",
							message=f"{reason}. Please check credentials and submit again.",
						)
						runtime.credentials_event.clear()
						try:
							await asyncio.wait_for(
								runtime.credentials_event.wait(),
								timeout=_remaining_seconds(deadline),
							)
						except asyncio.TimeoutError:
							runtime.error = "Login timed out"
							_set_headless_state(runtime, status="failed", message=runtime.error)
							return

						if runtime.stop_requested:
							_set_headless_state(runtime, status="cancelled", message="Login cancelled")
							return

						_set_headless_state(runtime, status="submitting_credentials", message="Submitting credentials")
						await _submit_login_credentials(runtime, page)
						_set_headless_state(runtime, status="waiting_login_result", message="Waiting for login result")
						submit_started_at = time.monotonic()

				await asyncio.sleep(1)

			runtime.error = "Login timed out"
			_set_headless_state(runtime, status="failed", message=runtime.error)

	except asyncio.TimeoutError:
		runtime.error = "Login timed out"
		_set_headless_state(runtime, status="failed", message=runtime.error)
	except Exception as e:
		runtime.error = str(e)
		_set_headless_state(runtime, status="failed", message=str(e))
	finally:
		try:
			if context:
				await context.close()
		except Exception:
			pass
		try:
			if browser:
				await browser.close()
		except Exception:
			pass


# ── Web-app authentication ──────────────────────────────────────────

@router.post("/signup")
async def signup(req: SignupRequest):
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
	user = login_user(req.username, req.password)
	if not user:
		raise HTTPException(status_code=401, detail="Invalid username or password")
	return LoginResponse(user_id=user["id"], username=user["username"])


# ── Instagram session (legacy headful save) ───────────────────────

async def _save_session_worker(task_id: str, user_id: int, timeout: int, browser_type: str):
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
			update_task(task_id, status=TaskStatus.FAILED, message="No cookies extracted")
			return

		loop = asyncio.get_running_loop()
		row = await loop.run_in_executor(
			None,
			partial(insert_new_user_cookies, user_id, cookies, instagram_username),
		)
		cookie_row_id = row.get("id", "?")

		update_task(
			task_id,
			status=TaskStatus.COMPLETED,
			message=f"Instagram cookies saved - row id={cookie_row_id}",
			result={"cookie_row_id": cookie_row_id, "cookie_count": len(cookies)},
		)
	except Exception as e:
		update_task(task_id, status=TaskStatus.FAILED, message=str(e))


@router.post("/save", response_model=TaskResponse)
async def save_session(req: SessionRequest, bg: BackgroundTasks):
	user = get_user_by_id(req.user_id)
	if not user:
		raise HTTPException(status_code=404, detail=f"User id {req.user_id} not found in authentication table")

	task = create_task(f"IG login -> user {req.user_id} ({user['username']})")
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


# ── Instagram session (new headless lifecycle) ────────────────────

@router.post("/save/headless/start")
async def start_headless_session(req: HeadlessStartRequest):
	user = get_user_by_id(req.user_id)
	if not user:
		raise HTTPException(status_code=404, detail=f"User id {req.user_id} not found in authentication table")

	session_id = create_task(f"Headless IG login -> user {req.user_id} ({user['username']})").task_id
	runtime = HeadlessLoginRuntime(
		session_id=session_id,
		user_id=req.user_id,
		timeout=req.timeout,
		browser_type=req.browser_type,
	)
	_headless_sessions[session_id] = runtime
	update_task(session_id, status=TaskStatus.RUNNING, message="Headless login session created")

	asyncio.create_task(_headless_save_session_worker(runtime))
	return {
		"session_id": session_id,
		"status": runtime.status,
		"message": "Headless session started",
	}


@router.get("/save/headless/{session_id}")
async def get_headless_session_status(session_id: str):
	runtime = _headless_sessions.get(session_id)
	if not runtime:
		raise HTTPException(status_code=404, detail="Headless session not found")

	if runtime.status in {"completed", "failed", "cancelled"}:
		mapped = {
			"completed": TaskStatus.COMPLETED,
			"failed": TaskStatus.FAILED,
			"cancelled": TaskStatus.STOPPED,
		}[runtime.status]
		update_task(
			session_id,
			status=mapped,
			message=runtime.message,
			result={
				"cookie_row_id": runtime.cookie_row_id,
				"cookie_count": runtime.cookie_count,
				"instagram_username": runtime.instagram_username,
				"current_url": runtime.current_url,
				"requires_2fa": runtime.requires_2fa,
			},
		)
	else:
		update_task(session_id, status=TaskStatus.RUNNING, message=runtime.message)

	return _headless_snapshot(runtime)


@router.post("/save/headless/{session_id}/credentials")
async def submit_headless_credentials(session_id: str, req: HeadlessCredentialRequest):
	runtime = _headless_sessions.get(session_id)
	if not runtime:
		raise HTTPException(status_code=404, detail="Headless session not found")
	if runtime.status not in {"awaiting_credentials", "submitting_credentials", "waiting_login_result"}:
		raise HTTPException(status_code=409, detail=f"Cannot submit credentials in state '{runtime.status}'")

	runtime.credentials = (req.identifier.strip(), req.password)
	runtime.credentials_event.set()
	return {"session_id": session_id, "status": runtime.status, "message": "Credentials submitted"}


@router.post("/save/headless/{session_id}/2fa")
async def submit_headless_two_factor(session_id: str, req: HeadlessTwoFactorRequest):
	runtime = _headless_sessions.get(session_id)
	if not runtime:
		raise HTTPException(status_code=404, detail="Headless session not found")
	if runtime.status not in {"awaiting_2fa", "submitting_2fa", "waiting_login_result"}:
		raise HTTPException(status_code=409, detail=f"Cannot submit 2FA code in state '{runtime.status}'")

	runtime.two_factor_code = req.code.strip()
	runtime.two_factor_event.set()
	return {"session_id": session_id, "status": runtime.status, "message": "2FA code submitted"}


@router.post("/save/headless/{session_id}/cancel")
async def cancel_headless_session(session_id: str):
	runtime = _headless_sessions.get(session_id)
	if not runtime:
		raise HTTPException(status_code=404, detail="Headless session not found")

	runtime.stop_requested = True
	_set_headless_state(runtime, status="cancelled", message="Login cancelled by user")
	update_task(session_id, status=TaskStatus.STOPPED, message="Headless login cancelled")
	return {"session_id": session_id, "status": runtime.status, "message": runtime.message}


# ── Cookie retrieval endpoints ─────────────────────────────────────

@router.get("/cookies/{user_id}")
async def get_cookies(user_id: int, latest: bool = True):
	try:
		if latest:
			row = fetch_latest_user_cookies(user_id)
			if not row:
				raise HTTPException(status_code=404, detail="No cookies found for this user")
			return {"user_id": user_id, "cookies": row}
		rows = fetch_all_user_cookies(user_id)
		if not rows:
			return {"user_id": user_id, "count": 0, "cookies": []}
		return {"user_id": user_id, "count": len(rows), "cookies": rows}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cookies/{cookie_id}")
async def remove_cookie(cookie_id: int):
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
	row = fetch_latest_user_cookies(user_id)
	has_cookies = bool(row and row.get("cookies"))
	instagram_username = None
	if has_cookies and row:
		instagram_username = row.get("instagram_username")
		if not instagram_username:
			instagram_username = _extract_instagram_username_from_cookies(row.get("cookies"))
	return {
		"user_id": user_id,
		"has_cookies": has_cookies,
		"instagram_username": instagram_username,
		"message": "Cookies ready" if has_cookies else "No cookies - call POST /session/save first",
	}

