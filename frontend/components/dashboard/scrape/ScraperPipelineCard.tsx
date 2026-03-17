"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type Target, type Job, type JobResults } from "@/lib/api";
import { useI18n } from "@/contexts/I18nContext";
import { useBeforeUnload } from "@/lib/useBeforeUnload";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  SearchCode, Loader2, Play, Download, CheckCircle2, XCircle,
} from "lucide-react";

interface ScraperPipelineCardProps {
  targets: Target[];
  selectedTarget: string;
  onTargetChange: (target: string) => void;
  onJobsRefetch: () => void;
}

export function ScraperPipelineCard({
  targets, selectedTarget, onTargetChange, onJobsRefetch,
}: ScraperPipelineCardProps) {
  const { t } = useI18n();
  const [maxCommenters, setMaxCommenters] = useState("15");
  const [submittingScrape, setSubmittingScrape] = useState(false);
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [jobResults, setJobResults] = useState<JobResults | null>(null);
  const jobPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isJobRunning = activeJob && (activeJob.status === "queued" || activeJob.status === "running");
  useBeforeUnload(!!isJobRunning);

  useEffect(() => {
    return () => { if (jobPollRef.current) clearInterval(jobPollRef.current); };
  }, []);

  function startJobPolling(jobId: string) {
    if (jobPollRef.current) clearInterval(jobPollRef.current);
    jobPollRef.current = setInterval(async () => {
      try {
        const status = await api.getJobStatus(jobId);
        setActiveJob(status);
        if (status.status === "completed" || status.status === "failed") {
          if (jobPollRef.current) clearInterval(jobPollRef.current);
          jobPollRef.current = null;
          onJobsRefetch();
          if (status.status === "completed") {
            toast.success(t("scrape.pipeline.pipelineCompleted"));
            try { setJobResults(await api.getJobResults(jobId)); } catch { /* no results */ }
          } else {
            toast.error(t("scrape.pipeline.scrapeFailed", { error: status.error ?? "" }));
          }
        }
      } catch { /* keep polling */ }
    }, 3000);
  }

  async function handleStartPipeline() {
    if (!selectedTarget) { toast.error(t("scrape.pipeline.selectTarget")); return; }
    setSubmittingScrape(true);
    setJobResults(null);
    try {
      const mc = parseInt(maxCommenters) || undefined;
      const res = await api.startScrape(selectedTarget, mc);
      setActiveJob({
        job_id: res.job_id, status: "queued", progress: "Waiting to start...",
        target_customer: selectedTarget, error: null, summary: null,
      });
      toast.success(t("scrape.pipeline.scrapeStarted"));
      startJobPolling(res.job_id);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to start");
    } finally {
      setSubmittingScrape(false);
    }
  }

  async function handleDownload(jobId: string) {
    try {
      const blob = await api.downloadExport(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `scrape_${jobId.slice(0, 8)}.csv`;
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
          <SearchCode className="h-5 w-5" />
          {t("scrape.pipeline.title")}
        </CardTitle>
        <CardDescription>{t("scrape.pipeline.desc")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
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
            <Label>{t("scrape.pipeline.maxCommenters")}</Label>
            <Input type="number" value={maxCommenters} onChange={(e) => setMaxCommenters(e.target.value)} min={1} max={50} />
          </div>
        </div>
        <Button onClick={handleStartPipeline} disabled={submittingScrape || !!isJobRunning}>
          {submittingScrape || isJobRunning ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2" />}
          {isJobRunning ? t("scrape.pipeline.pipelineRunning") : t("scrape.pipeline.startPipeline")}
        </Button>
      </CardContent>

      {activeJob && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              {activeJob.status === "completed" ? (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : activeJob.status === "failed" ? (
                <XCircle className="h-5 w-5 text-destructive" />
              ) : (
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
              )}
              Pipeline {activeJob.job_id.slice(0, 8)}...
              <Badge
                variant={activeJob.status === "completed" ? "default" : activeJob.status === "failed" ? "destructive" : "secondary"}
                className="ml-auto"
              >
                {activeJob.status}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm">{activeJob.progress}</p>

            {activeJob.summary && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                {([
                  [t("scrape.pipeline.totalScraped"), activeJob.summary.total_scraped],
                  [t("scrape.pipeline.owners"), activeJob.summary.owners],
                  [t("scrape.pipeline.commenters"), activeJob.summary.commenters],
                  [t("scrape.pipeline.filtered"), activeJob.summary.filtered],
                ] as [string, number][]).map(([label, val]) => (
                  <div key={label} className="rounded-md border p-3">
                    <p className="text-2xl font-bold">{String(val)}</p>
                    <p className="text-xs text-muted-foreground">{label}</p>
                  </div>
                ))}
              </div>
            )}

            {activeJob.status === "completed" && activeJob.summary?.csv_path && (
              <Button variant="outline" onClick={() => handleDownload(activeJob.job_id)}>
                <Download className="h-4 w-4 mr-2" />
                {t("common.downloadCsv")}
              </Button>
            )}

            {jobResults && jobResults.results.length > 0 && (
              <>
                <Separator />
                <p className="text-sm font-medium">
                  {t("common.results")} ({jobResults.results.length})
                </p>
                <div className="max-h-48 overflow-y-auto rounded border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t("common.username")}</TableHead>
                        <TableHead>{t("common.source")}</TableHead>
                        <TableHead>{t("common.details")}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {jobResults.results.slice(0, 30).map((r, i) => (
                        <TableRow key={i}>
                          <TableCell className="font-mono text-sm">@{String(r.username ?? "")}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">{String(r.source ?? "—")}</TableCell>
                          <TableCell>
                            {r.classification ? (
                              <Badge variant="secondary">{String(r.classification)} ({String(r.score)}/100)</Badge>
                            ) : r.niche ? (
                              <Badge variant="secondary">{String(r.niche)} ({String(r.relevance)}/10)</Badge>
                            ) : "—"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </Card>
  );
}
