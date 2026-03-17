"use client";

import { useI18n } from "@/contexts/I18nContext";

export function ScrapePageHeader() {
  const { t } = useI18n();
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">{t("scrape.title")}</h1>
      <p className="text-muted-foreground">{t("scrape.subtitle")}</p>
    </div>
  );
}
