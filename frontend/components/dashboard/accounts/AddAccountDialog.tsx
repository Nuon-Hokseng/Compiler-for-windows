"use client";

import { useState, useRef, useEffect } from "react";
import { toast } from "sonner";
import { api, type HeadlessSessionSnapshot } from "@/lib/api";
import { useI18n } from "@/contexts/I18nContext";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Instagram } from "lucide-react";

interface AddAccountDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
  userId: number;
}

export function AddAccountDialog({
  open,
  onOpenChange,
  onSuccess,
  userId,
}: AddAccountDialogProps) {
  const { t } = useI18n();
  const [starting, setStarting] = useState(false);
  const [submittingCredentials, setSubmittingCredentials] = useState(false);
  const [submitting2FA, setSubmitting2FA] = useState(false);
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [twoFactorCode, setTwoFactorCode] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<HeadlessSessionSnapshot | null>(
    null,
  );
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isTerminalState =
    snapshot?.status === "completed" ||
    snapshot?.status === "failed" ||
    snapshot?.status === "cancelled";

  const canSubmitCredentials =
    !!sessionId && snapshot?.status === "awaiting_credentials";
  const canSubmit2FA = !!sessionId && snapshot?.status === "awaiting_2fa";

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    if (!open) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      setStarting(false);
      setSubmittingCredentials(false);
      setSubmitting2FA(false);
      setIdentifier("");
      setPassword("");
      setTwoFactorCode("");
      setSessionId(null);
      setSnapshot(null);
    }
  }, [open]);

  useEffect(() => {
    if (!sessionId || !open) return;

    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const next = await api.getHeadlessSessionStatus(sessionId);
        setSnapshot(next);

        if (next.status === "completed") {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          toast.success(t("accounts.addDialog.connected"));
          onSuccess();
          onOpenChange(false);
          return;
        }

        if (next.status === "failed" || next.status === "cancelled") {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          toast.error(
            next.error || next.message || t("accounts.addDialog.failed"),
          );
        }
      } catch {
        // Keep polling unless the user closes the dialog.
      }
    }, 1500);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [open, onOpenChange, onSuccess, sessionId, t]);

  async function handleStartSession() {
    setStarting(true);
    try {
      const res = await api.startHeadlessSession(userId, 180);
      setSessionId(res.session_id);
      toast.info(t("accounts.addDialog.headlessStarting"));
    } catch (e: unknown) {
      toast.error(
        e instanceof Error ? e.message : t("accounts.addDialog.failedToStart"),
      );
    } finally {
      setStarting(false);
    }
  }

  async function handleSubmitCredentials() {
    if (!sessionId || !identifier.trim() || !password.trim()) return;
    setSubmittingCredentials(true);
    try {
      await api.submitHeadlessCredentials(
        sessionId,
        identifier.trim(),
        password,
      );
      toast.info(t("accounts.addDialog.credentialsSubmitted"));
    } catch (e: unknown) {
      toast.error(
        e instanceof Error
          ? e.message
          : t("accounts.addDialog.failedCredentials"),
      );
    } finally {
      setSubmittingCredentials(false);
    }
  }

  async function handleSubmit2FA() {
    if (!sessionId || !twoFactorCode.trim()) return;
    setSubmitting2FA(true);
    try {
      await api.submitHeadless2FA(sessionId, twoFactorCode.trim());
      setTwoFactorCode("");
      toast.info(t("accounts.addDialog.twoFactorSubmitted"));
    } catch (e: unknown) {
      toast.error(
        e instanceof Error
          ? e.message
          : t("accounts.addDialog.failedTwoFactor"),
      );
    } finally {
      setSubmitting2FA(false);
    }
  }

  async function handleClose(nextOpen: boolean) {
    if (!nextOpen && sessionId && !isTerminalState) {
      try {
        await api.cancelHeadlessSession(sessionId);
      } catch {
        // No-op: close should still proceed.
      }
    }
    onOpenChange(nextOpen);
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Instagram className="h-5 w-5" />
            {t("accounts.addDialog.title")}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <p className="text-sm text-muted-foreground">
            {t("accounts.addDialog.description")}
          </p>

          {sessionId && (
            <div className="rounded-md border p-3 space-y-1">
              <p className="text-sm font-medium">
                {t("accounts.addDialog.status")}:{" "}
                {snapshot?.status ?? "initializing"}
              </p>
              <p className="text-xs text-muted-foreground">
                {snapshot?.message || t("accounts.addDialog.waiting")}
              </p>
              {snapshot?.current_url && (
                <p className="text-xs text-muted-foreground break-all">
                  URL: {snapshot.current_url}
                </p>
              )}
            </div>
          )}

          <div className="grid gap-2">
            <Label htmlFor="ig-identifier">
              {t("accounts.addDialog.identifierLabel")}
            </Label>
            <Input
              id="ig-identifier"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder={t("accounts.addDialog.identifierPlaceholder")}
              disabled={
                !sessionId || !canSubmitCredentials || submittingCredentials
              }
              autoComplete="username"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="ig-password">
              {t("accounts.addDialog.passwordLabel")}
            </Label>
            <Input
              id="ig-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t("accounts.addDialog.passwordPlaceholder")}
              disabled={
                !sessionId || !canSubmitCredentials || submittingCredentials
              }
              autoComplete="current-password"
            />
          </div>

          {(snapshot?.requires_2fa || canSubmit2FA) && (
            <div className="grid gap-2">
              <Label htmlFor="ig-2fa">
                {t("accounts.addDialog.twoFactorLabel")}
              </Label>
              <Input
                id="ig-2fa"
                value={twoFactorCode}
                onChange={(e) => setTwoFactorCode(e.target.value)}
                placeholder={t("accounts.addDialog.twoFactorPlaceholder")}
                disabled={!canSubmit2FA || submitting2FA}
                autoComplete="one-time-code"
                inputMode="numeric"
              />
            </div>
          )}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">{t("common.cancel")}</Button>
          </DialogClose>
          {!sessionId ? (
            <Button onClick={handleStartSession} disabled={starting}>
              {starting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {t("accounts.addDialog.startHeadless")}
            </Button>
          ) : canSubmit2FA ? (
            <Button
              onClick={handleSubmit2FA}
              disabled={submitting2FA || !twoFactorCode.trim()}>
              {submitting2FA && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              {t("accounts.addDialog.submitTwoFactor")}
            </Button>
          ) : (
            <Button
              onClick={handleSubmitCredentials}
              disabled={
                submittingCredentials ||
                !canSubmitCredentials ||
                !identifier.trim() ||
                !password.trim()
              }>
              {submittingCredentials && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              {t("accounts.addDialog.submitCredentials")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
