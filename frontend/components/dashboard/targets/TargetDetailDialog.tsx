"use client";

import { useEffect, useState } from "react";
import { api, type TargetDetail } from "@/lib/api";
import { useI18n } from "@/contexts/I18nContext";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Hash, Users, Brain } from "lucide-react";

interface TargetDetailDialogProps {
  open: boolean;
  targetKey: string | null;
  onOpenChange: (open: boolean) => void;
}

export function TargetDetailDialog({ open, targetKey, onOpenChange }: TargetDetailDialogProps) {
  const { t } = useI18n();
  const [detail, setDetail] = useState<TargetDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !targetKey) { setDetail(null); return; }
    setLoading(true);
    api.getTarget(targetKey).then(setDetail).finally(() => setLoading(false));
  }, [open, targetKey]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between">
            {loading ? <Skeleton className="h-6 w-40" /> : detail?.name}
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="space-y-3 py-4">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : detail ? (
          <div className="space-y-5 py-2">
            <div>
              <p className="text-sm font-medium text-muted-foreground mb-1">{t("common.key")}</p>
              <Badge variant="outline" className="font-mono">{detail.key}</Badge>
            </div>

            <div>
              <p className="text-sm font-medium text-muted-foreground mb-1">{t("targets.detail.aiBrain")}</p>
              <div className="flex items-center gap-2">
                <Brain className="h-4 w-4" />
                <span className="text-sm">
                  {detail.config.use_target_identification_brain
                    ? t("targets.detail.targetIdBrain")
                    : t("targets.detail.nicheClassBrain")}
                </span>
              </div>
            </div>

            <Separator />

            <div>
              <div className="flex items-center gap-2 mb-2">
                <Hash className="h-4 w-4" />
                <p className="text-sm font-medium">
                  {t("targets.hashtags")} ({detail.config.hashtags.length})
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {detail.config.hashtags.map((h) => (
                  <Badge key={h} variant="secondary">#{h}</Badge>
                ))}
              </div>
            </div>

            <Separator />

            <div>
              <div className="flex items-center gap-2 mb-2">
                <Users className="h-4 w-4" />
                <p className="text-sm font-medium">
                  {t("targets.detail.niches")} ({detail.config.niches.length})
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {detail.config.niches.map((n) => (
                  <Badge key={n} variant="outline">{n}</Badge>
                ))}
              </div>
            </div>

            {detail.config.keywords && detail.config.keywords.length > 0 && (
              <>
                <Separator />
                <div>
                  <p className="text-sm font-medium mb-2">{t("common.keywords")}</p>
                  <p className="text-sm text-muted-foreground">{detail.config.keywords.join(", ")}</p>
                </div>
              </>
            )}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
