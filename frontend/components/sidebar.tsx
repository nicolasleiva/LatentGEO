"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  BarChart2,
  Link2,
  Zap,
  Settings,
  Globe,
  Bot,
  FileText,
  Download,
  Github,
  Webhook,
  Activity,
  Radio,
  RotateCcw,
  Wand2,
  Sparkles,
} from "lucide-react";
import { withLocale } from "@/lib/locale-routing";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();
  const route = (href: string) => withLocale(pathname, href);

  // Check if we are inside an audit context
  const auditMatch = pathname.match(/\/audits\/(\d+)/);
  const currentAuditId = auditMatch ? auditMatch[1] : null;

  return (
    <div className="fixed inset-y-0 left-0 z-50 w-64 bg-sidebar border-r border-sidebar-border flex flex-col">
      <div className="h-16 flex items-center px-6 border-b border-sidebar-border">
        <div className="flex items-center gap-2 font-semibold text-lg tracking-tight">
          <Sparkles className="h-5 w-5 text-primary" />
          <span>LatentGEO.ai</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-6 px-3 space-y-1">
        <div className="px-3 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Platform
        </div>

        <Link
          href={route("/")}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            pathname === route("/")
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
          )}
        >
          <LayoutDashboard className="h-4 w-4" />
          Overview
        </Link>

        <Link
          href={route("/audits")}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            pathname === route("/audits")
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
          )}
        >
          <Search className="h-4 w-4" />
          Audit History
        </Link>

        <Link
          href={route("/reports")}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            pathname === route("/reports")
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
          )}
        >
          <FileText className="h-4 w-4" />
          Reports
        </Link>

        <Link
          href={route("/exports")}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            pathname === route("/exports")
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
          )}
        >
          <Download className="h-4 w-4" />
          Exports
        </Link>

        {currentAuditId && (
          <>
            <div className="mt-8 px-3 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Current Audit #{currentAuditId}
            </div>

            <Link
              href={route(`/audits/${currentAuditId}`)}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                pathname === route(`/audits/${currentAuditId}`)
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
              )}
            >
              <BarChart2 className="h-4 w-4" />
              Dashboard
            </Link>

            <Link
              href={route(`/audits/${currentAuditId}/rank-tracking`)}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                pathname.includes("rank-tracking")
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
              )}
            >
              <Globe className="h-4 w-4" />
              Rank Tracking
            </Link>

            <Link
              href={route(`/audits/${currentAuditId}/backlinks`)}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                pathname.includes("backlinks")
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
              )}
            >
              <Link2 className="h-4 w-4" />
              Link Analysis
            </Link>

            <Link
              href={route(`/audits/${currentAuditId}/llm-visibility`)}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                pathname.includes("llm-visibility")
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
              )}
            >
              <Bot className="h-4 w-4" />
              AI Visibility
            </Link>
          </>
        )}

        <div className="mt-8 px-3 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Tools
        </div>

        <Link
          href={route("/tools/content-editor")}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            pathname.includes("content-editor")
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
          )}
        >
          <Wand2 className="h-4 w-4" />
          GEO Content Editor
        </Link>

        <div className="mt-8 px-3 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Integrations
        </div>

        <Link
          href={route("/integrations/hubspot/connect")}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            pathname.includes("/integrations/hubspot")
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
          )}
        >
          <Zap className="h-4 w-4" />
          HubSpot
        </Link>

        <Link
          href={route("/integrations/hubspot/rollback")}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            pathname === route("/integrations/hubspot/rollback")
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
          )}
        >
          <RotateCcw className="h-4 w-4" />
          HubSpot Rollback
        </Link>

        <Link
          href={route("/integrations/github")}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            pathname === route("/integrations/github")
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
          )}
        >
          <Github className="h-4 w-4" />
          GitHub Admin
        </Link>

        <div className="mt-8 px-3 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Ops
        </div>

        <Link
          href={route("/ops/health")}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            pathname === route("/ops/health")
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
          )}
        >
          <Activity className="h-4 w-4" />
          Health
        </Link>

        <Link
          href={route("/ops/webhooks")}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            pathname === route("/ops/webhooks")
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
          )}
        >
          <Webhook className="h-4 w-4" />
          Webhooks
        </Link>

        <Link
          href={route("/ops/realtime")}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            pathname === route("/ops/realtime")
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
          )}
        >
          <Radio className="h-4 w-4" />
          Realtime
        </Link>
      </div>

      <div className="p-4 border-t border-sidebar-border">
        <div className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-sidebar-accent/50 cursor-pointer transition-colors">
          <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-medium">
            JD
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">John Doe</p>
            <p className="text-xs text-muted-foreground truncate">Pro Plan</p>
          </div>
          <Settings className="h-4 w-4 text-muted-foreground" />
        </div>
      </div>
    </div>
  );
}
