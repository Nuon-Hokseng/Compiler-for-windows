"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  Crosshair,
  Instagram,
  Globe,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { SignedIn, SignedOut, UserButton, SignInButton } from "@clerk/nextjs";
import { useI18n } from "@/contexts/I18nContext";
import { Button } from "@/components/ui/button";

const linkKeys = [
  { href: "/", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { href: "/accounts", labelKey: "nav.accounts", icon: Users },
  { href: "/leads", labelKey: "nav.pipeline", icon: Crosshair },
];

export function SidebarNav() {
  const pathname = usePathname();
  const { t, locale, setLocale } = useI18n();

  return (
    <aside className="hidden md:flex w-64 flex-col border-r bg-card">
      {/* Brand */}
      <div className="flex items-center gap-2 px-6 py-5 border-b">
        <Instagram className="h-6 w-6 text-primary" />
        <span className="font-semibold text-lg tracking-tight">{t("nav.brand")}</span>
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {linkKeys.map(({ href, labelKey, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {t(labelKey)}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            {t("nav.footer")}
          </p>
          <SignedIn>
            <UserButton />
          </SignedIn>
          <SignedOut>
            <SignInButton />
          </SignedOut>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 text-xs text-muted-foreground"
          onClick={() => setLocale(locale === "en" ? "ja" : "en")}
        >
          <Globe className="h-3.5 w-3.5" />
          {locale === "en" ? "日本語に切替" : "Switch to English"}
        </Button>
      </div>
    </aside>
  );
}
