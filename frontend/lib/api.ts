/**
 * API client — every frontend call goes through here.
 * Base URL: NEXT_PUBLIC_API_URL > NEXT_PUBLIC_LOCAL_API_URL > NEXT_PUBLIC_RPA_URL > localhost
 */

export const BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  process.env.NEXT_PUBLIC_LOCAL_API_URL ??
  process.env.NEXT_PUBLIC_RPA_URL ??
  "http://localhost:8000";

// ─── generic helpers ─────────────────────────────────────────────────────────

export async function get<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `GET ${path} failed (${res.status})`);
  }
  return res.json();
}

async function post<T = unknown>(
  path: string,
  body: unknown,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    ...init,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? `POST ${path} failed (${res.status})`);
  }
  return res.json();
}

// ─── types ───────────────────────────────────────────────────────────────────

export interface TargetConfig {
  name: string;
  hashtags: string[];
  niches: string[];
  keywords?: string[];
  use_target_identification_brain?: boolean;
}

export interface Target {
  key: string;
  name: string;
  config?: TargetConfig;
}

export interface TargetDetail {
  key: string;
  name: string;
  config: TargetConfig;
}

export interface SessionStatus {
  exists: boolean;
}

export interface UserInput {
  username: string;
  source?: string;
  bio?: string;
  post_summary?: string;
  profile_notes?: string;
  source_hashtag?: string;
}

export interface ClassifyResult {
  username: string;
  classification: string;
  score: number;
  signals_used: string[];
  uncertainties: string[];
  source?: string;
  source_hashtag?: string;
  target_customer?: string;
}

export interface AnalyzeResult {
  username: string;
  niche: string;
  relevance: number;
  source?: string;
  source_hashtag?: string;
  target_customer?: string;
}

export interface JobSummary {
  total_scraped: number;
  owners: number;
  commenters: number;
  filtered: number;
  csv_path: string | null;
}

export interface Job {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: string;
  target_customer: string;
  error: string | null;
  summary: JobSummary | null;
}

export interface JobResults {
  job_id: string;
  results: Record<string, unknown>[];
  summary: JobSummary | null;
}

// ─── Cookie / Session types ──────────────────────────────────────────────────

export interface CookieSnapshot {
  id: number;
  user_id: number;
  cookies: Record<string, unknown>[];
  created_at?: string;
  instagram_username?: string | null;
}

// ─── Account types ───────────────────────────────────────────────────────────

export interface Account {
  username: string;
  has_session: boolean;
}

// ─── Scrolling Automation types ──────────────────────────────────────────────

export interface ScrollRequest {
  user_id: number;
  duration: number;
  headless: boolean;
  infinite_mode: boolean;
  browser_type?: "chromium" | "firefox" | "webkit";
}

export interface CombinedScrollRequest extends ScrollRequest {
  search_targets?: string[];
  search_chance: number;
  profile_scroll_count_min: number;
  profile_scroll_count_max: number;
}

export interface ScraperScrollRequest extends CombinedScrollRequest {
  target_customer: string;
  scraper_chance: number;
  model: string;
}

export interface CSVProfileVisitRequest {
  user_id: number;
  csv_path: string;
  headless: boolean;
  scroll_count_min: number;
  scroll_count_max: number;
  delay_min: number;
  delay_max: number;
  like_chance: number;
  browser_type?: "chromium" | "firefox" | "webkit";
}

export interface AutomationTask {
  task_id: string;
  type: string;
  account: string; // derived from task message or metadata
  status: "pending" | "running" | "completed" | "failed" | "stopped";
  progress: string;
  message?: string;
  logs?: string[];
  result?: Record<string, unknown>;
  error: string | null;
}

// ─── Lead Generation types ───────────────────────────────────────────────────

export interface LeadGenRequest {
  user_id: number;
  target_interest: string;
  optional_keywords?: string[];
  max_profiles?: number;
  headless?: boolean;
  browser_type?: string;
  model?: string;
  cookie_id?: number;
}

export interface DiscoveryPlan {
  search_queries: string[];
  hashtags: string[];
  bio_keywords: string[];
  caption_keywords: string[];
  japanese_keywords: string[];
  seed_accounts: string[];
  priority_order: string[];
}

export interface LeadScores {
  age: number;
  work_lifestyle: number;
  occupation: number;
  location: number;
  side_job_signal: number;
}

