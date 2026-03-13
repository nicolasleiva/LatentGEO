import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  ExternalLink,
  FileText,
  Gauge,
  Github,
  Globe,
  Link as LinkIcon,
  PenSquare,
  Search,
  ShoppingBag,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";

import { Header } from "@/components/header";
import AuditPipelineDiagnostics, {
  type RuntimeDiagnosticEntry,
} from "@/components/audit-pipeline-diagnostics";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatStableDate } from "@/lib/dates";

import AuditDetailActionsClient from "./AuditDetailActionsClient";

export type AuditOverview = {
  id: number;
  url: string;
  domain?: string | null;
  status: string;
  progress: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  geo_score?: number | null;
  total_pages?: number | null;
  critical_issues?: number | null;
  high_issues?: number | null;
  medium_issues?: number | null;
  source?: string | null;
  language?: string | null;
  category?: string | null;
  market?: string | null;
  intake_profile?: {
    add_articles?: boolean;
    article_count?: number;
    improve_ecommerce_fixes?: boolean;
  } | null;
  diagnostics_summary?: RuntimeDiagnosticEntry[] | null;
  error_message?: string | null;
  competitor_count: number;
  fix_plan_count: number;
  report_ready: boolean;
  pagespeed_available: boolean;
  pdf_available: boolean;
  external_intelligence?: {
    category?: string;
    market?: string;
  } | null;
};

type AuditDetailCompletedPageProps = {
  locale: string;
  auditId: string;
  overview: AuditOverview;
};

const resolveCategory = (overview: AuditOverview) =>
  overview.category ??
  overview.external_intelligence?.category ??
  "Unclassified";

const resolveMarket = (overview: AuditOverview) =>
  overview.market ?? overview.external_intelligence?.market ?? "—";

const toolCardClassName =
  "group block rounded-2xl border border-border/70 bg-card p-6 transition-[transform,border-color,background-color] hover:-translate-y-1 hover:border-border hover:bg-muted/30";

