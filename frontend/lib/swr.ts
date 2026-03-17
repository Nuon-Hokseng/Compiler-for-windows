/**
 * SWR hooks — cached data fetching for all GET endpoints.
 *
 * Data is kept in memory across page navigations so switching tabs
 * never triggers a redundant network request.
 */

import useSWR, { type SWRConfiguration } from "swr";
import { BASE, get } from "./api";
import type {
    Target,
    Job,
    CookieSnapshot,
    SavedLead,
} from "./api";

// ─── Generic fetcher used by every hook ──────────────────────────────────────

async function fetcher<T = unknown>(path: string): Promise<T> {
    return get<T>(path);
}

// Shared defaults: no refetch on window focus (automation tool, not a social feed)
const defaults: SWRConfiguration = {
    revalidateOnFocus: false,
};

// ─── Hooks ───────────────────────────────────────────────────────────────────

/** Session / cookie status for a user */
export function useSession(userId: number | undefined) {
    return useSWR<{
        user_id: number;
        has_cookies: boolean;
        instagram_username?: string | null;
        message: string;
    }>(
        userId != null ? `/session/check/${userId}` : null,
        fetcher,
        defaults,
    );
}

/** All cookie snapshots for a user */
export function useCookies(
    userId: number | undefined,
    latest = true,
) {
    return useSWR<{
        user_id: number;
        count?: number;
        cookies: CookieSnapshot | CookieSnapshot[];
    }>(
        userId != null
            ? `/session/cookies/${userId}?latest=${latest}`
            : null,
        fetcher,
        defaults,
    );
}

/** Target customers list (transformed to Target[]) */
export function useTargets() {
    return useSWR<Target[]>(
        "/scraper/targets",
        async (path: string) => {
            const res = await get<{
                targets: string[];
                details: Record<string, string>;
            }>(path);
            return res.targets.map((key) => ({
                key,
                name: res.details[key] || key,
                config: undefined,
            }));
        },
        defaults,
    );
}

/** Scraper jobs */
export function useJobs() {
    return useSWR<Job[]>("/api/jobs", fetcher, defaults);
}

/** Saved / qualified leads */
export function useSavedLeads(
    userId: number | undefined,
    niche?: string,
) {
    const params = userId != null ? new URLSearchParams({ user_id: String(userId) }) : null;
    if (params && niche) params.set("niche", niche);

    return useSWR<{ status: string; leads: SavedLead[] }>(
        params ? `/leads/saved?${params}` : null,
        fetcher,
        defaults,
    );
}

/** Available niche filter values */
export function useSavedNiches(userId: number | undefined) {
    return useSWR<{ status: string; niches: string[] }>(
        userId != null ? `/leads/saved/niches?user_id=${userId}` : null,
        fetcher,
        defaults,
    );
}
