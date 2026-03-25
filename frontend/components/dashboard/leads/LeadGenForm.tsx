"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  api,
  type CookieSnapshot,
  type LeadGenResult,
  type DiscoveryPlan,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { useBeforeUnload } from "@/lib/useBeforeUnload";
import { usePersistState } from "@/lib/usePersistState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, Rocket, StopCircle } from "lucide-react";

interface LeadGenFormProps {
  onResults: (result: LeadGenResult) => void;
  onStart?: () => void;
  onDiscoveryPlan?: (plan: DiscoveryPlan) => void;
  campaignId?: number;
  fixedTargetInterest?: string;
  fixedKeywords?: string;
  fixedMaxProfiles?: number;
}

const INIT_FORM = {
  targetInterest: "",
  keywords: "",
  maxProfiles: 50,
  model: "claude-sonnet-4-6",
};

export function LeadGenForm({
  onResults,
  onStart,
  onDiscoveryPlan,
  campaignId,
  fixedTargetInterest,
  fixedKeywords,
  fixedMaxProfiles,
}: LeadGenFormProps) {
  const { user } = useAuth();
  const { t } = useI18n();
  const [form, setForm] = usePersistState("leads_form", INIT_FORM);
  const targetInterest = fixedTargetInterest ?? form.targetInterest;
  const keywords = fixedKeywords ?? form.keywords;
  const maxProfiles = fixedMaxProfiles ?? form.maxProfiles;
  const { model } = form;
  const setTargetInterest = (v: string) =>
    setForm((p) => ({ ...p, targetInterest: v }));
  const setKeywords = (v: string) => setForm((p) => ({ ...p, keywords: v }));
  const setMaxProfiles = (v: number) =>
    setForm((p) => ({ ...p, maxProfiles: v }));
  const setModel = (v: string) => setForm((p) => ({ ...p, model: v }));
  const [running, setRunning] = useState(false);
  useBeforeUnload(running);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState<string[]>([]);
  const [cookies, setCookies] = useState<CookieSnapshot[]>([]);
  const [selectedCookieId, setSelectedCookieId] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const campaignTaskStorageKey = campaignId
    ? `campaign_active_task_${campaignId}`
    : null;
  const campaignCookieStorageKey = campaignId
    ? `campaign_selected_cookie_${campaignId}`
    : null;

  const persistCampaignTask = (id: string | null) => {
    if (!campaignTaskStorageKey) return;
    if (id) localStorage.setItem(campaignTaskStorageKey, id);
    else localStorage.removeItem(campaignTaskStorageKey);
  };

  const persistCampaignCookie = (id: number | null) => {
    if (!campaignCookieStorageKey) return;
    if (id !== null) localStorage.setItem(campaignCookieStorageKey, String(id));
    else localStorage.removeItem(campaignCookieStorageKey);
  };

  useEffect(() => {
    if (!user) return;
    api
      .getCookies(user.user_id, false)
      .then((res) => {
        const list = Array.isArray(res.cookies)
          ? res.cookies
          : res.cookies
            ? [res.cookies]
            : [];
        setCookies(list);
        if (list.length === 0) {
          setSelectedCookieId(null);
          return;
        }

        if (campaignCookieStorageKey) {
          const savedRaw = localStorage.getItem(campaignCookieStorageKey);
          const savedId = savedRaw ? Number(savedRaw) : null;
          const matched =
            savedId !== null && Number.isFinite(savedId)
              ? list.find((c) => c.id === savedId)
              : undefined;
          if (matched) {
            setSelectedCookieId(matched.id);
            return;
          }
        }

        setSelectedCookieId(list[0].id);
      })
      .catch(() => {});
  }, [user, campaignCookieStorageKey]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  function startPolling(activeTaskId: string) {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    pollRef.current = setInterval(async () => {
      try {
        const task = await api.getTaskStatus(activeTaskId);
        if (task.logs && task.logs.length > 0) setProgress(task.logs);
        if (task.result) {
          const partial = task.result as Record<string, unknown>;
          if (partial.discovery_plan && onDiscoveryPlan)
            onDiscoveryPlan(partial.discovery_plan as DiscoveryPlan);
        }
        if (
          task.status === "completed" ||
          task.status === "failed" ||
          task.status === "stopped"
        ) {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          setRunning(false);
          setTaskId(null);
          persistCampaignTask(null);
          if (task.status === "completed" && task.result) {
            const result = task.result as unknown as LeadGenResult;
            onResults(result);
            const followed = result.profiles_followed ?? 0;
            toast.success(
              `Found ${result.total_qualified} leads from ${result.total_scanned} profiles` +
                (followed > 0 ? ` (${followed} followed)` : ""),
            );
          } else if (task.status === "failed") {
            toast.error(task.message || "Pipeline failed");
          } else if (task.status === "stopped" && task.result) {
            const result = task.result as unknown as LeadGenResult;
            if (result.leads && result.leads.length > 0) {
              onResults(result);
              toast.info(
                `${t("leads.form.pipelineStopped")} — ${result.total_qualified} leads`,
              );
            } else {
              toast.info(t("leads.form.pipelineStopped"));
            }
          } else {
            toast.info(t("leads.form.pipelineStopped"));
          }
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        if (msg.includes("Task not found") || msg.includes("404")) {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          setRunning(false);
          setTaskId(null);
          persistCampaignTask(null);
          toast.error(
            "Task lost. The server may have restarted due to memory limits. Please try again.",
          );
        }
      }
    }, 2000);
  }

  useEffect(() => {
    if (!campaignId || !user?.user_id) return;

    let mounted = true;
    const restore = async () => {
      try {
        const status = await api.getCampaignRunStatus(campaignId, user.user_id);
        if (!mounted || !status.run?.task_id) return;

        const id = status.run.task_id;
        if (status.active) {
          setTaskId(id);
          setRunning(true);
          setProgress((prev) =>
            prev.length > 0 ? prev : ["Reconnected to running campaign..."],
          );
          persistCampaignTask(id);
          startPolling(id);
        }
      } catch {
        // Non-fatal: campaign may not have an active run.
      }
    };

    restore();
    return () => {
      mounted = false;
    };
  }, [campaignId, user?.user_id]);

  async function startPipeline() {
    if (!targetInterest.trim()) {
      toast.error(t("leads.form.enterTarget"));
      return;
    }
    const userId = user?.user_id;
    if (!userId) {
      toast.error(t("leads.form.noAccountError"));
      return;
    }

    setRunning(true);
    setProgress([]);
    setTaskId(null);
    if (onStart) onStart();

    try {
      const optionalKeywords = keywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);
      const res = await api.startSmartLeadGeneration({
        user_id: userId,
        target_interest: targetInterest,
        optional_keywords:
          optionalKeywords.length > 0 ? optionalKeywords : undefined,
        max_profiles: maxProfiles,
        model,
        cookie_id: selectedCookieId ?? undefined,
        campaign_id: campaignId,
      });

      setTaskId(res.task_id);
      persistCampaignTask(res.task_id);
      toast.success(t("leads.form.pipelineStarted"));
      setProgress((prev) => [...prev, "Pipeline started..."]);
      startPolling(res.task_id);
    } catch (e: unknown) {
      setRunning(false);
      toast.error(e instanceof Error ? e.message : "Failed to start pipeline");
    }
  }

  async function stopPipeline() {
    setRunning(false);
    setProgress((prev) => [...prev, t("leads.form.stoppingPipeline")]);
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (taskId) {
      try {
        if (campaignId && user?.user_id)
          await api.stopCampaignRun(campaignId, user.user_id);
        else await api.stopAutomation(taskId);
      } catch {
        /* Ignore */
      }
      persistCampaignTask(null);
      setTaskId(null);
    }
    toast.info(t("leads.form.pipelineStopped"));
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Rocket className="h-5 w-5" />
          {t("leads.form.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {cookies.length > 0 && (
          <div className="space-y-2">
            <Label>{t("leads.form.instagramAccount")}</Label>
            <Select
              value={String(selectedCookieId ?? "")}
              onValueChange={(v) => {
                const id = Number(v);
                setSelectedCookieId(id);
                persistCampaignCookie(id);
              }}>
              <SelectTrigger>
                <SelectValue placeholder={t("leads.form.selectAccount")} />
              </SelectTrigger>
              <SelectContent>
                {cookies.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.instagram_username
                      ? `@${c.instagram_username}`
                      : `Account #${c.id}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {cookies.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {t("leads.form.noSessions")}{" "}
            <a href="/accounts" className="underline">
              {t("leads.form.accountsLink")}
            </a>{" "}
            {t("leads.form.noSessionsSuffix")}
          </p>
        )}

        <div className="space-y-2">
          <Label>{t("leads.form.targetInterest")}</Label>
          <Input
            placeholder={t("leads.form.targetPlaceholder")}
            value={targetInterest}
            onChange={(e) => setTargetInterest(e.target.value)}
            disabled={running || !!fixedTargetInterest}
          />
          <p className="text-xs text-muted-foreground">
            {t("leads.form.targetHint")}
          </p>
        </div>

        <div className="space-y-2">
          <Label>{t("leads.form.optionalKeywords")}</Label>
          <Input
            placeholder={t("leads.form.keywordsPlaceholder")}
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            disabled={running || !!fixedKeywords}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>{t("leads.form.maxTargetAccounts")}</Label>
            <Input
              type="number"
              min={1}
              max={200}
              value={maxProfiles}
              onChange={(e) => setMaxProfiles(Number(e.target.value))}
              disabled={running || !!fixedMaxProfiles}
            />
          </div>
          <div className="space-y-2">
            <Label>{t("leads.form.aiModel")}</Label>
            <Select value={model} onValueChange={setModel} disabled={running}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="gpt-4.1-mini">gpt-4.1-mini</SelectItem>
                <SelectItem value="llama3:8b">llama3:8b</SelectItem>
                <SelectItem value="gpt-4.1-nano">gpt-4.1-nano</SelectItem>
                <SelectItem value="gpt-4.1">gpt-4.1</SelectItem>
                <SelectItem value="gpt-4o-mini">gpt-4o-mini</SelectItem>
                <SelectItem value="gpt-4o">gpt-4o</SelectItem>
                <SelectItem value="claude-haiku-4-5">
                  Claude Haiku 4.5
                </SelectItem>
                <SelectItem value="claude-sonnet-4-6">
                  Claude Sonnet 4.6
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex gap-3">
          <Button
            onClick={startPipeline}
            disabled={running || !targetInterest.trim()}>
            {running && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            {running
              ? t("leads.form.runningPipeline")
              : t("leads.form.startPipeline")}
          </Button>
          {running && (
            <Button variant="destructive" onClick={stopPipeline}>
              <StopCircle className="h-4 w-4 mr-2" />
              {t("common.stop")}
            </Button>
          )}
        </div>

        {progress.length > 0 && (
          <div className="mt-4 rounded-md bg-muted p-3 max-h-48 overflow-y-auto">
            <p className="text-xs font-medium mb-1 text-muted-foreground">
              {t("leads.form.pipelineLog")}
            </p>
            {progress.map((line, i) => (
              <p key={i} className="text-xs font-mono text-muted-foreground">
                {line}
              </p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
