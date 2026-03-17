"use client";

import { useI18n } from "@/contexts/I18nContext";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { UserPlus, CheckCircle2, XCircle, Instagram, Trash2 } from "lucide-react";
import type { CookieSnapshot } from "@/lib/api";

function extractIgUsername(cookies: Record<string, unknown>[]): string | null {
  if (!Array.isArray(cookies)) return null;
  for (const c of cookies) {
    if (c?.name === "ds_user" && typeof c.value === "string") return c.value;
  }
  return null;
}

function formatDate(iso?: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

interface AccountsTableProps {
  hasCookies: boolean;
  instagramUsername?: string | null;
  loading: boolean;
  onAddClick: () => void;
  cookieSnapshots: CookieSnapshot[];
  onDeleteCookie: (cookieId: number, label: string) => void;
}

export function AccountsTable({
  hasCookies, loading, onAddClick, cookieSnapshots, onDeleteCookie,
}: AccountsTableProps) {
  const { t } = useI18n();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Instagram className="h-5 w-5" />
          {t("accounts.instagramAccounts")}
        </CardTitle>
        <CardDescription>{t("accounts.tableDesc")}</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : cookieSnapshots.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("accounts.account")}</TableHead>
                <TableHead>{t("accounts.savedAt")}</TableHead>
                <TableHead>{t("common.status")}</TableHead>
                <TableHead className="text-right">{t("common.actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cookieSnapshots.map((snap) => {
                const igUser = snap.instagram_username || extractIgUsername(snap.cookies);
                const label = igUser ? `@${igUser}` : `Session #${snap.id}`;
                return (
                  <TableRow key={snap.id}>
                    <TableCell className="font-medium">{label}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">{formatDate(snap.created_at)}</TableCell>
                    <TableCell>
                      <Badge variant="default" className="bg-green-600 hover:bg-green-700">
                        <CheckCircle2 className="h-3 w-3 mr-1" />
                        {t("common.connected")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost" size="sm"
                        className="text-destructive hover:text-destructive hover:bg-destructive/10"
                        onClick={() => onDeleteCookie(snap.id, label)}
                      >
                        <Trash2 className="h-4 w-4 mr-1" />
                        {t("common.delete")}
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        ) : (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <XCircle className="h-10 w-10 text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground mb-4">
              {hasCookies ? t("accounts.couldNotLoad") : t("accounts.noSessions")}
            </p>
            <Button size="sm" onClick={onAddClick}>
              <UserPlus className="h-4 w-4 mr-1" />
              {t("common.addAccount")}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
