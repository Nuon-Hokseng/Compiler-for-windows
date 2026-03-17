"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  api, type Target, type UserInput, type ClassifyResult, type AnalyzeResult,
} from "@/lib/api";
import { useI18n } from "@/contexts/I18nContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { BrainCircuit, Download, Loader2 } from "lucide-react";

type AnyResult = ClassifyResult | AnalyzeResult;

interface AnalysisConfigCardProps {
  results: AnyResult[];
  onResults: (results: AnyResult[]) => void;
}

export function AnalysisConfigCard({ results, onResults }: AnalysisConfigCardProps) {
  const { t } = useI18n();
  const [targets, setTargets] = useState<Target[]>([]);
  const [targetKey, setTargetKey] = useState("");
  const [usernamesText, setUsernamesText] = useState("");
  const [model, setModel] = useState("");
  const [mode, setMode] = useState<"classify" | "analyze">("analyze");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getTargets().then((tgs) => {
      setTargets(tgs);
      if (tgs.length > 0) setTargetKey(tgs[0].key);
    });
  }, []);

  function parseUsers(): UserInput[] {
    return usernamesText.split("\n").map((l) => l.trim().replace(/^@/, "")).filter(Boolean).map((username) => ({ username, source: "manual" }));
  }

  async function handleRun() {
    const users = parseUsers();
    if (users.length === 0) { toast.error(t("analyze.enterUsername")); return; }
    setRunning(true);
    setError(null);
    onResults([]);
    try {
      if (mode === "classify") {
        const res = await api.classify(users, model || undefined);
        onResults(res.results);
        toast.success(t("analyze.classified", { count: res.results.length }));
      } else {
        if (!targetKey) { toast.error(t("analyze.selectTargetFirst")); setRunning(false); return; }
        const res = await api.analyze(users, targetKey, model || undefined);
        onResults(res.results);
        toast.success(t("analyze.analyzed", { count: res.results.length }));
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("analyze.requestFailed");
      setError(msg);
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  }

  async function handleExport() {
    if (results.length === 0) return;
    try {
      const blob = await api.exportCsv(results as unknown as Record<string, unknown>[], targetKey || "export");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${targetKey || "results"}_export.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(t("scrape.pipeline.csvDownloaded"));
    } catch {
      toast.error(t("scrape.pipeline.downloadFailed"));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BrainCircuit className="h-5 w-5" />
          {t("analyze.configTitle")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <Tabs value={mode} onValueChange={(v) => setMode(v as "classify" | "analyze")}>
          <TabsList>
            <TabsTrigger value="analyze">{t("analyze.nicheAnalyze")}</TabsTrigger>
            <TabsTrigger value="classify">{t("analyze.targetClassify")}</TabsTrigger>
          </TabsList>

          <TabsContent value="analyze" className="mt-4 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>{t("analyze.targetCustomer")}</Label>
                <Select value={targetKey} onValueChange={setTargetKey}>
                  <SelectTrigger>
                    <SelectValue placeholder={t("analyze.selectTarget")} />
                  </SelectTrigger>
                  <SelectContent>
                    {targets.map((tgt) => (
                      <SelectItem key={tgt.key} value={tgt.key}>{tgt.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>{t("analyze.modelOptional")}</Label>
                <Input placeholder={t("analyze.modelPlaceholder")} value={model} onChange={(e) => setModel(e.target.value)} />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="classify" className="mt-4 space-y-4">
            <div className="space-y-2">
              <Label>{t("analyze.modelOptional")}</Label>
              <Input placeholder={t("analyze.modelPlaceholder")} value={model} onChange={(e) => setModel(e.target.value)} />
            </div>
            <p className="text-sm text-muted-foreground">{t("analyze.classifyHint")}</p>
          </TabsContent>
        </Tabs>

        <div className="space-y-2">
          <Label>{t("analyze.usernames")}</Label>
          <Textarea rows={6} placeholder={t("analyze.usernamesPlaceholder")} value={usernamesText} onChange={(e) => setUsernamesText(e.target.value)} />
          <p className="text-xs text-muted-foreground">{t("analyze.usernameCount", { count: parseUsers().length })}</p>
        </div>

        <div className="flex gap-3">
          <Button onClick={handleRun} disabled={running}>
            {running && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            {mode === "classify" ? t("common.classify") : t("common.analyze")}
          </Button>
          {results.length > 0 && (
            <Button variant="outline" onClick={handleExport}>
              <Download className="h-4 w-4 mr-2" />
              {t("common.exportCsv")}
            </Button>
          )}
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}
