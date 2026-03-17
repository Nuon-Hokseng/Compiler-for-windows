"use client";

import { useI18n } from "@/contexts/I18nContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import type { Account } from "@/lib/api";

interface AccountSelectorCardProps {
  accounts: Account[];
  selectedAccount: string;
  onAccountChange: (account: string) => void;
}

export function AccountSelectorCard({
  accounts, selectedAccount, onAccountChange,
}: AccountSelectorCardProps) {
  const { t } = useI18n();
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{t("scrape.accountCard.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {accounts.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("scrape.accountCard.noAccounts")}{" "}
            <a href="/accounts" className="underline text-primary">
              {t("scrape.accountCard.addOneFirst")}
            </a>
            .
          </p>
        ) : (
          <div className="flex items-center gap-3">
            <Select value={selectedAccount} onValueChange={onAccountChange}>
              <SelectTrigger className="w-64">
                <SelectValue placeholder={t("scrape.accountCard.selectAccount")} />
              </SelectTrigger>
              <SelectContent>
                {accounts.map((a) => (
                  <SelectItem key={a.username} value={a.username}>
                    @{a.username} {a.has_session ? "✓" : `(${t("common.noSession")})`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedAccount && (
              <Badge
                variant={
                  accounts.find((a) => a.username === selectedAccount)?.has_session
                    ? "default" : "secondary"
                }
              >
                {accounts.find((a) => a.username === selectedAccount)?.has_session
                  ? t("common.loggedIn") : t("common.loginNeeded")}
              </Badge>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
