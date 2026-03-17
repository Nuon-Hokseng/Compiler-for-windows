"use client";

import { useI18n } from "@/contexts/I18nContext";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

interface DeleteAccountDialogProps {
  cookieId: number | null;
  label: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (cookieId: number) => void;
  deleting?: boolean;
}

export function DeleteAccountDialog({
  cookieId, label, open, onOpenChange, onConfirm, deleting = false,
}: DeleteAccountDialogProps) {
  const { t } = useI18n();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("accounts.deleteDialog.title")}</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          {t("accounts.deleteDialog.confirm", { label: label ?? "" })}
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={deleting}>
            {t("common.cancel")}
          </Button>
          <Button variant="destructive" onClick={() => cookieId != null && onConfirm(cookieId)} disabled={deleting}>
            {deleting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            {t("common.remove")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
