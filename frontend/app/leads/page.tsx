"use client";

import { useI18n } from "@/contexts/I18nContext";
import { SavedLeads } from "@/components/dashboard/leads/SavedLeads";
import { Star } from "lucide-react";

export default function LeadsPage() {
  const { t } = useI18n();

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Star className="h-6 w-6" />
          {t("leads.pageTitle")}
        </h1>
        <p className="text-muted-foreground">{t("leads.pageSubtitle")}</p>
      </div>

      <SavedLeads />
    </div>
  );
}
