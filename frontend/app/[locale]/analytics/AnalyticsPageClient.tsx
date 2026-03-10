import Link from "next/link";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle,
  Loader2,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";

import { Header } from "@/components/header";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import AnalyticsHistoryExplorer from "./AnalyticsHistoryExplorer";

type AnalyticsPageClientProps = {
  locale: string;
  dashboardData: any;
};

export default function AnalyticsPageClient({
  locale,
  dashboardData,
}: AnalyticsPageClientProps) {
  if (!dashboardData) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <Header />
        <main className="flex min-h-[calc(100vh-6rem)] items-center justify-center p-6">
          <Card className="glass-card max-w-md p-12 text-center">
            <AlertTriangle className="mx-auto mb-4 h-16 w-16 text-amber-500" />
            <h2 className="mb-2 text-xl font-semibold text-foreground">
              No Data Available
            </h2>
            <p className="text-muted-foreground">
              Unable to load analytics data.
            </p>
          </Card>
        </main>
      </div>
    );
  }

  const { summary, recent_audits: recentAudits, metrics } = dashboardData;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="mx-auto max-w-7xl px-6 py-12">
        <div className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Visibility Command Center
          </h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Monitor execution health, queue throughput, and competitive AI
            visibility trends.
          </p>
        </div>

        <div className="mx-auto max-w-7xl space-y-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card className="glass-card p-6">
              <div className="mb-2 flex items-center justify-between">
                <BarChart3 className="h-5 w-5 text-brand" />
                <Badge
                  variant="outline"
                  className="border-sky-200 bg-sky-100 text-sky-800"
                >
                  Total
                </Badge>
              </div>
              <div className="mb-1 text-3xl font-semibold text-foreground">
                {summary.total_audits}
              </div>
              <div className="text-sm text-muted-foreground">
                Audits in system
              </div>
            </Card>

            <Card className="glass-card p-6">
              <div className="mb-2 flex items-center justify-between">
                <CheckCircle className="h-5 w-5 text-emerald-500" />
                <Badge
                  variant="outline"
                  className="border-emerald-200 bg-emerald-100 text-emerald-800"
                >
                  {summary.success_rate.toFixed(0)}%
                </Badge>
              </div>
              <div className="mb-1 text-3xl font-semibold text-foreground">
                {summary.completed_audits}
              </div>
              <div className="text-sm text-muted-foreground">
                Successfully completed
              </div>
            </Card>

            <Card className="glass-card p-6">
              <div className="mb-2 flex items-center justify-between">
                <Loader2 className="h-5 w-5 animate-soft-pulse text-amber-500" />
                <Badge
                  variant="outline"
                  className="border-amber-200 bg-amber-100 text-amber-800"
                >
                  Active
                </Badge>
              </div>
              <div className="mb-1 text-3xl font-semibold text-foreground">
                {summary.running_audits}
              </div>
              <div className="text-sm text-muted-foreground">
                Currently processing
              </div>
            </Card>

            <Card className="glass-card p-6">
              <div className="mb-2 flex items-center justify-between">
                <Users className="h-5 w-5 text-foreground" />
                <Badge
                  variant="outline"
                  className="border-border/70 bg-muted/50 text-foreground"
                >
                  Unique
                </Badge>
              </div>
              <div className="mb-1 text-3xl font-semibold text-foreground">
                {metrics.unique_domains}
              </div>
              <div className="text-sm text-muted-foreground">
                Tracked domains
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card className="glass-card p-6">
              <div className="mb-4 flex items-center gap-3">
                <div className="rounded-lg bg-red-500/10 p-3">
                  <AlertTriangle className="h-6 w-6 text-red-500" />
                </div>
                <div>
                  <p className="font-semibold text-foreground">
                    Remediation Backlog
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Issues across active projects
                  </p>
                </div>
              </div>
              <div className="mb-2 text-4xl font-semibold text-red-700">
                {metrics.total_issues}
              </div>
              <div className="text-sm text-muted-foreground">
                Average: {metrics.average_issues_per_audit} issues per audit
              </div>
            </Card>

            <Card className="glass-card p-6">
              <div className="mb-4 flex items-center gap-3">
                <div className="rounded-lg bg-emerald-500/10 p-3">
                  <Target className="h-6 w-6 text-emerald-500" />
                </div>
                <div>
                  <p className="font-semibold text-foreground">
                    Completion Reliability
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Queue conversion rate
                  </p>
                </div>
              </div>
              <div className="mb-2 text-4xl font-semibold text-emerald-800">
                {summary.success_rate.toFixed(1)}%
              </div>
              <div className="text-sm text-muted-foreground">
                {summary.completed_audits} of {summary.total_audits} completed
              </div>
            </Card>

            <Card className="glass-card p-6">
              <div className="mb-4 flex items-center gap-3">
                <div className="rounded-lg bg-brand/10 p-3">
                  <TrendingUp className="h-6 w-6 text-brand" />
                </div>
                <div>
                  <p className="font-semibold text-foreground">
                    Operational Health
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Failure pressure indicator
                  </p>
                </div>
              </div>
              <div className="mb-2 text-4xl font-semibold text-sky-800">
                {summary.failed_audits === 0 ? "Excellent" : "Good"}
              </div>
              <div className="text-sm text-muted-foreground">
                {summary.failed_audits} failed runs requiring review
              </div>
            </Card>
          </div>

          <AnalyticsHistoryExplorer recentAudits={recentAudits} />

          <Card className="glass-card p-6">
            <h2 className="mb-6 text-xl font-semibold text-foreground">
              Latest Audit Activity
            </h2>
            <div className="space-y-4">
              {recentAudits.slice(0, 10).map((audit: any) => (
                <Link
                  key={audit.id}
                  href={`/${locale}/audits/${audit.id}`}
                  className="glass-panel flex cursor-pointer items-center justify-between rounded-xl p-4 transition-colors hover:bg-muted/50"
                >
                  <div className="flex-1">
                    <div className="mb-1 flex items-center gap-3">
                      <h3 className="font-semibold text-foreground">
                        {audit.domain}
                      </h3>
                      <Badge
                        variant="outline"
                        className={
                          audit.status === "completed"
                            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600"
                            : audit.status === "running"
                              ? "border-amber-500/30 bg-amber-500/10 text-amber-600"
                              : "border-red-500/30 bg-red-500/10 text-red-600"
                        }
                      >
                        {audit.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{audit.url}</p>
                  </div>

                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <div className="text-sm text-muted-foreground">Pages</div>
                      <div className="text-lg font-semibold text-foreground">
                        {audit.total_pages}
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-sm text-muted-foreground">
                        Issues
                      </div>
                      <div className="text-lg font-semibold text-red-500">
                        {(audit.issues.critical || 0) +
                          (audit.issues.high || 0) +
                          (audit.issues.medium || 0) +
                          (audit.issues.low || 0)}
                      </div>
                    </div>

                    {audit.status === "running" ? (
                      <div className="text-right">
                        <div className="text-sm text-muted-foreground">
                          Progress
                        </div>
                        <div className="text-lg font-semibold text-amber-500">
                          {audit.progress}%
                        </div>
                      </div>
                    ) : null}
                  </div>
                </Link>
              ))}
            </div>

            {recentAudits.length === 0 ? (
              <div className="py-12 text-center text-muted-foreground">
                <BarChart3 className="mx-auto mb-3 h-12 w-12 opacity-40" />
                <p>
                  No audit activity yet. Run your first audit to unlock this
                  dashboard.
                </p>
              </div>
            ) : null}
          </Card>
        </div>
      </main>
    </div>
  );
}
