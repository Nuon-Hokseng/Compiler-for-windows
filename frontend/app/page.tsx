"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { useSession, useJobs } from "@/lib/swr";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import { QuickActionsCard } from "@/components/dashboard/QuickActionsCard";
import { PipelineReportCard } from "@/components/dashboard/PipelineReportCard";

export default function DashboardPage() {
  const { user } = useAuth();
  const { t } = useI18n();

  const {
    data: session,
    error: sessionError,
    isLoading: sessionLoading,
    mutate: mutateSession,
  } = useSession(user?.user_id);

  const {
    data: jobs,
    error: jobsError,
    isLoading: jobsLoading,
    mutate: mutateJobs,
  } = useJobs();

  const loading = sessionLoading || jobsLoading;
  const error =
    !loading && (sessionError || jobsError) && !session?.has_cookies;

  const hasCookies = session?.has_cookies ?? false;
  const instagramUsername = session?.instagram_username ?? null;

  function handleRefresh() {
    mutateSession();
    mutateJobs();
  }

  return (
    <div className="space-y-8 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t("dashboard.title")}
          </h1>
          <p className="text-muted-foreground">{t("dashboard.subtitle")}</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={loading}
        >
          <RefreshCw
            className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`}
          />
          {t("common.refresh")}
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{t("dashboard.noAccountFound")}</AlertDescription>
        </Alert>
      )}
      <QuickActionsCard />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>
              {t("dashboard.instagramAccounts")}
            </CardDescription>
            <CardTitle className="flex items-center gap-2 text-lg">
              {loading ? (
                <Skeleton className="h-5 w-24" />
              ) : hasCookies ? (
                <>
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                  {instagramUsername
                    ? `@${instagramUsername}`
                    : t("dashboard.oneConnected")}
                </>
              ) : (
                <>
                  <XCircle className="h-5 w-5 text-destructive" />
                  {t("dashboard.noSessions")}
                </>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {hasCookies
                ? instagramUsername
                  ? t("dashboard.connectedReady", {
                      username: instagramUsername,
                    })
                  : t("dashboard.sessionConnected")
                : t("dashboard.addAccountPrompt")}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>{t("dashboard.backend")}</CardDescription>
            <CardTitle className="text-lg">
              {loading ? (
                <Skeleton className="h-5 w-16" />
              ) : error ? (
                t("common.offline")
              ) : (
                t("common.online")
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground break-all">
              {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}
            </p>
          </CardContent>
        </Card>
      </div>
      <PipelineReportCard />
    </div>
  );
}
