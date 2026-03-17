"use client";

import { useState, Fragment } from "react";
import type { Lead } from "@/lib/api";
import { useI18n } from "@/contexts/I18nContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, Download, Users } from "lucide-react";

interface LeadGenResultsProps {
  leads: Lead[];
  allResults: Lead[];
  totalScanned: number;
  totalQualified: number;
}

function scoreBadge(score: number) {
  if (score >= 80) return <Badge variant="default">{score}</Badge>;
  if (score >= 65) return <Badge variant="secondary">{score}</Badge>;
  return <Badge variant="outline">{score}</Badge>;
}

export function LeadGenResults({
  leads, allResults, totalScanned, totalQualified,
}: LeadGenResultsProps) {
  const { t } = useI18n();
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  if (allResults.length === 0) return null;

  const displayData = showAll ? allResults : leads;

  function confidenceBadge(confidence: string) {
    switch (confidence) {
      case "high": return <Badge variant="default">{t("common.high")}</Badge>;
      case "medium": return <Badge variant="secondary">{t("common.medium")}</Badge>;
      default: return <Badge variant="outline">{t("common.low")}</Badge>;
    }
  }

  function exportCSV() {
    const headers = [
      "username", "full_name", "bio", "followers_count", "total_score", "confidence",
      "is_target", "age_score", "work_score", "occupation_score", "location_score",
      "side_job_score", "reasoning", "discovery_source",
    ];
    const rows = displayData.map((l) =>
      [
        l.username, l.full_name, `"${(l.bio || "").replace(/"/g, '""')}"`,
        l.followers_count, l.total_score, l.confidence, l.is_target,
        l.scores?.age ?? 0, l.scores?.work_lifestyle ?? 0, l.scores?.occupation ?? 0,
        l.scores?.location ?? 0, l.scores?.side_job_signal ?? 0,
        `"${(l.reasoning || "").replace(/"/g, '""')}"`, l.discovery_source,
      ].join(",")
    );
    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "leads_export.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            {t("leads.results.title")}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline">
              {t("leads.results.leadsScanned", { qualified: totalQualified, scanned: totalScanned })}
            </Badge>
            <Button variant="outline" size="sm" onClick={exportCSV}>
              <Download className="h-3.5 w-3.5 mr-1" />
              {t("common.csv")}
            </Button>
          </div>
        </div>
        <div className="flex gap-2 mt-2">
          <Button variant={!showAll ? "default" : "outline"} size="sm" onClick={() => setShowAll(false)}>
            {t("leads.results.qualifiedOnly", { count: leads.length })}
          </Button>
          <Button variant={showAll ? "default" : "outline"} size="sm" onClick={() => setShowAll(true)}>
            {t("leads.results.all", { count: allResults.length })}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("common.username")}</TableHead>
              <TableHead>{t("common.name")}</TableHead>
              <TableHead>{t("common.score")}</TableHead>
              <TableHead>{t("common.confidence")}</TableHead>
              <TableHead>{t("common.language")}</TableHead>
              <TableHead>{t("common.followers")}</TableHead>
              <TableHead className="w-10"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayData.map((lead) => {
              const expanded = expandedRow === lead.username;
              return (
                <Fragment key={lead.username}>
                  <TableRow className="cursor-pointer" onClick={() => setExpandedRow(expanded ? null : lead.username)}>
                    <TableCell className="font-mono text-sm">@{lead.username}</TableCell>
                    <TableCell className="text-sm max-w-[120px] truncate">{lead.full_name || "—"}</TableCell>
                    <TableCell>{scoreBadge(lead.total_score)}</TableCell>
                    <TableCell>{confidenceBadge(lead.confidence)}</TableCell>
                    <TableCell><Badge variant="outline" className="text-xs">{lead.detected_language || "?"}</Badge></TableCell>
                    <TableCell className="text-sm text-muted-foreground">{lead.followers_count?.toLocaleString() ?? "—"}</TableCell>
                    <TableCell>{expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</TableCell>
                  </TableRow>
                  {expanded && (
                    <TableRow>
                      <TableCell colSpan={7} className="bg-muted/50">
                        <div className="grid gap-4 py-3 text-sm sm:grid-cols-2">
                          <div>
                            <p className="font-medium mb-2">{t("leads.results.scoreBreakdown")}</p>
                            <div className="space-y-1 text-muted-foreground">
                              <div className="flex justify-between"><span>{t("leads.results.age")}</span><span>{lead.scores?.age ?? 0}/30</span></div>
                              <div className="flex justify-between"><span>{t("leads.results.workLifestyle")}</span><span>{lead.scores?.work_lifestyle ?? 0}/25</span></div>
                              <div className="flex justify-between"><span>{t("leads.results.occupation")}</span><span>{lead.scores?.occupation ?? 0}/15</span></div>
                              <div className="flex justify-between"><span>{t("leads.results.location")}</span><span>{lead.scores?.location ?? 0}/15</span></div>
                              <div className="flex justify-between"><span>{t("leads.results.sideJobSignal")}</span><span>{lead.scores?.side_job_signal ?? 0}/15</span></div>
                              <div className="flex justify-between font-medium text-foreground pt-1 border-t"><span>{t("leads.results.total")}</span><span>{lead.total_score}/100</span></div>
                            </div>
                          </div>
                          <div className="space-y-3">
                            {lead.bio && (
                              <div>
                                <p className="font-medium mb-1">{t("common.bio")}</p>
                                <p className="text-muted-foreground text-xs">{lead.bio}</p>
                              </div>
                            )}
                            {lead.reasoning && (
                              <div>
                                <p className="font-medium mb-1">{t("leads.results.aiReasoning")}</p>
                                <p className="text-muted-foreground text-xs text-wrap overflow-hidden break-words" style={{ overflowWrap: "anywhere" }}>{lead.reasoning}</p>
                              </div>
                            )}
                            {lead.discovery_source && (
                              <div>
                                <p className="font-medium mb-1">{t("leads.results.discoverySource")}</p>
                                <Badge variant="outline" className="text-xs">{lead.discovery_source}</Badge>
                              </div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
