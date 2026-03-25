"use client";

import { useEffect, useRef, useState } from "react";
import { api, type AutomationTask } from "@/lib/api";
import { useI18n } from "@/contexts/I18nContext";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Terminal } from "lucide-react";

interface TaskLogsDialogProps {
  taskId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function TaskLogsDialog({ taskId, open, onOpenChange }: TaskLogsDialogProps) {
  const { t } = useI18n();
  const [logsData, setLogsData] = useState<AutomationTask | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!open || !taskId) {
      setLogsData(null);
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }
    const poll = async () => {
      try {
        const t = await api.getTaskStatus(taskId);
        setLogsData(t);
        if (t.status !== "running") {
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
        }
      } catch (err: unknown) { 
        const msg = err instanceof Error ? err.message : String(err);
        if (msg.includes("Task not found") || msg.includes("404")) {
          setLogsData(null);
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
        }
      }
    };
    poll();
    pollRef.current = setInterval(poll, 2000);
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [open, taskId]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5" />
            {t("accounts.taskLogs.title")}
            {logsData && (
              <Badge
                variant={logsData.status === "completed" ? "default" : logsData.status === "failed" ? "destructive" : "secondary"}
                className="ml-2"
              >
                {logsData.status}
              </Badge>
            )}
          </DialogTitle>
        </DialogHeader>
        <ScrollArea className="h-80 rounded-md border bg-muted/30 p-3 font-mono text-xs">
          {logsData?.logs?.map((line, i) => (
            <div key={i} className="py-0.5 whitespace-pre-wrap">{line}</div>
          )) ?? <p className="text-muted-foreground">{t("accounts.taskLogs.loadingLogs")}</p>}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
