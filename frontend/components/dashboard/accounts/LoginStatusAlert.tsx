"use client";

import { useI18n } from "@/contexts/I18nContext";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2 } from "lucide-react";

interface LoginStatusAlertProps {
  account: string;
  progress: string;
}

export function LoginStatusAlert({ account, progress }: LoginStatusAlertProps) {
  const { t } = useI18n();
  return (
    <Alert>
      <Loader2 className="h-4 w-4 animate-spin" />
      <AlertDescription>
        <span className="font-medium">@{account}</span> — {progress}{" "}
        <span className="text-muted-foreground text-xs">
          {t("accounts.loginStatus.browserHint")}
        </span>
      </AlertDescription>
    </Alert>
  );
}
