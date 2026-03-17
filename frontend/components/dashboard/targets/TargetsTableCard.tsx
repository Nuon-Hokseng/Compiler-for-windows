"use client";

import { useI18n } from "@/contexts/I18nContext";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { Target } from "@/lib/api";

interface TargetsTableCardProps {
  targets: Target[];
  loading: boolean;
  onTargetClick: (key: string) => void;
}

export function TargetsTableCard({ targets, loading, onTargetClick }: TargetsTableCardProps) {
  const { t } = useI18n();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("targets.targetCustomers")}</CardTitle>
        <CardDescription>{t("targets.clickToSeeConfig")}</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("common.key")}</TableHead>
                <TableHead>{t("common.name")}</TableHead>
                <TableHead>{t("targets.hashtags")}</TableHead>
                <TableHead>{t("targets.brain")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {targets.map((tgt) => (
                <TableRow
                  key={tgt.key}
                  className="cursor-pointer hover:bg-accent"
                  onClick={() => onTargetClick(tgt.key)}
                >
                  <TableCell className="font-mono text-sm">{tgt.key}</TableCell>
                  <TableCell className="font-medium">{tgt.name}</TableCell>
                  <TableCell>
                    <span className="text-muted-foreground text-sm">
                      {tgt.config?.hashtags?.length ?? 0} {t("targets.tags")}
                    </span>
                  </TableCell>
                  <TableCell>
                    {tgt.config?.use_target_identification_brain ? (
                      <Badge>{t("targets.targetId")}</Badge>
                    ) : (
                      <Badge variant="secondary">{t("targets.niche")}</Badge>
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