export interface Lead {
  username: string;
  full_name: string;
  bio: string;
  followers_count: number;
  following_count: number;
  profile_image_url: string;
  detected_language: string;
  discovery_source: string;
  is_target: boolean;
  total_score: number;
  scores: LeadScores;
  confidence: "low" | "medium" | "high";
  reasoning: string;
}

export interface LeadGenResult {
  leads: Lead[];
  all_results: Lead[];
  total_scanned: number;
  total_qualified: number;
  profiles_followed?: number;
  discovery_plan: DiscoveryPlan;
  stats?: Record<string, number>;
}

// ─── Saved / Qualified Lead types ────────────────────────────────────────────

export interface SavedLead {
  id: number;
  cookie_id: number;
  user_id: number;
  niche: string;
  username: string;
  full_name: string;
  bio: string;
  followers_count: number;
  following_count: number;
  profile_image_url: string;
  detected_language: string;
  total_score: number;
  scores: LeadScores;
  confidence: "low" | "medium" | "high";
  reasoning: string;
  discovery_source: string;
  followed: boolean;
  created_at: string;
}

// ─── generic delete helper ───────────────────────────────────────────────────

async function del<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `DELETE ${path} failed (${res.status})`);
  }
  return res.json();
}

// ─── API functions ───────────────────────────────────────────────────────────

