"use client";

import { useState, useRef, useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useI18n } from "@/contexts/I18nContext";
import { useBeforeUnload } from "@/lib/useBeforeUnload";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2, Instagram } from "lucide-react";

interface AddAccountDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
  userId: number;
}

export function AddAccountDialog({ open, onOpenChange, onSuccess, userId }: AddAccountDialogProps) {
  const { t } = useI18n();
  const [adding, setAdding] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useBeforeUnload(adding && open);

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  async function handleAdd() {
    setAdding(true);
    try {
      const res = await api.saveSession(userId);
      toast.info(t("accounts.addDialog.browserOpening"));

      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const status = await api.getSessionTaskStatus(res.task_id);
          if (status.status === "completed") {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setAdding(false);
            toast.success(t("accounts.addDialog.connected"));
            onSuccess();
            onOpenChange(false);
          } else if (status.status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setAdding(false);
            toast.error(`Failed: ${status.message ?? "Unknown error"}`);
          }
        } catch { /* keep polling */ }
      }, 2000);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to start");
      setAdding(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Instagram className="h-5 w-5" />
            {t("accounts.addDialog.title")}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <p className="text-sm text-muted-foreground">{t("accounts.addDialog.description")}</p>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">{t("common.cancel")}</Button>
          </DialogClose>
          <Button onClick={handleAdd} disabled={adding}>
            {adding && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            {t("accounts.addDialog.openLogin")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