export default function AuditDetailCompletedPage({
  locale,
  auditId,
  overview,
}: AuditDetailCompletedPageProps) {
  const localePrefix = `/${locale}`;
  const toolBase = `${localePrefix}/audits/${auditId}`;
  const articleCount = Math.max(
    1,
    Math.min(12, Number(overview.intake_profile?.article_count) || 3),
  );
  const geoArticleEngineHref = overview.intake_profile?.add_articles
    ? `${toolBase}/geo?tab=article-engine&articleCount=${articleCount}`
    : `${toolBase}/geo?tab=article-engine`;

  return (
    <div className="flex min-h-screen flex-col pb-20">
      <Header />

      <main className="container mx-auto flex-1 px-6 py-8">
        <Button
          asChild
          variant="ghost"
          className="mb-8 pl-0 text-muted-foreground hover:text-foreground"
        >
          <Link href={`${localePrefix}/audits`}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Queue
          </Link>
        </Button>

        <section className="glass-card relative mb-8 overflow-hidden p-8">
          <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-brand/10 blur-3xl" />
          <div className="absolute bottom-0 right-0 p-8 opacity-10">
            <Globe className="h-40 w-40 text-foreground" />
          </div>

          <div className="relative z-10 flex flex-col gap-8 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0 flex-1 space-y-4">
              <div className="flex flex-wrap items-center gap-3 text-xs uppercase tracking-wide text-muted-foreground">
                <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-emerald-600">
                  Completed
                </span>
                <span className="rounded-full border border-border bg-muted/40 px-3 py-1">
                  Progress {Math.round(overview.progress || 100)}%
                </span>
                <span className="rounded-full border border-border bg-muted/40 px-3 py-1">
                  Created {formatStableDate(overview.created_at)}
                </span>
                {overview.completed_at ? (
                  <span className="rounded-full border border-border bg-muted/40 px-3 py-1">
                    Completed {formatStableDate(overview.completed_at)}
                  </span>
                ) : null}
              </div>

              <div>
                <h1 className="break-all text-3xl font-semibold text-foreground md:text-4xl">
                  {overview.domain || overview.url}
                </h1>
                <p className="mt-2 flex items-center gap-2 break-all text-base text-muted-foreground">
                  <Globe className="h-4 w-4" />
                  {overview.url}
                </p>
              </div>

              {overview.error_message ? (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-700">
                  {overview.error_message}
                </div>
              ) : null}
            </div>

            <div className="space-y-4">
              <AuditDetailActionsClient
                auditId={auditId}
                hasPageSpeed={overview.pagespeed_available}
              />
              <div className="flex flex-wrap gap-3">
                <Button asChild className="glass-button px-6">
                  <Link href={`${toolBase}/geo`}>
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Open GEO Command Center
                  </Link>
                </Button>
                {overview.source === "hubspot" ? (
                  <Button
                    asChild
                    className="bg-[#ff7a59] px-6 text-white hover:bg-[#ff7a59]/90"
                  >
                    <Link href={`${toolBase}/hubspot-apply`}>
                      <Sparkles className="mr-2 h-4 w-4" />
                      Apply to HubSpot
                    </Link>
                  </Button>
                ) : null}
              </div>
            </div>
          </div>
        </section>

        <section className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          <div className="glass-panel rounded-2xl p-5">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
              GEO Score
            </div>
            <div className="text-3xl font-semibold text-foreground">
              {typeof overview.geo_score === "number"
                ? Math.round(overview.geo_score)
                : 0}
            </div>
          </div>
          <div className="glass-panel rounded-2xl p-5">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
              Pages Audited
            </div>
            <div className="text-3xl font-semibold text-foreground">
              {overview.total_pages || 0}
            </div>
          </div>
          <div className="glass-panel rounded-2xl p-5">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
              Critical Issues
            </div>
            <div className="text-3xl font-semibold text-red-600">
              {overview.critical_issues || 0}
            </div>
          </div>
          <div className="glass-panel rounded-2xl p-5">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
              Competitors
            </div>
            <div className="text-3xl font-semibold text-foreground">
              {overview.competitor_count || 0}
            </div>
          </div>
        </section>

        <section className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="glass-panel rounded-2xl p-5">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
              Context
            </div>
            <div className="text-lg font-semibold text-foreground">
              {resolveCategory(overview)}
            </div>
            <div className="mt-1 text-sm text-muted-foreground">
              Market: {resolveMarket(overview)} · Language:{" "}
              {overview.language || "en"}
            </div>
          </div>

          <div className="glass-panel rounded-2xl p-5">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
              Coverage
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge
                variant={overview.pagespeed_available ? "default" : "outline"}
              >
                PageSpeed
              </Badge>
              <Badge
                variant={overview.competitor_count > 0 ? "default" : "outline"}
              >
                Competitors
              </Badge>
              <Badge
                variant={overview.fix_plan_count > 0 ? "default" : "outline"}
              >
                Fix Plan
              </Badge>
              <Badge variant={overview.report_ready ? "default" : "outline"}>
                Narrative
              </Badge>
            </div>
          </div>

          <div className="glass-panel rounded-2xl p-5">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
              Delivery Status
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">
                  Execution plan items
                </span>
                <span className="font-semibold text-foreground">
                  {overview.fix_plan_count}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Narrative report</span>
                <span className="font-semibold text-foreground">
                  {overview.report_ready ? "Ready" : "Pending PDF generation"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">PDF export</span>
                <span className="font-semibold text-foreground">
                  {overview.pdf_available ? "Available" : "Not generated"}
                </span>
              </div>
            </div>
          </div>
        </section>

        <AuditPipelineDiagnostics
          diagnostics={overview.diagnostics_summary}
          errorMessage={overview.error_message}
          className="mb-8"
        />

        <section className="glass-card mb-8 p-8">
          <div className="mb-6 flex flex-col gap-2">
            <h2 className="text-2xl font-bold text-foreground">
              Execution Tool Suite
            </h2>
            <p className="text-sm text-muted-foreground">
              Jump directly into the tools that turn this audit into
              deliverables.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            <Link
              href={`${toolBase}/geo`}
              data-testid="geo-tool-card-dashboard"
              className={toolCardClassName}
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="rounded-xl bg-brand/10 p-3">
                  <Target className="h-6 w-6 text-brand" />
                </div>
                <ExternalLink className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-foreground">
                GEO Dashboard
              </h3>
              <p className="text-sm text-muted-foreground">
                Monitor citations, discovery opportunities, and assistant-facing
                visibility.
              </p>
            </Link>

            <Link href={`${toolBase}/keywords`} className={toolCardClassName}>
              <div className="mb-3 flex items-start justify-between">
                <div className="rounded-xl bg-brand/10 p-3">
                  <Search className="h-6 w-6 text-brand" />
                </div>
                <ExternalLink className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-foreground">
                Keyword Discovery
              </h3>
              <p className="text-sm text-muted-foreground">
                Expand prompt coverage, intent mapping, and demand capture.
              </p>
            </Link>

            <Link href={`${toolBase}/backlinks`} className={toolCardClassName}>
              <div className="mb-3 flex items-start justify-between">
                <div className="rounded-xl bg-emerald-500/10 p-3">
                  <LinkIcon className="h-6 w-6 text-emerald-600" />
                </div>
                <ExternalLink className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-foreground">
                Backlink Intelligence
              </h3>
              <p className="text-sm text-muted-foreground">
                Evaluate authority signals and build the linking roadmap.
              </p>
            </Link>

            <Link
              href={`${toolBase}/rank-tracking`}
              className={toolCardClassName}
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="rounded-xl bg-amber-500/10 p-3">
                  <TrendingUp className="h-6 w-6 text-amber-600" />
                </div>
                <ExternalLink className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-foreground">
                Rank Tracking
              </h3>
              <p className="text-sm text-muted-foreground">
                Track search movement and visibility drift over time.
              </p>
            </Link>

            <Link href={`${toolBase}/ai-content`} className={toolCardClassName}>
              <div className="mb-3 flex items-start justify-between">
                <div className="rounded-xl bg-fuchsia-500/10 p-3">
                  <Sparkles className="h-6 w-6 text-fuchsia-600" />
                </div>
                <ExternalLink className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-foreground">
                AI Content Strategy
              </h3>
              <p className="text-sm text-muted-foreground">
                Generate topic gaps, FAQs, and outlines grounded in the audit.
              </p>
            </Link>

            <Link
              href={`${toolBase}/geo?tab=commerce`}
              data-testid="geo-tool-card-commerce"
              className={toolCardClassName}
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="rounded-xl bg-pink-500/10 p-3">
                  <ShoppingBag className="h-6 w-6 text-pink-600" />
                </div>
                <ExternalLink className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-foreground">
                Ecommerce Query Analyzer
              </h3>
              <p className="text-sm text-muted-foreground">
                Upgrade product positioning, query capture, and catalog signals.
              </p>
            </Link>

            <Link
              href={geoArticleEngineHref}
              data-testid="geo-tool-card-article-engine"
              className={toolCardClassName}
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="rounded-xl bg-sky-500/10 p-3">
                  <PenSquare className="h-6 w-6 text-sky-600" />
                </div>
                <ExternalLink className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-foreground">
                Article Engine
              </h3>
              <p className="text-sm text-muted-foreground">
                Convert the audit into production-ready editorial briefs and
                content packs.
              </p>
            </Link>

            <Link
              href={`${toolBase}/github-auto-fix`}
              className={toolCardClassName}
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="rounded-xl bg-slate-500/10 p-3">
                  <Github className="h-6 w-6 text-slate-700" />
                </div>
                <ExternalLink className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-foreground">
                GitHub Auto-Fix
              </h3>
              <p className="text-sm text-muted-foreground">
                Prepare implementation-ready fixes and PR guidance for
                engineering.
              </p>
            </Link>

            <Link
              href={`${toolBase}/odoo-delivery`}
              className={toolCardClassName}
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="rounded-xl bg-indigo-500/10 p-3">
                  <Gauge className="h-6 w-6 text-indigo-600" />
                </div>
                <ExternalLink className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-foreground">
                Odoo Delivery Pack
              </h3>
              <p className="text-sm text-muted-foreground">
                Package Odoo fixes, article recommendations, and ecommerce
                delivery inputs.
              </p>
            </Link>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="glass-card p-6 lg:col-span-2">
            <div className="mb-4 flex items-center gap-3">
              <FileText className="h-5 w-5 text-brand" />
              <h2 className="text-xl font-semibold text-foreground">
                Report Materialization
              </h2>
            </div>
            <p className="text-sm leading-6 text-muted-foreground">
              The narrative report and full execution plan are generated as part
              of the PDF delivery flow. Use the export action above to
              materialize the board-ready report and then continue with Odoo,
              GitHub, GEO, or HubSpot execution from the tool suite.
            </p>
          </div>

          <div className="glass-card p-6">
            <div className="mb-4 flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              <h2 className="text-xl font-semibold text-foreground">
                Immediate Priorities
              </h2>
            </div>
            <div className="space-y-2 text-sm text-muted-foreground">
              <div>Critical issues: {overview.critical_issues || 0}</div>
              <div>High issues: {overview.high_issues || 0}</div>
              <div>Medium issues: {overview.medium_issues || 0}</div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
