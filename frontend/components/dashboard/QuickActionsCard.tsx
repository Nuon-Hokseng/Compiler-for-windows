"use client";

import Link from "next/link";
import { useI18n } from "@/contexts/I18nContext";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { UserPlus, Crosshair, Zap } from "lucide-react";

const actions = [
  {
    href: "/accounts?add=1",
    icon: UserPlus,
    titleKey: "dashboard.quickActions.addAccount",
    descKey: "dashboard.quickActions.addAccountDesc",
  },
  {
    href: "/leads",
    icon: Crosshair,
    titleKey: "dashboard.quickActions.runPipeline",
    descKey: "dashboard.quickActions.runPipelineDesc",
  },
];

export function QuickActionsCard() {
  const { t } = useI18n();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Zap className="h-5 w-5 text-primary" />
          {t("dashboard.quickActions.title")}
        </CardTitle>
        <CardDescription>
          {t("dashboard.quickActions.subtitle")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {actions.map(({ href, icon: Icon, titleKey, descKey }) => (
            <Button
              key={href}
              variant="outline"
              className="h-auto w-full flex-col items-start gap-1.5 px-4 py-4 text-left"
              asChild
            >
              <Link
                href={href}
                className="flex w-full flex-col items-start gap-1.5"
              >
                <span className="flex items-center gap-2">
                  <Icon className="h-4 w-4" />
                  <span className="font-medium">{t(titleKey)}</span>
                </span>
                <span className="text-xs font-normal text-muted-foreground">
                  {t(descKey)}
                </span>
              </Link>
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