export const api = {
  // Health
  health: () => get<{ status: string }>("/api/health"),

  // Targets
  getTargets: () =>
    get<{ targets: string[]; details: Record<string, string> }>(
      "/scraper/targets",
    ).then((res) =>
      res.targets.map((key) => ({
        key,
        name: res.details[key] || key,
        config: undefined,
      })),
    ),
  getTarget: (key: string) => get<TargetDetail>(`/scraper/targets/${key}`),

  // Session (legacy)
  getSession: () => get<SessionStatus>("/api/session/exists"),

  // Session API (signup, login, Instagram cookie save)
  signup: (username: string, password: string) =>
    post<{ user_id: number; username: string; message: string }>(
      "/session/signup",
      {
        username,
        password,
      },
    ),

  login: (username: string, password: string) =>
    post<{ user_id: number; username: string; message?: string }>(
      "/session/login",
      {
        username,
        password,
      },
    ),

  saveSession: (user_id: number, timeout?: number) =>
    post<{ task_id: string; status: string; message: string }>(
      "/session/save",
      {
        user_id,
        timeout: timeout ?? 120,
        browser_type: "chromium",
      },
    ),

  checkSession: (user_id: number) =>
    get<{
      user_id: number;
      has_cookies: boolean;
      instagram_username?: string | null;
      message: string;
    }>(`/session/check/${user_id}`),

  getCookies: (userId: number, latest = true) =>
    get<{
      user_id: number;
      count?: number;
      cookies: CookieSnapshot | CookieSnapshot[];
    }>(`/session/cookies/${userId}?latest=${latest}`),

  deleteCookie: (cookieId: number) =>
    del<{ deleted: boolean; cookie_id: number }>(
      `/session/cookies/${cookieId}`,
    ),

  // Task polling for session save (uses /tasks/ not /api/automation/)
  getSessionTaskStatus: (taskId: string) =>
    get<{
      task_id: string;
      status: string;
      message?: string;
      result?: unknown;
    }>(`/tasks/${taskId}`),

  // Accounts (Use cookies as source of truth for now)
  // This helper emulates functionality by fetching cookies
  getAccounts: (userId: number) =>
    get<{ user_id: number; count: number; cookies: CookieSnapshot[] }>(
      `/session/cookies/${userId}?latest=false`,
    ).then((res) => ({
      accounts: (res.cookies || []).map((c) => {
        const ds_user = c.cookies.find((k: any) => k.name === "ds_user");
        return {
          username: (ds_user?.value as string) || "Unknown",
          has_session: true,
        };
      }),
    })),

  // Login a specific account (currently just verifies session)
  loginAccount: (username: string) =>
    Promise.resolve({
      task_id: "mock",
      status: "completed",
      message: "Assuming valid session",
    }),

  // Automation tasks (Scrolling)
  startBasicScroll: (req: ScrollRequest) =>
    post<{ task_id: string; status: string; message: string }>(
      "/scrolling/basic",
      req,
    ),

  startCombinedScroll: (req: CombinedScrollRequest) =>
    post<{ task_id: string; status: string; message: string }>(
      "/scrolling/combined",
      req,
    ),

  startScraperScroll: (req: ScraperScrollRequest) =>
    post<{ task_id: string; status: string; message: string }>(
      "/scrolling/scraper",
      req,
    ),

  startCsvProfileVisit: (req: CSVProfileVisitRequest) =>
    post<{ task_id: string; status: string; message: string }>(
      "/scrolling/csv-visit",
      req,
    ),

  stopAutomation: (taskId: string) =>
    post<{ task_id: string; message: string }>(
      `/tasks/${taskId}/stop`, // Use global task stop endpoint
      {},
    ),

  getTaskStatus: (taskId: string) => get<AutomationTask>(`/tasks/${taskId}`), // Use global task status endpoint
  getTasks: () => get<AutomationTask[]>("/tasks"), // Use global task list endpoint

  // Classify / Analyze
  classify: (users: UserInput[], model?: string) =>
    post<{ results: ClassifyResult[] }>("/api/classify", { users, model }),

  analyze: (users: UserInput[], target_customer: string, model?: string) =>
    post<{ results: AnalyzeResult[] }>("/api/analyze", {
      users,
      target_customer,
      model,
    }),

  // Export
  exportCsv: async (
    results: Record<string, unknown>[],
    target_customer: string,
  ) => {
    const res = await fetch(`${BASE}/api/export/csv`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ results, target_customer }),
    });
    if (!res.ok) throw new Error("CSV export failed");
    return res.blob();
  },

  // Scraper pipeline
  startScrape: (target_customer: string, max_commenters?: number) =>
    post<{ job_id: string; status: string }>("/api/scraper/run", {
      target_customer,
      max_commenters,
    }),

  getJobStatus: (jobId: string) => get<Job>(`/api/scraper/status/${jobId}`),
  getJobResults: (jobId: string) =>
    get<JobResults>(`/api/scraper/results/${jobId}`),
  getJobs: () => get<Job[]>("/api/jobs"),

  downloadExport: (jobId: string) =>
    fetch(`${BASE}/api/scraper/export/${jobId}`).then((r) => {
      if (!r.ok) throw new Error("Download failed");
      return r.blob();
    }),

  // Lead Generation
  generateDiscoveryPlan: (
    target_interest: string,
    optional_keywords?: string[],
    max_profiles?: number,
    model?: string,
    signal?: AbortSignal,
  ) =>
    post<{ status: string; discovery_plan: DiscoveryPlan }>(
      "/leads/discover",
      {
        target_interest,
        optional_keywords,
        max_profiles: max_profiles ?? 50,
        model: model ?? "gpt-4.1-mini",
      },
      { signal },
    ),

  qualifyProfiles: (profiles: Record<string, unknown>[], model?: string) =>
    post<{
      status: string;
      leads: Lead[];
      all_results: Lead[];
      total_scanned: number;
      total_qualified: number;
    }>("/leads/qualify", {
      profiles,
      model: model ?? "gpt-4.1-mini",
    }),

  startLeadGeneration: (req: LeadGenRequest) =>
    post<{ task_id: string; status: string; message: string }>("/leads/run", {
      ...req,
      max_profiles: req.max_profiles ?? 50,
      model: req.model ?? "gpt-4.1-mini",
    }),

  startSmartLeadGeneration: (req: LeadGenRequest) =>
    post<{ task_id: string; status: string; message: string }>(
      "/leads/smart-run",
      {
        ...req,
        max_profiles: req.max_profiles ?? 50,
        model: req.model ?? "gpt-4.1-mini",
      },
    ),

  // Saved / Qualified Leads
  getSavedLeads: (
    userId: number,
    niche?: string,
    cookieId?: number,
    limit?: number,
  ) => {
    const params = new URLSearchParams({ user_id: String(userId) });
    if (niche) params.set("niche", niche);
    if (cookieId) params.set("cookie_id", String(cookieId));
    if (limit) params.set("limit", String(limit));
    return get<{ status: string; leads: SavedLead[] }>(
      `/leads/saved?${params}`,
    );
  },

  getSavedNiches: (userId: number) =>
    get<{ status: string; niches: string[] }>(
      `/leads/saved/niches?user_id=${userId}`,
    ),

  deleteSavedLead: (leadId: number) =>
    del<{ status: string; deleted: Record<string, unknown> }>(
      `/leads/saved/${leadId}`,
    ),
};
