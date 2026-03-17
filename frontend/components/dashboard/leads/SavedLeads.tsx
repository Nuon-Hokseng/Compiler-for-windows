"use client";

import { useState } from "react";
import { toast } from "sonner";
import { api, type SavedLead } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { useSavedLeads, useSavedNiches } from "@/lib/swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Eye, Loader2, Star, Trash2, Users } from "lucide-react";

export function SavedLeads() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [selectedNiche, setSelectedNiche] = useState<string>("all");
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [reasoningLead, setReasoningLead] = useState<SavedLead | null>(null);

  const niche = selectedNiche === "all" ? undefined : selectedNiche;

  const { data: nichesData } = useSavedNiches(user?.user_id);
  const {
    data: leadsData, isLoading: loading, mutate: mutateLeads,
  } = useSavedLeads(user?.user_id, niche);

  const niches = nichesData?.niches ?? [];
  const leads = leadsData?.leads ?? [];

  async function handleDelete(leadId: number) {
    setDeletingId(leadId);
    try {
      await api.deleteSavedLead(leadId);
      mutateLeads(
        (prev) => prev ? { ...prev, leads: prev.leads.filter((l) => l.id !== leadId) } : prev,
        { revalidate: false },
      );
      toast.success(t("leads.saved.leadRemoved"));
    } catch {
      toast.error(t("leads.saved.failedRemove"));
    } finally {
      setDeletingId(null);
    }
  }

  function confidenceColor(c: string) {
    if (c === "high") return "default" as const;
    if (c === "medium") return "secondary" as const;
    return "outline" as const;
  }

  if (!user) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Star className="h-5 w-5" />
            {t("leads.saved.title")}
          </CardTitle>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {leads.length} {leads.length !== 1 ? t("leads.saved.leadCountPlural", { count: leads.length }).replace(`${leads.length} `, "") : t("leads.saved.leadCount", { count: leads.length }).replace(`${leads.length} `, "")}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {niches.length > 0 && (
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium">{t("leads.saved.filterByNiche")}</span>
            <Select value={selectedNiche} onValueChange={setSelectedNiche}>
              <SelectTrigger className="w-70">
                <SelectValue placeholder={t("leads.saved.allNiches")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("leads.saved.allNiches")}</SelectItem>
                {niches.map((n) => <SelectItem key={n} value={n}>{n}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : leads.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Users className="h-10 w-10 mx-auto mb-2 opacity-50" />
            <p className="text-sm">{t("leads.saved.noSavedLeads")}</p>
          </div>
        ) : (
          <div className="rounded-md border overflow-auto max-h-125">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("common.username")}</TableHead>
                  <TableHead>{t("common.name")}</TableHead>
                  <TableHead>{t("leads.saved.niche")}</TableHead>
                  <TableHead className="text-center">{t("common.score")}</TableHead>
                  <TableHead className="text-center">{t("common.confidence")}</TableHead>
                  <TableHead className="text-center">{t("common.followers")}</TableHead>
                  <TableHead>{t("leads.saved.aiReasoning")}</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {leads.map((lead) => (
                  <TableRow key={lead.id}>
                    <TableCell className="font-medium">
                      <a href={`https://instagram.com/${lead.username}`} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                        @{lead.username}
                      </a>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{lead.full_name || "—"}</TableCell>
                    <TableCell><Badge variant="secondary" className="text-xs">{lead.niche}</Badge></TableCell>
                    <TableCell className="text-center font-semibold">{lead.total_score}</TableCell>
                    <TableCell className="text-center"><Badge variant={confidenceColor(lead.confidence)}>{lead.confidence}</Badge></TableCell>
                    <TableCell className="text-center text-muted-foreground">{lead.followers_count.toLocaleString()}</TableCell>
                    <TableCell className="max-w-[250px]">
                      <div className="flex items-center gap-2">
                        <p className="text-xs text-muted-foreground truncate flex-1">{lead.reasoning || "—"}</p>
                        {lead.reasoning && (
                          <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={() => setReasoningLead(lead)}>
                            <Eye className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost" size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={() => handleDelete(lead.id)}
                        disabled={deletingId === lead.id}
                      >
                        {deletingId === lead.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>

      <Dialog open={!!reasoningLead} onOpenChange={(open) => !open && setReasoningLead(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{t("leads.saved.aiReasoning")} — @{reasoningLead?.username}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex items-center gap-3 text-sm">
              <Badge variant="secondary">{t("common.score")}: {reasoningLead?.total_score}</Badge>
              <Badge variant="outline">{reasoningLead?.confidence} {t("common.confidence").toLowerCase()}</Badge>
            </div>
            <p className="text-sm leading-relaxed text-muted-foreground" style={{ overflowWrap: "anywhere" }}>
              {reasoningLead?.reasoning || t("leads.saved.noReasoningAvailable")}
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
