"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  Instagram,
  Menu,
  Users,
  Crosshair,
  Globe,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetTitle,
} from "@/components/ui/sheet";
import { SignedIn, UserButton } from "@clerk/nextjs";
import { useI18n } from "@/contexts/I18nContext";

const linkKeys = [
  { href: "/", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { href: "/accounts", labelKey: "nav.accounts", icon: Users },
  { href: "/leads", labelKey: "nav.pipeline", icon: Crosshair },
];

export function MobileNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { t, locale, setLocale } = useI18n();

  return (
    <div className="md:hidden flex items-center justify-between border-b px-4 py-3">
      <div className="flex items-center gap-2">
        <Instagram className="h-5 w-5 text-primary" />
        <span className="font-semibold">{t("nav.brand")}</span>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setLocale(locale === "en" ? "ja" : "en")}
        >
          <Globe className="h-4 w-4" />
        </Button>

        <SignedIn>
          <UserButton />
        </SignedIn>

        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon">
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-64 p-0">
            <SheetTitle className="px-6 py-5 border-b font-semibold text-lg">
              {t("nav.brand")}
            </SheetTitle>
            <nav className="px-3 py-4 space-y-1">
              {linkKeys.map(({ href, labelKey, icon: Icon }) => {
                const active =
                  href === "/" ? pathname === "/" : pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setOpen(false)}
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
          </SheetContent>
        </Sheet>
      </div>
    </div>
  );
}
