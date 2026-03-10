import Link from "next/link";
import { Suspense } from "react";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { serverJson } from "@/lib/server-api";
import { ArrowLeft, TrendingUp, TrendingDown, AlertCircle } from "lucide-react";

type AnalyticsPageProps = {
  auditId: number;
  locale: string;
  analytics: any;
};

type ScoreColorFn = (score: number) => string;
type ScoreBgFn = (score: number) => string;

const getScoreColor: ScoreColorFn = (score) => {
  if (score >= 8) return "text-emerald-600";
  if (score >= 5) return "text-amber-500";
  return "text-red-500";
};

const getScoreBg: ScoreBgFn = (score) => {
  if (score >= 8) return "bg-emerald-500/10 border-emerald-500/20";
  if (score >= 5) return "bg-amber-500/10 border-amber-500/20";
  return "bg-red-500/10 border-red-500/20";
};

function ScoresGrid({ scores }: { scores: Record<string, number> }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6 animate-fade-up">
      {Object.entries(scores).map(([key, value]) => (
        <Card
          key={key}
          className={`glass-card border p-4 ${getScoreBg(value)}`}
        >
          <div className="mb-1 text-xs uppercase text-muted-foreground">
            {key.replace("_score", "").replace("_", " ")}
          </div>
          <div className={`text-2xl font-bold ${getScoreColor(value)}`}>
            {value.toFixed(1)}
          </div>
          <div className="text-xs text-muted-foreground/70">/ 10.0</div>
        </Card>
      ))}
    </div>
  );
}

function IssuesSummary({ issues }: { issues: any }) {
  return (
    <Card className="glass-card p-6 animate-fade-up">
      <h2 className="mb-6 text-xl font-semibold text-foreground">
        Issues Summary
      </h2>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <div className="mb-1 text-xs text-red-600">CRITICAL</div>
          <div className="text-3xl font-semibold text-red-500">
            {issues.critical}
          </div>
        </div>
        <div className="rounded-lg border border-orange-500/20 bg-orange-500/10 p-4">
          <div className="mb-1 text-xs text-orange-600">HIGH</div>
          <div className="text-3xl font-semibold text-orange-500">
            {issues.high}
          </div>
        </div>
        <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-4">
          <div className="mb-1 text-xs text-amber-600">MEDIUM</div>
          <div className="text-3xl font-semibold text-amber-500">
            {issues.medium}
          </div>
        </div>
        <div className="rounded-lg border border-brand/20 bg-brand/10 p-4">
          <div className="mb-1 text-xs text-brand">LOW</div>
          <div className="text-3xl font-semibold text-brand">{issues.low}</div>
        </div>
      </div>
      <div className="mt-4 rounded-lg border border-border p-4 glass-panel">
        <div className="text-sm text-muted-foreground">Total Issues</div>
        <div className="text-2xl font-semibold text-foreground">
          {issues.total}
        </div>
      </div>
    </Card>
  );
}

