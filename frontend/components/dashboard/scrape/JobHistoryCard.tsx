"use client";

import { useI18n } from "@/contexts/I18nContext";
import { toast } from "sonner";
import { api, type Job } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Clock, Download, RefreshCw } from "lucide-react";

interface JobHistoryCardProps {
  jobs: Job[];
  loading: boolean;
  onRefresh: () => void;
}

export function JobHistoryCard({ jobs, loading, onRefresh }: JobHistoryCardProps) {
  const { t } = useI18n();

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
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            {t("scrape.jobHistory.title")}
          </CardTitle>
          <Button variant="ghost" size="sm" onClick={onRefresh}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : jobs.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("scrape.jobHistory.noJobs")}</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("scrape.jobHistory.jobId")}</TableHead>
                <TableHead>{t("scrape.jobHistory.target")}</TableHead>
                <TableHead>{t("common.status")}</TableHead>
                <TableHead>{t("scrape.pipeline.filtered")}</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((j) => (
                <TableRow key={j.job_id}>
                  <TableCell className="font-mono text-xs">{j.job_id.slice(0, 8)}...</TableCell>
                  <TableCell>{j.target_customer}</TableCell>
                  <TableCell>
                    <Badge
                      variant={j.status === "completed" ? "default" : j.status === "failed" ? "destructive" : "secondary"}
                    >
                      {j.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{j.summary?.filtered ?? "—"}</TableCell>
                  <TableCell>
                    {j.status === "completed" && j.summary?.csv_path && (
                      <Button variant="ghost" size="sm" onClick={() => handleDownload(j.job_id)}>
                        <Download className="h-4 w-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
