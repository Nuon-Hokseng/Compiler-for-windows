"use client";

import { useI18n } from "@/contexts/I18nContext";
import { usePersistState, clearPersistedState } from "@/lib/usePersistState";
import { LeadGenForm } from "@/components/dashboard/leads/LeadGenForm";
import { LeadGenResults } from "@/components/dashboard/leads/LeadGenResults";
import { DiscoveryPlanCard } from "@/components/dashboard/leads/DiscoveryPlanCard";
import { SavedLeads } from "@/components/dashboard/leads/SavedLeads";
import type { Lead, DiscoveryPlan } from "@/lib/api";
import { Crosshair } from "lucide-react";

const INIT_RESULTS = {
  leads: [] as Lead[],
  allResults: [] as Lead[],
  discoveryPlan: null as DiscoveryPlan | null,
  totalScanned: 0,
  totalQualified: 0,
};

export default function LeadsPage() {
  const { t } = useI18n();
  const [results, setResults] = usePersistState("leads_results", INIT_RESULTS);
  const { leads, allResults, discoveryPlan, totalScanned, totalQualified } = results;

  function updateResults(partial: Partial<typeof INIT_RESULTS>) {
    setResults((p) => ({ ...p, ...partial }));
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Crosshair className="h-6 w-6" />
          {t("leads.pageTitle")}
        </h1>
        <p className="text-muted-foreground">{t("leads.pageSubtitle")}</p>
      </div>

      <LeadGenForm
        onStart={() => {
          clearPersistedState("leads_results");
          setResults(INIT_RESULTS);
        }}
        onDiscoveryPlan={(plan) => updateResults({ discoveryPlan: plan })}
        onResults={(result) => {
          updateResults({
            leads: result.leads,
            allResults: result.all_results,
            discoveryPlan: result.discovery_plan,
            totalScanned: result.total_scanned,
            totalQualified: result.total_qualified,
          });
        }}
      />

      {discoveryPlan && <DiscoveryPlanCard plan={discoveryPlan} />}

      <LeadGenResults
        leads={leads}
        allResults={allResults}
        totalScanned={totalScanned}
        totalQualified={totalQualified}
      />

      <SavedLeads />
    </div>
  );
}