function PagesPerformance({ pages }: { pages: any[] }) {
  return (
    <Card className="glass-card p-6 animate-fade-up">
      <h2 className="mb-6 text-xl font-semibold text-foreground">
        Pages Performance
      </h2>
      <div className="space-y-2">
        {pages.slice(0, 10).map((page: any) => (
          <div
            key={page.url || page.path || page.id}
            className="flex items-center justify-between rounded-lg border border-border p-4 glass-panel transition-colors hover:bg-muted/50"
          >
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-foreground">
                {page.path || "/"}
              </div>
              <div className="truncate text-xs text-muted-foreground">
                {page.url}
              </div>
            </div>
            <div className="ml-4 flex items-center gap-4">
              <div className="text-center">
                <div className="text-xs text-muted-foreground">Score</div>
                <div
                  className={`text-lg font-bold ${getScoreColor(page.overall_score)}`}
                >
                  {page.overall_score.toFixed(1)}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-muted-foreground">Issues</div>
                <div className="text-lg font-bold text-red-500">
                  {page.issues.critical +
                    page.issues.high +
                    page.issues.medium +
                    page.issues.low}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
      {pages.length > 10 && (
        <div className="mt-4 text-center text-sm text-muted-foreground">
          Showing 10 of {pages.length} pages
        </div>
      )}
    </Card>
  );
}

function DeferredSectionCard() {
  return (
    <Card className="glass-card p-6">
      <div className="h-6 w-40 animate-pulse rounded bg-muted/60" />
      <div className="mt-6 space-y-3">
        <div className="h-20 animate-pulse rounded-xl bg-muted/40" />
        <div className="h-20 animate-pulse rounded-xl bg-muted/40" />
      </div>
    </Card>
  );
}

async function CompetitorBenchmarkSection({ auditId }: { auditId: number }) {
  const competitorData: any = await serverJson(
    `/api/v1/analytics/competitors/${auditId}`,
  ).catch(() => null);

  if (!competitorData) {
    return null;
  }

  return (
    <Card className="glass-card p-6 animate-fade-up">
      <h2 className="mb-6 text-xl font-semibold text-foreground">
        Competitor Benchmark
      </h2>
      <div className="mb-6 grid grid-cols-1 gap-6 md:grid-cols-3">
        <div className="rounded-xl border border-border p-6 text-center glass-panel">
          <div className="mb-2 text-sm text-muted-foreground">
            Your GEO Score
          </div>
          <div
            className={`text-4xl font-semibold ${getScoreColor(competitorData.your_geo_score)}`}
          >
            {competitorData.your_geo_score.toFixed(1)}%
          </div>
        </div>
        <div className="rounded-xl border border-border p-6 text-center glass-panel">
          <div className="mb-2 text-sm text-muted-foreground">
            Competitor Average
          </div>
          <div className="text-4xl font-semibold text-foreground">
            {competitorData.average_competitor_score.toFixed(1)}%
          </div>
        </div>
        <div className="rounded-xl border border-border p-6 text-center glass-panel">
          <div className="mb-2 text-sm text-muted-foreground">Position</div>
          <div className="flex items-center justify-center gap-2">
            {competitorData.your_geo_score >
            competitorData.average_competitor_score ? (
              <>
                <TrendingUp className="h-6 w-6 text-emerald-500" />
                <span className="text-lg font-semibold text-emerald-600">
                  Above Average
                </span>
              </>
            ) : (
              <>
                <TrendingDown className="h-6 w-6 text-red-500" />
                <span className="text-lg font-semibold text-red-500">
                  Below Average
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {competitorData.competitors?.length > 0 && (
        <div className="space-y-2">
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">
            Top Competitors
          </h3>
          {competitorData.competitors
            .slice(0, 5)
            .map((comp: any, idx: number) => (
              <div
                key={comp.url || comp.domain || comp.name}
                className="flex items-center justify-between rounded-lg border border-border p-3 glass-panel"
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${
                      idx === 0
                        ? "bg-amber-500/10 text-amber-600"
                        : "bg-muted/60 text-muted-foreground"
                    }`}
                  >
                    {idx + 1}
                  </div>
                  <div>
                    <div className="font-medium text-foreground">
                      {comp.domain}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {comp.url}
                    </div>
                  </div>
                </div>
                <div
                  className={`text-lg font-bold ${getScoreColor(comp.geo_score)}`}
                >
                  {comp.geo_score.toFixed(1)}%
                </div>
              </div>
            ))}
        </div>
      )}
    </Card>
  );
}

async function IssuesByPrioritySection({ auditId }: { auditId: number }) {
  const issuesData: any = await serverJson(
    `/api/v1/analytics/issues/${auditId}`,
  ).catch(() => null);

  if (!issuesData || !issuesData.by_priority) {
    return null;
  }

  return (
    <Card className="glass-card p-6 animate-fade-up">
      <h2 className="mb-6 text-xl font-semibold text-foreground">
        Issues by Priority ({issuesData.total_issues} total)
      </h2>
      <div className="space-y-6">
        {Object.entries(issuesData.by_priority).map(
          ([priority, items]: [string, any]) =>
            items.length > 0 ? (
              <div key={priority}>
                <h3
                  className={`mb-3 text-sm font-medium ${
                    priority === "CRITICAL"
                      ? "text-red-500"
                      : priority === "HIGH"
                        ? "text-orange-500"
                        : priority === "MEDIUM"
                          ? "text-amber-500"
                          : "text-brand"
                  }`}
                >
                  {priority} ({items.length})
                </h3>
                <div className="space-y-2">
                  {items.slice(0, 5).map((issue: any) => (
                    <div
                      key={
                        issue.description ||
                        issue.page_path ||
                        JSON.stringify(issue)
                      }
                      className="rounded-lg border border-border p-3 text-sm glass-panel"
                    >
                      <div className="mb-1 font-medium text-foreground">
                        {issue.description}
                      </div>
                      {issue.page_path && (
                        <div className="mb-1 text-xs text-muted-foreground">
                          Page: {issue.page_path}
                        </div>
                      )}
                      {issue.suggestion && (
                        <div className="text-xs text-muted-foreground">
                          💡 {issue.suggestion}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : null,
        )}
      </div>
    </Card>
  );
}

export default function AuditAnalyticsPageClient({
  auditId,
  locale,
  analytics,
}: AnalyticsPageProps) {
  if (!analytics) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <Card className="glass-card p-12 text-center">
          <AlertCircle className="mx-auto mb-4 h-16 w-16 text-red-500" />
          <h3 className="mb-2 text-xl font-semibold text-foreground">
            Analytics Not Available
          </h3>
          <Button asChild className="glass-button-primary">
            <Link href={`/${locale}/audits/${auditId}`}>Back to Audit</Link>
          </Button>
        </Card>
      </div>
    );
  }

  const { scores, issues, pages, domain, is_ymyl, category } = analytics;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="mx-auto max-w-7xl px-6 py-12">
        <div className="mb-8 animate-fade-up">
          <div className="mb-2 flex items-center gap-4">
            <Button asChild variant="ghost" className="text-muted-foreground">
              <Link href={`/${locale}/audits/${auditId}`}>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Audit
              </Link>
            </Button>
            <div className="h-6 w-px bg-border" />
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
              Analytics: {domain}
            </h1>
          </div>
          <div className="flex items-center gap-2">
            {is_ymyl && (
              <Badge className="border-amber-500/30 bg-amber-500/10 text-amber-600">
                YMYL
              </Badge>
            )}
            {category && (
              <Badge
                variant="outline"
                className="border-border/70 bg-muted/40 text-muted-foreground"
              >
                {category}
              </Badge>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <ScoresGrid scores={scores} />
          <IssuesSummary issues={issues} />
          <PagesPerformance pages={pages} />
          <Suspense fallback={<DeferredSectionCard />}>
            <CompetitorBenchmarkSection auditId={auditId} />
          </Suspense>
          <Suspense fallback={<DeferredSectionCard />}>
            <IssuesByPrioritySection auditId={auditId} />
          </Suspense>
        </div>
      </main>
    </div>
  );
}
