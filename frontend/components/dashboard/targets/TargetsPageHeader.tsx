"use client";

import { useI18n } from "@/contexts/I18nContext";

export function TargetsPageHeader() {
  const { t } = useI18n();
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">{t("targets.title")}</h1>
      <p className="text-muted-foreground">{t("targets.subtitle")}</p>
    </div>
  );
}
