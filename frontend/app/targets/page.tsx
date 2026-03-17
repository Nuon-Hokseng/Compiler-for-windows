"use client";

import { useState } from "react";
import { useTargets } from "@/lib/swr";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { TargetsPageHeader } from "../../components/dashboard/targets/TargetsPageHeader";
import { TargetsTableCard } from "../../components/dashboard/targets/TargetsTableCard";
import { TargetDetailDialog } from "../../components/dashboard/targets/TargetDetailDialog";

export default function TargetsPage() {
  const { data: targets, error, isLoading: loading } = useTargets();
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  function handleTargetClick(key: string) {
    setSelectedKey(key);
    setDetailOpen(true);
  }

  function handleDetailClose(open: boolean) {
    setDetailOpen(open);
    if (!open) setSelectedKey(null);
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <TargetsPageHeader />

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}

      <TargetsTableCard
        targets={targets ?? []}
        loading={loading}
        onTargetClick={handleTargetClick}
      />

      <TargetDetailDialog
        open={detailOpen}
        targetKey={selectedKey}
        onOpenChange={handleDetailClose}
      />
    </div>
  );
}
