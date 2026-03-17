"use client";

import { useI18n } from "@/contexts/I18nContext";
import type { DiscoveryPlan } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Search } from "lucide-react";

interface DiscoveryPlanCardProps {
  plan: DiscoveryPlan;
}

export function DiscoveryPlanCard({ plan }: DiscoveryPlanCardProps) {
  const { t } = useI18n();

  const badgeSections = [
    { label: t("leads.discoveryPlan.searchQueries"), items: plan.search_queries ?? [] },
    { label: t("leads.discoveryPlan.hashtags"), items: (plan.hashtags ?? []).map((h) => `#${h.replace(/^#/, "")}`) },
    { label: t("leads.discoveryPlan.bioKeywords"), items: plan.bio_keywords ?? [] },
    { label: t("leads.discoveryPlan.japaneseKeywords"), items: plan.japanese_keywords ?? [] },
    { label: t("leads.discoveryPlan.seedAccounts"), items: (plan.seed_accounts ?? []).map((a) => `@${a.replace(/^@/, "")}`) },
  ].filter((s) => s.items.length > 0);

  const priorityOrder = plan.priority_order ?? [];
  const hasContent = badgeSections.length > 0 || priorityOrder.length > 0;

  if (!hasContent) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Search className="h-4 w-4" />
          {t("leads.discoveryPlan.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {badgeSections.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {badgeSections.map((section) => (
              <div key={section.label}>
                <p className="text-sm font-medium mb-1.5">{section.label}</p>
                <div className="flex flex-wrap gap-1.5">
                  {section.items.map((item, i) => (
                    <Badge key={i} variant="secondary" className="text-xs">{item}</Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {priorityOrder.length > 0 && (
          <div>
            <p className="text-sm font-medium mb-2">{t("leads.discoveryPlan.priorityOrder")}</p>
            <div className="flex flex-col gap-2">
              {priorityOrder.map((item, i) => (
                <div key={i} className="text-xs bg-secondary text-secondary-foreground px-2.5 py-1.5 rounded-md leading-relaxed whitespace-normal break-words">
                  {item}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
