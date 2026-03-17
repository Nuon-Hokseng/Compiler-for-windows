"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type Target, type AutomationTask } from "@/lib/api";
import { useBeforeUnload } from "@/lib/useBeforeUnload";
import { usePersistState } from "@/lib/usePersistState";
import { useI18n } from "@/contexts/I18nContext";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Loader2, Play, Square, Terminal, Scroll, BrainCircuit, Combine,
} from "lucide-react";

interface AutomationPanelProps {
  userId: number;
  targets: Target[];
  selectedTarget: string;
  onTargetChange: (target: string) => void;
  selectedAccount: string;
}

export function AutomationPanel({
  userId, targets, selectedTarget, onTargetChange, selectedAccount,
}: AutomationPanelProps) {
  const { t } = useI18n();
  const [form, setForm] = usePersistState("scrape_automation_form", {
    mode: "scroll" as const,
    duration: "120",
    infiniteMode: false,
    headless: true,
    searchTargets: "",
    searchChance: "30",
  });
  const { mode, duration, infiniteMode, headless, searchTargets, searchChance } = form;
  const setMode = (v: typeof form.mode) => setForm((p) => ({ ...p, mode: v }));
  const setDuration = (v: string) => setForm((p) => ({ ...p, duration: v }));
  const setInfiniteMode = (v: boolean) => setForm((p) => ({ ...p, infiniteMode: v }));
  const setHeadless = (v: boolean) => setForm((p) => ({ ...p, headless: v }));
  const setSearchTargets = (v: string) => setForm((p) => ({ ...p, searchTargets: v }));
  const setSearchChance = (v: string) => setForm((p) => ({ ...p, searchChance: v }));

  const [persistedTaskId, setPersistedTaskId] = usePersistState<string | null>("scrape_active_task", null);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeTask, setActiveTask] = useState<AutomationTask | null>(null);
  const [error, setError] = useState<string | null>(null);
  const taskPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isAutomationRunning = activeTask?.status === "running";
  useBeforeUnload(isAutomationRunning);

  useEffect(() => {
    return () => { if (taskPollRef.current) clearInterval(taskPollRef.current); };
  }, []);

  function startTaskPolling(taskId: string) {
    if (taskPollRef.current) clearInterval(taskPollRef.current);
    setPersistedTaskId(taskId);
    taskPollRef.current = setInterval(async () => {
      try {
        const status = await api.getTaskStatus(taskId);
        setActiveTask(status);
        if (status.status === "completed" || status.status === "failed") {
          if (taskPollRef.current) clearInterval(taskPollRef.current);
          taskPollRef.current = null;
          setPersistedTaskId(null);
          if (status.status === "completed") toast.success(t("scrape.automation.automationCompleted"));
          else toast.error(t("scrape.automation.automationFailed", { error: status.error ?? "" }));
        }
      } catch { /* keep polling */ }
    }, 2000);
  }

  useEffect(() => {
    const tid = persistedTaskId;
    if (!tid) return;
    setActiveTaskId(tid);
    setActiveTask((prev) => prev ?? { task_id: tid, type: "scroll", account: "", status: "running", progress: "Recovering...", logs: [], error: null });
    startTaskPolling(tid);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleStartAutomation() {
    if (!selectedAccount) { toast.error(t("scrape.automation.selectAccountFirst")); return; }
    if (!userId) { toast.error(t("scrape.automation.userIdMissing")); return; }

    setError(null);
    try {
      let res;
      const common = {
        user_id: userId, duration: parseInt(duration) || 120,
        infinite_mode: infiniteMode, headless, browser_type: "chromium" as const,
      };

      if (mode === "scroll") {
        res = await api.startBasicScroll(common);
      } else if (mode === "combined") {
        const targetList = searchTargets.split(",").map((t) => t.trim()).filter(Boolean);
        if (targetList.length === 0) { toast.error(t("scrape.automation.enterSearchTarget")); return; }
        res = await api.startCombinedScroll({
          ...common, search_targets: targetList,
          search_chance: (parseInt(searchChance) || 30) / 100,
          profile_scroll_count_min: 3, profile_scroll_count_max: 6,
        });
      } else if (mode === "scraper") {
        if (!selectedTarget) { toast.error(t("scrape.automation.selectTargetCustomer")); return; }
        res = await api.startScraperScroll({
          ...common, target_customer: selectedTarget,
          scraper_chance: 0.2, model: "llama3", search_chance: 0.0,
          profile_scroll_count_min: 3, profile_scroll_count_max: 6,
        });
      }

      if (!res) throw new Error("Invalid mode selected");

      setActiveTaskId(res.task_id);
      setActiveTask({
        task_id: res.task_id, type: mode, account: selectedAccount,
        status: "running", progress: "Starting...", logs: [], error: null,
      });
      toast.success(t("scrape.automation.automationStarted"));
      startTaskPolling(res.task_id);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to start";
      setError(msg);
      toast.error(msg);
    }
  }

  async function handleStopAutomation() {
    const tid = activeTaskId ?? persistedTaskId;
    if (!tid) return;
    try {
      await api.stopAutomation(tid);
      setPersistedTaskId(null);
      setActiveTaskId(null);
      setActiveTask(null);
      if (taskPollRef.current) {
        clearInterval(taskPollRef.current);
        taskPollRef.current = null;
      }
      toast.info(t("scrape.automation.stopSignalSent"));
    } catch {
      toast.error(t("scrape.automation.stopSignalFailed"));
    }
  }

  return (
    <>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs value={mode} onValueChange={(v) => setMode(v as typeof mode)}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="scroll" className="gap-2">
            <Scroll className="h-4 w-4" />
            {t("scrape.automation.scroll")}
          </TabsTrigger>
          <TabsTrigger value="combined" className="gap-2">
            <Combine className="h-4 w-4" />
            {t("scrape.automation.combined")}
          </TabsTrigger>
          <TabsTrigger value="scraper" className="gap-2">
            <BrainCircuit className="h-4 w-4" />
            {t("scrape.automation.scraper")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="scroll">
          <Card>
            <CardHeader>
              <CardTitle>{t("scrape.automation.autoScroll")}</CardTitle>
              <CardDescription>{t("scrape.automation.autoScrollDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label>{t("scrape.automation.duration")}</Label>
                  <Input type="number" value={duration} onChange={(e) => setDuration(e.target.value)} disabled={infiniteMode} />
                </div>
                <div className="flex items-end gap-3">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={infiniteMode} onChange={(e) => setInfiniteMode(e.target.checked)} className="accent-primary h-4 w-4" />
                    {t("scrape.automation.infiniteMode")}
                  </label>
                </div>
                <div className="flex items-end gap-3">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={headless} onChange={(e) => setHeadless(e.target.checked)} className="accent-primary h-4 w-4" />
                    {t("scrape.automation.headless")}
                  </label>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="combined">
          <Card>
            <CardHeader>
              <CardTitle>{t("scrape.automation.combinedTitle")}</CardTitle>
              <CardDescription>{t("scrape.automation.combinedDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label>{t("scrape.automation.duration")}</Label>
                  <Input type="number" value={duration} onChange={(e) => setDuration(e.target.value)} disabled={infiniteMode} />
                </div>
                <div className="space-y-2">
                  <Label>{t("scrape.automation.searchChance")}</Label>
                  <Input type="number" value={searchChance} onChange={(e) => setSearchChance(e.target.value)} min={1} max={100} />
                </div>
                <div className="flex items-end gap-3 flex-wrap">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={infiniteMode} onChange={(e) => setInfiniteMode(e.target.checked)} className="accent-primary h-4 w-4" />
                    {t("scrape.automation.infinite")}
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={headless} onChange={(e) => setHeadless(e.target.checked)} className="accent-primary h-4 w-4" />
                    {t("scrape.automation.headlessShort")}
                  </label>
                </div>
              </div>
              <div className="space-y-2">
                <Label>{t("scrape.automation.searchTargets")}</Label>
                <Textarea rows={3} placeholder="#travel, #food, @someuser, #photography" value={searchTargets} onChange={(e) => setSearchTargets(e.target.value)} />
                <p className="text-xs text-muted-foreground">{t("scrape.automation.searchTargetsHint")}</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="scraper">
          <Card>
            <CardHeader>
              <CardTitle>{t("scrape.automation.scraperTitle")}</CardTitle>
              <CardDescription>{t("scrape.automation.scraperDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label>{t("scrape.automation.targetCustomer")}</Label>
                  <Select value={selectedTarget} onValueChange={onTargetChange}>
                    <SelectTrigger>
                      <SelectValue placeholder={t("scrape.automation.selectTarget")} />
                    </SelectTrigger>
                    <SelectContent>
                      {targets.map((tgt) => (
                        <SelectItem key={tgt.key} value={tgt.key}>{tgt.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>{t("scrape.automation.duration")}</Label>
                  <Input type="number" value={duration} onChange={(e) => setDuration(e.target.value)} disabled={infiniteMode} />
                </div>
                <div className="flex items-end gap-3 flex-wrap">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={infiniteMode} onChange={(e) => setInfiniteMode(e.target.checked)} className="accent-primary h-4 w-4" />
                    {t("scrape.automation.infinite")}
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={headless} onChange={(e) => setHeadless(e.target.checked)} className="accent-primary h-4 w-4" />
                    {t("scrape.automation.headlessShort")}
                  </label>
                </div>
              </div>
              <div className="space-y-2">
                <Label>{t("scrape.automation.searchTargetsOptional")}</Label>
                <Textarea rows={2} placeholder="#travel, @someuser" value={searchTargets} onChange={(e) => setSearchTargets(e.target.value)} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <div className="flex gap-3">
        <Button onClick={handleStartAutomation} disabled={isAutomationRunning || !selectedAccount} size="lg">
          {isAutomationRunning ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2" />}
          {isAutomationRunning ? t("scrape.automation.running") : t("scrape.automation.startMode", { mode })}
        </Button>
        {isAutomationRunning && (
          <Button variant="destructive" size="lg" onClick={handleStopAutomation}>
            <Square className="h-4 w-4 mr-2" />
            {t("common.stop")}
          </Button>
        )}
      </div>

      {activeTask && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Terminal className="h-4 w-4" />
              {t("scrape.automation.liveLogs", { account: activeTask.account, type: activeTask.type })}
              <Badge
                variant={activeTask.status === "completed" ? "default" : activeTask.status === "failed" ? "destructive" : "secondary"}
                className="ml-auto"
              >
                {activeTask.status}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-52 rounded-md border bg-zinc-950 p-3 font-mono text-xs text-green-400">
              {activeTask.logs && activeTask.logs.length > 0 ? (
                activeTask.logs.map((line, i) => (
                  <div key={i} className="py-0.5 whitespace-pre-wrap">{line}</div>
                ))
              ) : (
                <p className="text-zinc-500">{t("scrape.automation.waitingOutput")}</p>
              )}
            </ScrollArea>
            {activeTask.error && (
              <Alert variant="destructive" className="mt-3">
                <AlertDescription>{activeTask.error}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}
    </>
  );
}
