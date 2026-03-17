"use client";

import { useState, Fragment } from "react";
import { useI18n } from "@/contexts/I18nContext";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { ClassifyResult, AnalyzeResult } from "@/lib/api";

type AnyResult = ClassifyResult | AnalyzeResult;

function isClassifyResult(r: AnyResult): r is ClassifyResult {
  return "classification" in r;
}

interface ResultsCardProps {
  results: AnyResult[];
}

export function ResultsCard({ results }: ResultsCardProps) {
  const { t } = useI18n();
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  if (results.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("analyze.results.title", { count: results.length })}</CardTitle>
        <CardDescription>
          {isClassifyResult(results[0])
            ? t("analyze.results.classifyDesc")
            : t("analyze.results.analyzeDesc")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("common.username")}</TableHead>
              {isClassifyResult(results[0]) ? (
                <>
                  <TableHead>{t("analyze.results.classification")}</TableHead>
                  <TableHead>{t("common.score")}</TableHead>
                </>
              ) : (
                <>
                  <TableHead>{t("targets.niche")}</TableHead>
                  <TableHead>{t("analyze.results.relevance")}</TableHead>
                </>
              )}
              <TableHead>{t("common.source")}</TableHead>
              <TableHead className="w-10"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {results.map((r) => {
              const expanded = expandedRow === r.username;
              return (
                <Fragment key={r.username}>
                  <TableRow
                    className="cursor-pointer"
                    onClick={() => setExpandedRow(expanded ? null : r.username)}
                  >
                    <TableCell className="font-mono text-sm">@{r.username}</TableCell>
                    {isClassifyResult(r) ? (
                      <>
                        <TableCell>
                          <Badge
                            variant={
                              r.classification === "IDEAL TARGET" ? "default"
                              : r.classification === "POSSIBLE TARGET" ? "secondary"
                              : "outline"
                            }
                          >
                            {r.classification}
                          </Badge>
                        </TableCell>
                        <TableCell>{r.score}/100</TableCell>
                      </>
                    ) : (
                      <>
                        <TableCell>
                          <Badge variant="secondary">{(r as AnalyzeResult).niche}</Badge>
                        </TableCell>
                        <TableCell>{(r as AnalyzeResult).relevance}/10</TableCell>
                      </>
                    )}
                    <TableCell className="text-muted-foreground text-sm">{r.source ?? "—"}</TableCell>
                    <TableCell>
                      {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </TableCell>
                  </TableRow>
                  {expanded && isClassifyResult(r) && (
                    <TableRow>
                      <TableCell colSpan={5} className="bg-muted/50">
                        <div className="grid gap-2 py-2 text-sm sm:grid-cols-2">
                          <div>
                            <p className="font-medium mb-1">{t("analyze.results.signalsUsed")}</p>
                            {r.signals_used.length > 0 ? (
                              <ul className="list-disc pl-4 text-muted-foreground space-y-0.5">
                                {r.signals_used.map((s, i) => <li key={i}>{s}</li>)}
                              </ul>
                            ) : (
                              <p className="text-muted-foreground">{t("common.none")}</p>
                            )}
                          </div>
                          <div>
                            <p className="font-medium mb-1">{t("analyze.results.uncertainties")}</p>
                            {r.uncertainties.length > 0 ? (
                              <ul className="list-disc pl-4 text-muted-foreground space-y-0.5">
                                {r.uncertainties.map((u, i) => <li key={i}>{u}</li>)}
                              </ul>
                            ) : (
                              <p className="text-muted-foreground">{t("common.none")}</p>
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
