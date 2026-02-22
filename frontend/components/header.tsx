"use client";

import { useCallback, useMemo, type ComponentType } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import {
  Sparkles,
  LayoutDashboard,
  FileText,
  Settings,
  BarChart3,
  Book,
  Tag,
  Menu,
  Activity,
  LogOut,
  Loader2,
  Rocket,
} from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { withLocale } from "@/lib/locale-routing";
import { isKnownLocale } from "@/lib/locales";

type NavItem = {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
};

const guestNavItems: NavItem[] = [
  { href: "/", label: "Platform", icon: Sparkles },
  { href: "/pricing", label: "Pricing", icon: Tag },
  { href: "/docs", label: "Playbooks", icon: Book },
];
const appNavItems: NavItem[] = [
  { href: "/audits", label: "Audits", icon: LayoutDashboard },
  { href: "/analytics", label: "Insights", icon: BarChart3 },
  { href: "/exports", label: "Exports", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Header() {
  const pathname = usePathname();
  const { user, isLoading } = useUser();

  const pathWithoutLocale = useMemo(() => {
    if (!pathname) return "/";
    const segments = pathname.split("/").filter(Boolean);
    if (segments[0] && isKnownLocale(segments[0])) {
      return `/${segments.slice(1).join("/")}` || "/";
    }
    return pathname;
  }, [pathname]);

  const activeAuditMatch = pathWithoutLocale.match(/^\/audits\/([^/]+)/);
  const activeAuditHref = activeAuditMatch
    ? `/audits/${activeAuditMatch[1]}`
    : null;

  const withCurrentLocale = useCallback(
    (href: string) => withLocale(pathname, href),
    [pathname],
  );

  const navItems: NavItem[] = useMemo(() => {
    if (!user) return guestNavItems;
    if (!activeAuditHref) return appNavItems;
    return [
      { href: activeAuditHref, label: "Live Audit", icon: Activity },
      ...appNavItems,
    ];
  }, [user, activeAuditHref]);

  const isActiveLink = (href: string) => {
    const target = withCurrentLocale(href).replace(/\/+$/, "");
    const current = (pathname || "").replace(/\/+$/, "");
    if (!target) return current === "";
    return current === target || current.startsWith(`${target}/`);
  };

  const profileLabel = user?.name || user?.email || "User";

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/70 bg-background/85 backdrop-blur-xl">
      <div className="container flex h-20 items-center justify-between px-4 sm:px-6">
        <Link href={withCurrentLocale("/")} className="flex items-center gap-3 group">
          <div className="p-2.5 bg-foreground/5 rounded-2xl border border-foreground/10 group-hover:bg-foreground/10 transition-colors">
            <Sparkles className="h-6 w-6 text-foreground" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-xl font-semibold tracking-tight">
              LatentGEO<span className="text-brand">.ai</span>
            </span>
            <span className="hidden xl:block text-[11px] tracking-wider uppercase text-muted-foreground mt-1">
              AI search operations
            </span>
          </div>
        </Link>

        <nav className="hidden lg:flex items-center gap-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActiveLink(item.href);
            return (
              <Link
                key={item.href}
                href={withCurrentLocale(item.href)}
                className={cn(
                  "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-card text-foreground border border-border/70 shadow-sm"
                    : "text-foreground/70 hover:bg-foreground/5 hover:text-foreground border border-transparent",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          {user && activeAuditHref && (
            <div className="hidden xl:flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-soft-pulse" />
              Audit stream active
            </div>
          )}
          <ThemeToggle />

          {isLoading ? (
            <div className="hidden md:flex items-center gap-2 text-foreground/60 px-2">
              <Loader2 className="w-4 h-4 animate-spin" />
            </div>
          ) : user ? (
            <div className="hidden md:flex items-center gap-2">
              <Button asChild size="sm" className="rounded-xl">
                <Link href={withCurrentLocale("/")}>
                  <Rocket className="h-4 w-4" />
                  Run audit
                </Link>
              </Button>

              <div className="hidden xl:flex items-center gap-2 px-3 py-1.5 bg-background/70 rounded-xl border border-border/70">
                <div className="relative w-7 h-7 rounded-full overflow-hidden border border-border/60 bg-muted/50 flex items-center justify-center">
                  {user.picture ? (
                    <Image
                      src={user.picture}
                      alt={profileLabel}
                      fill
                      className="object-cover"
                      unoptimized
                    />
                  ) : (
                    <span className="text-xs font-semibold text-foreground/80">
                      {profileLabel.charAt(0).toUpperCase()}
                    </span>
                  )}
                </div>
                <span className="text-sm font-medium text-foreground/80 max-w-[150px] truncate">
                  {profileLabel}
                </span>
              </div>

              <Button
                asChild
                variant="ghost"
                size="sm"
                className="rounded-xl text-red-500 hover:text-red-600 hover:bg-red-500/10"
              >
                <a href="/auth/logout">
                  <LogOut className="h-4 w-4" />
                  Logout
                </a>
              </Button>
            </div>
          ) : (
            <div className="hidden md:flex items-center gap-2">
              <Button asChild variant="ghost" size="sm" className="rounded-xl">
                <a href="/auth/login">Sign in</a>
              </Button>
              <Button asChild size="sm" className="rounded-xl">
                <a href="/auth/login">Start audit</a>
              </Button>
            </div>
          )}

          <Sheet>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                className="md:hidden rounded-xl"
                aria-label="Open navigation"
              >
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[88vw] sm:w-[420px]">
              <SheetHeader>
                <SheetTitle>Navigation</SheetTitle>
                <SheetDescription>
                  {user
                    ? "Signed in workspace navigation."
                    : "Explore product and start your first audit."}
                </SheetDescription>
              </SheetHeader>

              <div className="px-4 pb-6 space-y-6">
                <div className="space-y-2">
                  {navItems.map((item) => {
                    const Icon = item.icon;
                    const active = isActiveLink(item.href);
                    return (
                      <SheetClose asChild key={item.href}>
                        <Link
                          href={withCurrentLocale(item.href)}
                          className={cn(
                            "flex items-center gap-3 rounded-xl border px-4 py-3 text-sm font-medium",
                            active
                              ? "bg-foreground/10 border-foreground/20 text-foreground"
                              : "bg-background/70 border-border text-foreground/80",
                          )}
                        >
                          <Icon className="h-4 w-4" />
                          {item.label}
                        </Link>
                      </SheetClose>
                    );
                  })}
                </div>

                {isLoading ? (
                  <div className="flex items-center gap-2 text-foreground/60 text-sm">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading session...
                  </div>
                ) : user ? (
                  <div className="space-y-2">
                    <SheetClose asChild>
                      <Link
                        href={withCurrentLocale("/")}
                        className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90"
                      >
                        <Rocket className="h-4 w-4" />
                        Run audit
                      </Link>
                    </SheetClose>
                    <SheetClose asChild>
                      <a
                        href="/auth/logout"
                        className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-red-500/20 bg-transparent px-4 text-sm font-medium text-red-600 hover:bg-red-500/10"
                      >
                        <LogOut className="h-4 w-4" />
                        Logout
                      </a>
                    </SheetClose>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <SheetClose asChild>
                      <a
                        href="/auth/login"
                        className="inline-flex h-10 w-full items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90"
                      >
                        Start audit
                      </a>
                    </SheetClose>
                    <SheetClose asChild>
                      <a
                        href="/auth/login"
                        className="inline-flex h-10 w-full items-center justify-center rounded-lg border border-border bg-transparent px-4 text-sm font-medium hover:bg-accent/70"
                      >
                        Sign in
                      </a>
                    </SheetClose>
                  </div>
                )}
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
