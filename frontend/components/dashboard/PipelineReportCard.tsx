"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { useSavedLeads } from "@/lib/swr";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TrendingUp, Users, UserCheck, Loader2, ArrowRight } from "lucide-react";

export function PipelineReportCard() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { data: leadsData, isLoading } = useSavedLeads(user?.user_id);

  const leads = leadsData?.leads ?? [];
  const followedCount = leads.filter((l) => l.followed).length;
  const recentLeads = leads.slice(0, 5);

  if (!user) return null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg">
            <TrendingUp className="h-5 w-5 text-primary" />
            {t("dashboard.report.title")}
          </CardTitle>
          <CardDescription>
            {t("dashboard.report.subtitle")}
          </CardDescription>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link href="/leads" className="flex items-center gap-1">
            {t("dashboard.report.viewAll")}
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : leads.length === 0 ? (
          <div className="rounded-lg border border-dashed bg-muted/30 py-8 text-center">
            <Users className="h-10 w-10 mx-auto mb-2 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">
              {t("dashboard.report.noLeads")}
            </p>
            <Button variant="link" size="sm" className="mt-2" asChild>
              <Link href="/leads">{t("dashboard.report.startPipeline")}</Link>
            </Button>
          </div>
        ) : (
          <>
            <div className="flex gap-4">
              <div className="flex items-center gap-2 rounded-lg border bg-card px-4 py-2">
                <Users className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">
                  {t("dashboard.report.found")}: {leads.length}
                </span>
              </div>
              <div className="flex items-center gap-2 rounded-lg border bg-card px-4 py-2">
                <UserCheck className="h-4 w-4 text-green-600" />
                <span className="text-sm font-medium">
                  {t("dashboard.report.followed")}: {followedCount}
                </span>
              </div>
            </div>

            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("common.username")}</TableHead>
                    <TableHead>{t("leads.saved.niche")}</TableHead>
                    <TableHead className="text-center">{t("common.score")}</TableHead>
                    <TableHead className="text-center">{t("dashboard.report.followed")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentLeads.map((lead) => (
                    <TableRow key={lead.id}>
                      <TableCell className="font-medium">
                        <a
                          href={`https://instagram.com/${lead.username}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline"
                        >
                          @{lead.username}
                        </a>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="text-xs">
                          {lead.niche}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center font-medium">
                        {lead.total_score}
                      </TableCell>
                      <TableCell className="text-center">
                        {lead.followed ? (
                          <Badge variant="default" className="text-xs">
                            {t("dashboard.report.yes")}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground text-xs">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
