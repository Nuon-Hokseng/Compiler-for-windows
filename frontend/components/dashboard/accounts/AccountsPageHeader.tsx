"use client";

import { useI18n } from "@/contexts/I18nContext";
import { Button } from "@/components/ui/button";
import { UserPlus, RefreshCw } from "lucide-react";

interface AccountsPageHeaderProps {
  loading: boolean;
  onRefresh: () => void;
  onAddClick: () => void;
}

export function AccountsPageHeader({
  loading,
  onRefresh,
  onAddClick,
}: AccountsPageHeaderProps) {
  const { t } = useI18n();
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("accounts.title")}</h1>
        <p className="text-muted-foreground">{t("accounts.subtitle")}</p>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          {t("common.refresh")}
        </Button>
        <Button size="sm" onClick={onAddClick}>
          <UserPlus className="h-4 w-4 mr-2" />
          {t("common.addAccount")}
        </Button>
      </div>
    </div>
  );
}
