"use client";

import { useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { usePersistState } from "@/lib/usePersistState";
import { type Account, type CookieSnapshot } from "@/lib/api";
import { useTargets, useCookies, useJobs } from "@/lib/swr";
import { Separator } from "@/components/ui/separator";
import { ScrapePageHeader } from "../../components/dashboard/scrape/ScrapePageHeader";
import { AccountSelectorCard } from "../../components/dashboard/scrape/AccountSelectorCard";
import { AutomationPanel } from "../../components/dashboard/scrape/AutomationPanel";
import { ScraperPipelineCard } from "../../components/dashboard/scrape/ScraperPipelineCard";
import { JobHistoryCard } from "../../components/dashboard/scrape/JobHistoryCard";

// Helper to extract username from cookie snapshot
function extractUsername(cookies: Record<string, unknown>[]): string {
  const ds_user = cookies.find((c) => c.name === "ds_user");
  return (ds_user?.value as string) || "Unknown";
}

export default function ScrapePage() {
  const { user } = useAuth();

  const { data: targets, isLoading: targetsLoading } = useTargets();
  const { data: cookiesData, isLoading: cookiesLoading } = useCookies(user?.user_id, false);
  const { data: jobs, isLoading: jobsLoading, mutate: mutateJobs } = useJobs();

  const [selectedAccount, setSelectedAccount] = usePersistState("scrape_selected_account", "");
  const [selectedTarget, setSelectedTarget] = usePersistState("scrape_selected_target", "");

  // Derive accounts from cookie snapshots
  const accounts: Account[] = (() => {
    if (!cookiesData) return [];
    const rawCookies = cookiesData.cookies;
    const snapshots = (
      Array.isArray(rawCookies) ? rawCookies : [rawCookies]
    ).filter(Boolean) as CookieSnapshot[];
    const accs: Account[] = snapshots.map((s) => ({
      username: s.instagram_username || extractUsername(s.cookies),
      has_session: true,
    }));
    // Deduplicate
    return Array.from(
      new Map(accs.map((item) => [item.username, item])).values(),
    );
  })();

  // Set defaults once data arrives
  useEffect(() => {
    if (targets && targets.length > 0 && !selectedTarget) {
      setSelectedTarget(targets[0].key);
    }
  }, [targets]);

  useEffect(() => {
    if (accounts.length > 0 && !selectedAccount) {
      setSelectedAccount(accounts[0].username);
    }
  }, [accounts.length]);

  if (!user) return null;

  return (
    <div className="space-y-6 max-w-5xl">
      <ScrapePageHeader />

      <AccountSelectorCard
        accounts={accounts}
        selectedAccount={selectedAccount}
        onAccountChange={setSelectedAccount}
      />

      <AutomationPanel
        userId={user.user_id}
        targets={targets ?? []}
        selectedTarget={selectedTarget}
        onTargetChange={setSelectedTarget}
        selectedAccount={selectedAccount}
      />

      <Separator />

      <ScraperPipelineCard
        targets={targets ?? []}
        selectedTarget={selectedTarget}
        onTargetChange={setSelectedTarget}
        onJobsRefetch={() => mutateJobs()}
      />

      <JobHistoryCard
        jobs={jobs ?? []}
        loading={jobsLoading}
        onRefresh={() => mutateJobs()}
      />
    </div>
  );
}
